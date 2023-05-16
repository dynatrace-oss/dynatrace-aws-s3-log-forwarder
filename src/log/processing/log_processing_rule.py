# Copyright 2022 Dynatrace LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from dataclasses import dataclass, field
from typing import Optional, List
import logging
import re
from pygrok import Grok
import jmespath
import dateutil.parser as dateparser
from utils.helpers import helper_regexes, custom_grok_expressions, get_attributes_from_cloudwatch_logs_data

logger = logging.getLogger(__name__)

def parse_date_from_string(date_string: str):
    '''
    Uses dateutil to parse a date from a given str
    '''
    datetime = date_string

    try:
        datetime = dateparser.parse(date_string,fuzzy=True).isoformat()
    except dateparser.ParserError:
        # Redshift timestamp doesn't include timezone, but logs are UTC. Example:
        # authenticated |Tue, 21 Feb 2023 16:58:20:471|[local]
        try:
            datetime = dateparser.parse(date_string + "Z",fuzzy=True).isoformat()
        except dateparser.ParserError:
            logger.exception("Unable to convert string timestamp")

    return datetime

@dataclass(frozen=True)
class LogProcessingRule:
    name: str
    source: str
    known_key_path_pattern: str
    log_format: str
    # if json_stream, we may want to filter out specific objects from a string
    # containing a specific key/value pair
    filter_json_objects_key: Optional[str]
    filter_json_objects_value: Optional[str]
    # if json or json_stream, a key may contain the list of log entries
    log_entries_key: Optional[str]
    annotations: Optional[dict]
    requester: Optional[List[str]]
    attribute_extraction_from_key_name: Optional[dict]
    attribute_extraction_grok_expression: Optional[str]
    attribute_extraction_jmespath_expression: Optional[dict]
    # if json_stream with log entry list, we may want to inherit attributes from top level json
    attribute_extraction_from_top_level_json: Optional[dict]
    attribute_mapping_from_top_level_json: Optional[dict]
    known_key_path_pattern_regex: re.Pattern = field(init=False)
    attribute_extraction_from_key_name_regex: re.Pattern = field(init=False)
    attribute_extraction_grok_object: Grok = field(init=False)
    skip_header_lines: Optional[int] = None

    def validate(self):
        '''
        Validate attribute types
        '''

        # Validate mandatory strings
        for i in [self.name, self.source, self.log_format, self.known_key_path_pattern]:
            if not isinstance(i, str):
                raise ValueError(f"{i} is not a string.")

        # validate optional strings
        for i in [self.attribute_extraction_grok_expression,
                  self.log_entries_key, self.filter_json_objects_key,
                  self.filter_json_objects_value]:
            if not (isinstance(i, str) or i is None):
                raise ValueError(f"{i} is not a string.")

        # validate optional dicts
        for i in [self.annotations, self.attribute_extraction_from_key_name,
                  self.attribute_extraction_jmespath_expression,
                  self.attribute_extraction_from_top_level_json,
                  self.attribute_mapping_from_top_level_json]:
            if not (isinstance(i, dict) or i is None):
                raise ValueError(f"{i} is not a dict.")
        if self.attribute_mapping_from_top_level_json is not None:
            if not (('include' in self.attribute_mapping_from_top_level_json) ^ \
                    ('exclude' in self.attribute_mapping_from_top_level_json)):
                raise ValueError(f"{self.attribute_mapping_from_top_level_json} should not define exactly one of 'include' or 'exclude'")

        # validate attribute extraction from top level json
        if (self.attribute_extraction_from_top_level_json and self.log_format != "json_stream" and
           self.log_entries_key is None):
            raise ValueError(
                "attribute_extraction_from_top_level_json is only valid for JSON Stream with JSON list entries")

        # validate filter json key-value if not None
        if self.filter_json_objects_key and not self.filter_json_objects_value:
            raise ValueError(
                "filter_json_objects_value can't be None if filter_json_objects_key is specified")

        # validate optional lists
        if not (isinstance(self.requester, list) or self.requester is None):
            raise ValueError("requester is not a list.")
        elif isinstance(self.requester, list):
            for i in self.requester:
                if not isinstance(i, str):
                    raise ValueError(
                        "requester list contains non-string items")

        # validate log format
        if self.log_format not in ['text', 'json', 'json_stream']:
            raise ValueError(
                "log_format must be either text, json or json_stream.")

        # validate skip_header_lines is int if defined, and not defined for non text log
        if self.skip_header_lines != 0 and self.log_format != "text":
            raise ValueError("skip_header_lines is only valid for text log format")
        elif not isinstance(self.skip_header_lines, int):
            raise ValueError(
                "skip_header_lines must be an int."
            )

    def __post_init__(self):
        self.validate()
        # Compile Regular expression here using defined helper patterns
        object.__setattr__(self, "known_key_path_pattern_regex", re.compile(
            self.known_key_path_pattern.format(**helper_regexes)))

        if self.attribute_extraction_from_key_name is not None:
            # Compile regular expressions for attribute extraction from key using
            # the defined helper patterns
            compiled_regexes_dict = {}
            for k, v in self.attribute_extraction_from_key_name.items():
                compiled_regexes_dict[k] = re.compile(
                    v.format(**helper_regexes))
            object.__setattr__(
                self, "attribute_extraction_from_key_name_regex", compiled_regexes_dict)
        else:
            object.__setattr__(
                self, "attribute_extraction_from_key_name_regex", None)

        # Load Grok object once. PyGrok reloads all patterns on __init__
        if self.attribute_extraction_grok_expression is not None:
            object.__setattr__(self, "attribute_extraction_grok_object", Grok(
                self.attribute_extraction_grok_expression,custom_patterns=custom_grok_expressions))
        else:
            object.__setattr__(self, "attribute_extraction_grok_object", None)

    def get_attributes_from_s3_key_name(self, key: str):
        '''
        Extract the required attributes from the S3 Key Name
        '''
        injected_attributes = {}
        if self.attribute_extraction_from_key_name_regex is not None:
            for dt_attribute, regex in self.attribute_extraction_from_key_name_regex.items():
                attrib = re.search(regex, key)
                if attrib is not None:
                    injected_attributes.update({dt_attribute: attrib.group()})
        return injected_attributes

    def get_extracted_log_attributes(self, message) -> dict:
        '''
        Receives the log message (dict or str) and extracts attributes.
        Text log: apply grok expression if it exists; then apply jmespath expression if it exists to calculate additional fields.
        JSON log: apply JMESPATH expressions to extract attributes.
        Tries to generate an ISO timestamp if the attribute timestamp_to_transform is present after extraction
        Cleans up attributes with Null values
        '''

        attributes_dict = {}
        json_message = {}

        if self.attribute_extraction_grok_object is not None:
            if isinstance(message, str):
                grok_attributes = self.attribute_extraction_grok_object.match(
                    message)
                if grok_attributes is not None:
                    attributes_dict.update(grok_attributes)
                    # Create JSON message, in case we need to apply also
                    # JMESPATH to new extracted attributes
                    json_message.update(grok_attributes)
                else:
                    logger.debug(
                        'Grok expression did not match log message: %s --> No attributes extracted.',
                        message)
            else:
                logger.error(
                    "Can't apply Grok expression to non-str object.")

        # if no grok expression, check if message is a Dict
        if isinstance(message, dict):
            json_message = message

        if self.attribute_extraction_jmespath_expression is not None:
            for k, v in self.attribute_extraction_jmespath_expression.items():
                jmespath_attr = jmespath.search(v, json_message)
                if jmespath_attr is not None:
                    attributes_dict[k] = jmespath_attr
                    # if attribute is being renamed from existing attribute remove
                    # but consider the case when an attribute is being extracted from json with the same name for mapping
                    # e.g timestamp extraction
                    if k != v:
                        attributes_dict.pop(v,'')
                else:
                    logger.warning('No matches for JMESPATH expression %s', v)

        if self.attribute_mapping_from_top_level_json is not None:

            _prefix = self.attribute_mapping_from_top_level_json['prefix']
            _postfix = self.attribute_mapping_from_top_level_json['postfix']
            _include = self.attribute_mapping_from_top_level_json.get('include')
            _exclude = self.attribute_mapping_from_top_level_json.get('exclude')

            _attributes_dict = {
                _prefix + k + _postfix: v for k, v in json_message.items() \
                if (_include and k in _include) or \
                   (_exclude and k not in _exclude)
            }
            
            attributes_dict.update(_attributes_dict)

        # Check if timestamp needs to be translated to ISO format
        if "timestamp_to_transform" in attributes_dict:
            attributes_dict['timestamp'] = parse_date_from_string(
                                            attributes_dict['timestamp_to_transform'])
            attributes_dict.pop('timestamp_to_transform')
        
        # Check if aws.log_group exists to extract aws.service and aws.resource.id
        if "aws.log_group" in json_message and "aws.log_stream" in json_message:
            attributes_dict.update(get_attributes_from_cloudwatch_logs_data(
                json_message['aws.log_group'], json_message['aws.log_stream']
            ))

        # Clean up Null values
        clean_attributes_dict = {k: v for k,v in attributes_dict.items() if v is not None}

        return clean_attributes_dict

    def get_processing_log_annotations(self):
        attributes = {}
        if self.annotations is not None:
            attributes.update(self.annotations)

        return attributes

    def get_all_attributes(self, message, s3_key_name):
        '''
        Returns all attributes generated for a given log message (str or dict) and S3 key:
          - Attributes extracted from S3 Key Name
          - Attributes extracted with Grok and Jmespath expressions
          - LogProcessingRule specific annotations
        '''

        attributes = {}

        attributes.update(self.get_attributes_from_s3_key_name(s3_key_name))
        attributes.update(self.get_extracted_log_attributes(message))
        attributes.update(self.get_processing_log_annotations())

        return attributes

    def match_s3_key(self, key_name: str) -> bool:
        '''
        Matches the given S3 key against known format for processing rule
        '''
        if self.known_key_path_pattern_regex.match(key_name):
            return True
        else:
            return False
