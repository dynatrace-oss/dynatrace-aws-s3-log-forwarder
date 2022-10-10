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

from log.processing import LogProcessingRule
from utils.helpers import is_yaml_file, ENCODING
import os
import logging
import yaml

BUILT_IN_PROCESSING_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "rules"
)
DEFAULT_CUSTOM_LOG_PROCESSING_RULES_PATH = "./config/log_processing_rules"

AVAILABLE_LOG_SOURCES = ['aws', 'generic', 'custom']

logger = logging.getLogger()

def list_rules_in_dir(rules_dir):
    '''
    List yaml files within directory and subdirectories
    '''

    log_processing_rule_files = []

    for path, dirs, files in os.walk(rules_dir):
        for file in files:
            if is_yaml_file(file):
                log_processing_rule_files.append(os.path.join(path,file))

    return log_processing_rule_files


def create_log_processing_rule(rule_dict):
    '''
    Genereates a LogProcessingRule Object from a dict
    '''

    # Validate we have all required attributes, and set to None the ones undefined

    required_attributes = ['name', 'source','known_key_path_pattern', 'log_format']
    optional_attributes = ['log_entries_key', 'annotations','requester',
                           'attribute_extraction_from_key_name', 'attribute_extraction_grok_expression',
                           'attribute_extraction_jmespath_expression']

    for attribute in required_attributes:
        if attribute not in rule_dict.keys():
            raise InvalidLogProcessingRuleFile
    
    for attribute in optional_attributes:
        if attribute not in rule_dict.keys():
            rule_dict[attribute] = None

    try:
        processing_rule = LogProcessingRule(
            rule_dict['name'],
            rule_dict['source'],
            rule_dict['known_key_path_pattern'],
            rule_dict['log_format'],
            rule_dict['log_entries_key'],
            rule_dict['annotations'],
            rule_dict['requester'],
            rule_dict['attribute_extraction_from_key_name'],
            rule_dict['attribute_extraction_grok_expression'],
            rule_dict['attribute_extraction_jmespath_expression']
        )
    except ValueError as e:
        raise InvalidLogProcessingRuleFile("Error parsing processing rule.")

    return processing_rule

def load_rules_from_dir(directory: str) -> dict:
    '''
    Looks for yaml files on the given directory and its subdirectories and attempts to load them as LogProcessingRule(s)
    '''
    
    log_processing_rule_files = list_rules_in_dir(directory)

    # initialize log_processing_rules
    log_processing_rules = {}
    for log_source in AVAILABLE_LOG_SOURCES:
        log_processing_rules[log_source] = {}

    for file in log_processing_rule_files:
        try:
            with open(file, encoding=ENCODING) as rule_file:
                processing_rule_dict = yaml.load(
                    rule_file, Loader=yaml.loader.SafeLoader)
                # if not a dict
                if not isinstance(processing_rule_dict, dict):
                    raise InvalidLogProcessingRuleFile(file=rule_file)
                
                # Check that source on the rule is valid. (custom is custom.name)
                source = processing_rule_dict['source'].split('.')[0]
                if source not in AVAILABLE_LOG_SOURCES:
                    raise InvalidLogProcessingRuleFile(file=rule_file,message="Invalid log source on rule file.")

                log_processing_rules[source][processing_rule_dict['name']] = create_log_processing_rule(processing_rule_dict)

        except InvalidLogProcessingRuleFile as e:
            logger.exception(e)
    
    return log_processing_rules
        
class InvalidLogProcessingRuleFile(Exception):

    def __init__(self, file=None, message='Processing rule file is invalid.'):
        self.file = file
        self.message = message

    
def load_built_in_rules():
    '''
    Load built-in log processing rules. 
    '''
    return load_rules_from_dir(BUILT_IN_PROCESSING_RULES_PATH)
    

def load_custom_rules():
    '''
    Load custom Log Processing rules.
    '''

    # initialize log_processing_rules
    log_processing_rules = {}
    for log_source in AVAILABLE_LOG_SOURCES:
        log_processing_rules[log_source] = {}

    if 'LOG_PROCESSING_RULES_PATH' in os.environ:
        log_processing_rules_directory = os.environ['LOG_PROCESSING_RULES_PATH']
    else:
        log_processing_rules_directory = DEFAULT_CUSTOM_LOG_PROCESSING_RULES_PATH

    if os.path.isdir(log_processing_rules_directory):
        loaded_log_processing_rules = load_rules_from_dir(log_processing_rules_directory)
        # if not an empty dict
        if loaded_log_processing_rules:
            log_processing_rules = loaded_log_processing_rules
    return log_processing_rules

def load():
    '''
    Loads built-in and custom log processing rules
    '''
    built_in_rules = load_built_in_rules()
    custom_rules = load_custom_rules()

    # initialize log_processing_rules
    log_processing_rules = {}
    for log_source in AVAILABLE_LOG_SOURCES:
        log_processing_rules[log_source] = {}

    # iterate over built-in and custom rules content to generate combined rules dict
    for source,built_in_rule_dict in built_in_rules.items():
        log_processing_rules[source].update(built_in_rule_dict)

    for custom_source,custom_rule_dict in custom_rules.items():
        log_processing_rules[custom_source].update(custom_rule_dict)

    return log_processing_rules

def lookup_processing_rule(source: str , source_name: str, processing_rules: dict, key_name: str):
    '''
    Given a dict of processing rules:
        {
            'aws': { 'name1' : LogProcessingRule, 'name2': LogProcessingRule },
            'custom': {'name1' : LogProcessingRule, 'name2': LogProcessingRule },
            'generic': { 'generic': LogProcessingRule }
        }
    Looks for a matching rule. If it's an aws rule, looks for the specific service Processing Rule matching key_name.
    If no processing rule is matched, returns generic rule.
    if source is invalid or None, returns None.
    source_name is only used for 'custom' rules.
    '''
    
    if not source in AVAILABLE_LOG_SOURCES or source is None:
        return None
    elif source == 'generic':
        return processing_rules['generic']['generic']
    # is it a custom rule? (e.g. custom.nginx)
    elif source == 'custom':
        try:
            logger.debug(f'Matched log processing rule {source}.{source_name}')
            return processing_rules['custom'][source_name]
        except KeyError:
            logger.warning(f"No matching log processing rule for {source}.{source_name}."
                            "Defaulting to 'generic' log ingestion.")
            return processing_rules['generic']['generic']
    elif source == 'aws':
        matched_processing_rule = None
        # if it's an AWS source, attempt to guess AWS Service
        for name, processing_rule in processing_rules['aws'].items():
            if processing_rule.match_s3_key(key_name):
                logger.debug(f"Matched aws log processing rule {name}")
                return processing_rule
        if not matched_processing_rule:
            logger.warning(f"Couldn't find a matching aws processing rule for {key_name}. Defaulting to generic ingestion.")
            return processing_rules['generic']['generic']