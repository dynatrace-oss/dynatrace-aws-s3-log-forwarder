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


import logging
import re
import os
import yaml

from . import LogForwardingRule
from utils.helpers import is_yaml_file
from utils import aws_appconfig_extension_helpers as aws_appconfig_helpers
from log.processing.log_processing_rules import AVAILABLE_LOG_SOURCES
from utils.helpers import ENCODING


DEFAULT_FORWARING_RULES_PATH =  "./config/log_forwarding_rules"

logger = logging.getLogger()

def load():
    '''
    Loads log forwarding rules from AWS Config or from local file. Only use this method for 
    lambda startup.
    '''
    if os.environ.get('LOG_FORWARDER_CONFIGURATION_LOCATION') == 'aws-appconfig':
        return load_forwarding_rules_from_aws_appconfig()
    elif os.environ.get('LOG_FORWARDER_CONFIGURATION_LOCATION') == 'local':
        return load_forwading_rules_from_local_folder()

def load_forwarding_rules_from_aws_appconfig():
    '''
    Loads log forwarding rules from AWS AppConfig using its AWS Lambda extension
    '''

    logger.info("Loading log-forwarding-rules from AWS AppConfig...")

    raw_forwarding_rules = aws_appconfig_helpers.get_configuration_from_aws_appconfig('log-forwarding-rules')

    log_forwarding_rules = {}

    try:
        yaml_iterator = yaml.load_all(raw_forwarding_rules['Body'],Loader=yaml.SafeLoader)
        for i, forwarding_rule_dict in enumerate(yaml_iterator):
            try:
                if isinstance(forwarding_rule_dict,dict):
                    try:
                        log_forwarding_rules[forwarding_rule_dict['bucket_name']] = {}
                        logger.info("Loading log-forwarding-rules for S3 bucket: %s", forwarding_rule_dict['bucket_name'])
                        if isinstance(forwarding_rule_dict['log_forwarding_rules'],list):
                            for j, rule in enumerate(forwarding_rule_dict['log_forwarding_rules']):
                                try:
                                    log_forwarding_rules[forwarding_rule_dict['bucket_name']][rule['name']] = _create_log_forwarding_rule_object(rule)
                                    logger.info("Loaded log-forwarding-rule: %s", rule['name'])
                                except IncorrectLogForwardingRuleFormat:
                                    logger.exception("%s: Skipping incorrect log forwarding rule %s", 
                                                     forwarding_rule_dict['bucket_name'],str(j))
                    except KeyError as ex:
                        raise InvalidLogForwardingRuleFile(file=str(i)) from ex
                elif forwarding_rule_dict is None:
                    logger.warning("Skipping empty log forwarding rule %s", str(i))
                else:
                    raise InvalidLogForwardingRuleFile(file=str(i))
            except InvalidLogForwardingRuleFile:
                logger.exception("Encountered an error while parsing log forwarding rule %s from AWS AppConfig",str(i))

    except yaml.YAMLError:
        logger.exception("Encountered an error while parsing load-forarding-rules. Aborting...")

    return log_forwarding_rules , raw_forwarding_rules['Configuration-Version']

