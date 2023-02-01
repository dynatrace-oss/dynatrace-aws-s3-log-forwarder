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

import os
import logging
import yaml
from log.processing import LogProcessingRule
from utils.helpers import is_yaml_file, ENCODING
from utils import aws_appconfig_extension_helpers as aws_appconfig_helpers

BUILT_IN_PROCESSING_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "rules"
)
DEFAULT_CUSTOM_LOG_PROCESSING_RULES_PATH = "./config/log_processing_rules"
DEFAULT_CUSTOM_LOG_PROCESSING_RULES_FILE = './config/log-processing-rules.yaml'

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
                           'attribute_extraction_jmespath_expression', 'filter_json_objects_key',
                           'filter_json_objects_value','attribute_extraction_from_top_level_json']

    for attribute in required_attributes:
        if attribute not in rule_dict.keys():
            raise InvalidLogProcessingRuleFile
    
    for attribute in optional_attributes:
        if attribute not in rule_dict.keys():
            rule_dict[attribute] = None
    
    # Check that source on the rule is valid. (
    if rule_dict['source'] not in AVAILABLE_LOG_SOURCES:
       raise InvalidLogProcessingRuleFile(message="Invalid log source on processing rule.")

    try:
        processing_rule = LogProcessingRule(
            name= rule_dict['name'],
            source = rule_dict['source'],
            known_key_path_pattern = rule_dict['known_key_path_pattern'],
            log_format = rule_dict['log_format'],
            filter_json_objects_key = rule_dict['filter_json_objects_key'],
            filter_json_objects_value = rule_dict['filter_json_objects_value'],
            log_entries_key = rule_dict['log_entries_key'],
            annotations = rule_dict['annotations'],
            requester = rule_dict['requester'],
            attribute_extraction_from_key_name = rule_dict['attribute_extraction_from_key_name'],
            attribute_extraction_grok_expression = rule_dict['attribute_extraction_grok_expression'],
            attribute_extraction_jmespath_expression = rule_dict['attribute_extraction_jmespath_expression'],
            attribute_extraction_from_top_level_json = rule_dict['attribute_extraction_from_top_level_json']
        )
    except ValueError as ex:
        raise InvalidLogProcessingRuleFile("Error parsing log processing rule.") from ex

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

                log_processing_rules[processing_rule_dict['source']][processing_rule_dict['name']] = create_log_processing_rule(processing_rule_dict)

        except (KeyError, InvalidLogProcessingRuleFile):
            logger.exception("There was an error creating the log processing rule. Log processing rule is invalid.")
    
    return log_processing_rules

def load_processing_rules_from_yaml(body: str):
    '''
    Gets a raw str with log processing rules in yaml format to return a dictionary of LogProcessingRule(s)
    {
        "aws": {},
        "generic": {},
        "custom": {
            "example_rule1": LogProcessingRule,
            "example_rule2": LogProcessingRule
        }
    }
    '''
    # initialize log_processing_rules
    log_processing_rules = {}
    for log_source in AVAILABLE_LOG_SOURCES:
        log_processing_rules[log_source] = {}

    try:
        yaml_iterator = yaml.load_all(body, Loader=yaml.SafeLoader)
        for i, processing_rule_dict in enumerate(yaml_iterator):
            try:
                if isinstance(processing_rule_dict,dict):
                    log_processing_rules[processing_rule_dict['source']][processing_rule_dict['name']] = create_log_processing_rule(processing_rule_dict)
                elif processing_rule_dict is None:
                    logger.warning("Skipping empty log processing rule")
                else:
                    raise InvalidLogProcessingRuleFile(file=str(i), message="Invalid log forwarding rule file")
            except (KeyError, InvalidLogProcessingRuleFile):
                logger.exception("There was an error creating the log processing rule. Log processing rule %s is invalid", str(i))
        
    except yaml.YAMLError:
        logger.exception("Encountered an error while parsing log-processing-rules. Aborting...")
    
    return log_processing_rules

def load_custom_rules_from_aws_appconfig():
    '''
    Loads custom log processing rules from AWS AppConfig. Returns a tuple containing a dict with the rules
    and the Configuration-Version number.
    '''

    logger.info("Loading custom log-processing-rules from AWS AppConfig...")

    raw_processing_rules = aws_appconfig_helpers.get_configuration_from_aws_appconfig('log-processing-rules')

    log_processing_rules = load_processing_rules_from_yaml(raw_processing_rules['Body'])

    return log_processing_rules, raw_processing_rules['Configuration-Version']

