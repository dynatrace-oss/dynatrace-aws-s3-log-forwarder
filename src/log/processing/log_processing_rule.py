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
from pygrok import Grok
import jmespath
import re
from utils.helpers import helper_regexes


logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LogProcessingRule:
    name: str
    source: str
    known_key_path_pattern: str
    log_format: str
    # if json_stream, we may want to filter out specific objects from a string containing a specific key/value pair
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
    known_key_path_pattern_regex: re.Pattern = field(init=False)
    attribute_extraction_from_key_name_regex: re.Pattern = field(init=False)
    attribute_extraction_grok_object: Grok = field(init=False)

    def validate(self):
        '''
        Validate attribute types
        '''

        # Validate mandatory strings
        for i in [self.name, self.source, self.log_format, self.known_key_path_pattern]:
            if not isinstance(i,str):
                raise ValueError(f"{i} is not a string.")

        # validate optional strings
        for i in [self.attribute_extraction_grok_expression,
                  self.log_entries_key,self.filter_json_objects_key,
                  self.filter_json_objects_value]:
            if not (isinstance(i,str) or i is None):
                raise ValueError(f"{i} is not a string.")

        # validate optional dicts
        for i in [self.annotations, self.attribute_extraction_from_key_name,
                  self.attribute_extraction_jmespath_expression,
                  self.attribute_extraction_from_top_level_json]:
            if not (isinstance(i,dict) or i is None):
                raise ValueError(f"{i} is not a dict.")
        
        # validate attribute extraction from top level json
        if (self.attribute_extraction_from_top_level_json and self.log_format != "json_stream" and
           self.log_entries_key is None):
            raise ValueError("attribute_extraction_from_top_level_json is only valid for JSON Stream with JSON list entries")
        
        #validate filter json key-value if not None
        if self.filter_json_objects_key:
            if not self.filter_json_objects_value:
                raise ValueError("filter_json_objects_value can't be None if filter_json_objects_key is specified")

        # validate optional lists
        if not (isinstance(self.requester,list) or self.requester is None):
            raise ValueError("requester is not a list.")
        elif isinstance(self.requester,list):
            for i in self.requester:
                if not isinstance(i,str):
                    raise ValueError("requester list contains non-string items")

        # validate log format
        if self.log_format not in ['text', 'json', 'json_stream']:
            raise ValueError("log_format must be either text, json or json_stream.")

    def __post_init__(self):
        self.validate()
        # Compile Regular expression here using defined helper patterns
        object.__setattr__(self,"known_key_path_pattern_regex",re.compile(self.known_key_path_pattern.format(**helper_regexes)))

        if self.attribute_extraction_from_key_name is not None:
            # Compile regular expressions for attribute extraction from key using the defined helper patterns
            compiled_regexes_dict = {}
            for k,v in self.attribute_extraction_from_key_name.items():
                compiled_regexes_dict[k] = re.compile(v.format(**helper_regexes))
            object.__setattr__(self,"attribute_extraction_from_key_name_regex",compiled_regexes_dict)
        else:
            object.__setattr__(self,"attribute_extraction_from_key_name_regex",None)
        
        # Load Grok object once. PyGrok reloads all patterns on __init__
        if self.attribute_extraction_grok_expression is not None:
            object.__setattr__(self,"attribute_extraction_grok_object",Grok(self.attribute_extraction_grok_expression))
        else:
            object.__setattr__(self,"attribute_extraction_grok_object",None)

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

    def get_extracted_log_attributes(self,message) -> dict:
        '''
        Receives the log message (dict or str) and extracts attributes.
        Text log: apply grok expression if it exists; then apply jmespath expression if it exists to calculate additional fields.
        JSON log: apply JMESPATH expressions to extract attributes.
        '''

        attributes_dict = {}
        json_message = {}

        if self.attribute_extraction_grok_object is not None:
            if isinstance(message,str):
                grok_attributes = self.attribute_extraction_grok_object.match(message)
                if grok_attributes is not None:
                    attributes_dict.update(grok_attributes)
                    # Create JSON message, in case we need to apply also JMESPATH to new extracted attributes
                    json_message.update(grok_attributes)
                else:
                    logger.warning(f'Grok expression did not match log message: {message} --> No attributes extracted.')
            else:
                logger.warning("Can't apply Grok expression to non-str object.")
        
        # if no grok expression, check if message is a Dict
        if isinstance(message,dict):
            json_message = message

        if self.attribute_extraction_jmespath_expression is not None:
            for k, v in self.attribute_extraction_jmespath_expression.items():
                jmespath_attr = jmespath.search(v, json_message)
                if jmespath_attr is not None:
                    attributes_dict[k] = jmespath_attr
                else:
                    logger.warning('No matches for JMESPATH expression %s', v)

        return attributes_dict

    def get_processing_log_annotations(self):
        attributes = {}
        if self.annotations is not None:
            attributes.update(self.annotations)

        return attributes
    
    def get_all_attributes(self,message,s3_key_name):
        '''
        Returns all attributes generated for a given log message (str or dict) and S3 key:
          - Attributes extracted from S3 Key Name
          - Attributes extracted with Grok and Jmespath expressions
          - LogProcessingRule specific annotations
        '''
        
        attributes = {}

        attributes.update(self.get_attributes_from_s3_key_name(s3_key_name))
        attributes.update(self.get_extracted_log_attributes(message))
        attributes.update(self.get_processing_log_annotations)

        return attributes

    def match_s3_key(self,key_name:str) -> bool:
        if self.known_key_path_pattern_regex.match(key_name):
            return True
        else:
            return False