def load_forwading_rules_from_local_folder():

    '''
    Loads log forwarding rules from config/log_forwarding_rules directory.
    Returns a dictionary with bucket_names as keys and the rules as value:
    { bucket_a: { rule_name: LogForwardingRule }, bucket_b: {...}}
    '''

    logger.info("Loading log-forwarding-rules from local folder...")

    if 'LOG_FORWARDING_RULES_PATH' in os.environ:
        log_forwarding_rules_directory = os.environ['LOG_FORWARDING_RULES_PATH']
    else:
        log_forwarding_rules_directory = DEFAULT_FORWARING_RULES_PATH

    # list yaml files on the forwarding rules directory
    log_forwarding_rule_files = [
        file for file
        in os.listdir(log_forwarding_rules_directory)
        if os.path.isfile(os.path.join(log_forwarding_rules_directory, file))
        and is_yaml_file(file)
    ]

    # Create a dict with the log forwarding rules for each S3 Bucket
    log_forwarding_rules = {}

    for rule_file in log_forwarding_rule_files:
        rule_config_file_path = os.path.join(
            log_forwarding_rules_directory, rule_file)
        try:
            with open(rule_config_file_path, encoding=ENCODING) as rule_file:
                rules_list = yaml.load(
                    rule_file, Loader=yaml.loader.SafeLoader)

                # if not a dict
                if not isinstance(rules_list, list):
                    raise InvalidLogForwardingRuleFile(file=rule_file.name)

                logger.debug(
                    'Reading rules from file: %s', rule_config_file_path)

                # Get S3 Bucket name from filename
                bucket_name = os.path.splitext(
                    os.path.basename(rule_config_file_path))[0]
                if not bucket_name in log_forwarding_rules:
                    log_forwarding_rules[bucket_name] = {}

                # If rule content is valid, then add to forwarding rule dictionary
                #  log_forwarding_rules format:
                #  {
                #     "bucket_a": {
                #        "rule_name_1": LogForwardingRule,
                #        "rule_name_2": LogForwardingRule
                #     }
                #     "bucket_b": {
                #        "..."
                #     }
                #  }
                for rule in rules_list:
                    try:
                        logger.debug(
                            'Loading rule: %s from file: %s',
                            rule, rule_config_file_path)
                        rule_obj = _create_log_forwarding_rule_object(rule)
                        # temporary assignment while legacy and new schema of log forwarding rules co-live
                        rule_obj['name'] = rule_obj['rule_name']
                        log_forwarding_rules[bucket_name][rule['rule_name']] = rule_obj
                    except IncorrectLogForwardingRuleFormat as ex:
                        logger.warning(
                            'Skipping incorrect log forwarding rule: %s in %s', rule, rule_file.name)
                        logger.error(ex)
                        continue

        except InvalidLogForwardingRuleFile as ex:
            logger.exception(
                'Invalid forwarding rules file: %s',
                ex.file)
            continue

        except Exception as ex:
            logger.exception(
                'Failed to load configuration file: %s. %s',
                rule_config_file_path, ex)
            continue
    
    return log_forwarding_rules, None

def get_matching_log_forwarding_rule(bucket_name, key_name, log_forwarding_rules):
    '''
    Checks against existing log forwarding rules for bucket name. If there's a match, returns the LogForwardingRule object.
    If there's no explicit rules for the bucket, but there's a default definition, try to match against default rules.
    It only checks the first rule that matches (if key matches multiple rules).
    If there's no match, returns None.
    '''
    try:
        for _ , rule in log_forwarding_rules[bucket_name].items():
            if rule.match(key_name):
                return rule
    except KeyError:
        # if there's no explicit rules for this bucket, but there's a default bucket defined, try to match with rules
        if log_forwarding_rules.get('default',False):
            for _ , rule in log_forwarding_rules['default'].items():
                if rule.match(key_name):
                    return rule
        return None

    return None

class IncorrectLogForwardingRuleFormat(Exception):
    '''
    Exception raised for formatting errors with Log Forwarding rules.
    '''

    def __init__(self, message='Invalid log forwarding rule format: ', part=None):
        self.message = message
        self.part = part
    
    def __str__(self):
        return f"{self.message} {self.part}"

    
class InvalidLogForwardingRuleFile(Exception):
    '''
    Exception raised when
    '''

    def __init__(self, file=None, message='Forwarding rules file is invalid'):
        self.file = file
        self.message = message

    def __str__(self):
        return f"{self.message} -> {self.file} \n"


def _create_log_forwarding_rule_object(rule: dict) -> LogForwardingRule:
    '''
    Creates LogForwardingRule object from dictionary, filling optional values not passed with None.
    '''
    log_forwarding_rule = None

    try:
        compiled_regex = re.compile(rule['prefix'])

         # fill optional values if not present
        for i in ['source_name','sinks','annotations']:
            if not rule.get(i):
                rule[i] = None

        log_forwarding_rule = LogForwardingRule(name=rule['name'],
                                                s3_prefix_expression=compiled_regex,
                                                source=rule['source'],
                                                source_name=rule['source_name'], 
                                                annotations=rule['annotations'], 
                                                sinks=rule['sinks'])
    except KeyError as ex:
        raise IncorrectLogForwardingRuleFormat(message=f"Missing attributes on log forwarding rule {rule}") from ex
    except ValueError as ex:
        raise IncorrectLogForwardingRuleFormat(message="LogForwardingRule contains invalid attributes.") from ex
    except Exception as ex:
        raise IncorrectLogForwardingRuleFormat("Unable to create LogForwarding rule.") from ex

    return log_forwarding_rule