def load_custom_rules_from_local_file():
    '''
    Loads custom log processing rules from a local file config/log-processing-rules.yaml. Returns a tuple 
    containing a dict with the rules and the Configuration-Version number.
    '''

    logger.info("Loading custom log-processing-rules from local file config/log-processing-rules.yaml ...")

    try:
        with open(file=DEFAULT_CUSTOM_LOG_PROCESSING_RULES_FILE,mode='r',encoding=ENCODING) as file:
            log_processing_rules = load_processing_rules_from_yaml(file.read())
    except OSError:
        logger.exception("Unable to open local file %s", DEFAULT_CUSTOM_LOG_PROCESSING_RULES_FILE)
        raise

    return log_processing_rules
     
class InvalidLogProcessingRuleFile(Exception):

    def __init__(self, file=None, message='Processing rule file is invalid.'):
        self.file = file
        self.message = message

    def __str__(self):
        return f"{self.message} --> {self.file}"

    
def load_built_in_rules():
    '''
    Load built-in log processing rules. 
    '''
    return load_rules_from_dir(BUILT_IN_PROCESSING_RULES_PATH)
    

def load_custom_rules():
    '''
    Load custom Log Processing rules. Returns a dict with the rules and the version.
    If custom rules are local, version is set to 0.
    '''
    log_processing_rules_verison = 0

    if os.environ.get('LOG_FORWARDER_CONFIGURATION_LOCATION') == 'aws-appconfig':
        log_processing_rules, log_processing_rules_verison = load_custom_rules_from_aws_appconfig()

    elif os.environ.get('LOG_FORWARDER_CONFIGURATION_LOCATION') == 'local':
        if 'LOG_PROCESSING_RULES_PATH' in os.environ:
            log_processing_rules_directory = os.environ['LOG_PROCESSING_RULES_PATH']
        else:
            log_processing_rules_directory = DEFAULT_CUSTOM_LOG_PROCESSING_RULES_PATH
        
        if os.path.isfile(DEFAULT_CUSTOM_LOG_PROCESSING_RULES_FILE):
            log_processing_rules = load_custom_rules_from_local_file()
        elif os.path.isdir(log_processing_rules_directory):
            loaded_log_processing_rules = load_rules_from_dir(log_processing_rules_directory)
            # if not an empty dict
            if loaded_log_processing_rules:
                log_processing_rules = loaded_log_processing_rules
            else:
                # initialize log_processing_rules
                log_processing_rules = {}
                for log_source in AVAILABLE_LOG_SOURCES:
                    log_processing_rules[log_source] = {}

    return log_processing_rules, log_processing_rules_verison

def load():
    '''
    Loads built-in and custom log processing rules
    '''
    built_in_rules = load_built_in_rules()
    custom_rules, custom_rules_version = load_custom_rules()

    # initialize log_processing_rules
    log_processing_rules = {}
    for log_source in AVAILABLE_LOG_SOURCES:
        log_processing_rules[log_source] = {}

    # iterate over built-in and custom rules content to generate combined rules dict
    for source,built_in_rule_dict in built_in_rules.items():
        log_processing_rules[source].update(built_in_rule_dict)

    for custom_source,custom_rule_dict in custom_rules.items():
        log_processing_rules[custom_source].update(custom_rule_dict)

    return log_processing_rules, custom_rules_version

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
    # is it a generic or custom rule? 
    elif source == 'custom' or source == 'generic':
        try:
            logger.debug('Matched log processing rule %s.%s',
            source,source_name)
            return processing_rules[source][source_name]
        except KeyError:
            logger.warning("No matching log processing rule for %s.%s. "
                            "Defaulting to 'generic' log ingestion.", source, source_name)
            return processing_rules['generic']['generic']
    elif source == 'aws':
        matched_processing_rule = None
        # if it's an AWS source, attempt to guess AWS Service
        for name, processing_rule in processing_rules['aws'].items():
            if processing_rule.match_s3_key(key_name):
                logger.debug("Matched aws log processing rule %s", name)
                return processing_rule
        if not matched_processing_rule:
            logger.warning("Couldn't find a matching aws processing rule for %s. Defaulting to generic ingestion.", key_name)
            return processing_rules['generic']['generic']