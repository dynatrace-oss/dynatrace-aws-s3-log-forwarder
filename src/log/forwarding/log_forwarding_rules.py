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
from log.processing.log_processing_rules import AVAILABLE_LOG_SOURCES
from utils.helpers import ENCODING


DEFAULT_FORWARING_RULES_PATH =  "./config/log_forwarding_rules"

logger = logging.getLogger()

def load():
    '''
    Loads log forwarding rules from config/log_forwarding_rules directory.
    Returns a dictionary with bucket_names as keys and the rules as value:
    { bucket_a: { rule_name: LogForwardingRule }, bucket_b: {...}}
    '''

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
                        log_forwarding_rules[bucket_name][rule['rule_name']] = rule_obj
                    except IncorrectLogForwardingRuleFormat as e:
                        logger.warning(
                            'Skipping incorrect log forwarding rule: %s in %s', rule, rule_file.name)
                        logger.error(e)
                        continue

        except InvalidLogForwardingRuleFile as e:
            logger.exception(
                'Invalid forwarding rules file: %s',
                e.file)
            continue

        except Exception as e:
            logger.exception(
                'Failed to load configuration file: %s. %s',
                rule_config_file_path, e)
            continue

    return log_forwarding_rules

def get_matching_log_forwarding_rule(bucket_name, key_name, log_forwarding_rules):
    '''
    Checks against existing log forwarding rules for bucket name. If there's a match, returns the LogForwardingRule object.
    It only checks the first rule that matches (if key matches multiple rules).
    If there's no match, returns None.
    '''
    try:
        for rule_name, rule in log_forwarding_rules[bucket_name].items():
            if rule.match(key_name):
                return rule
    except KeyError:
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
        return f"{self.message} -> {self.file}"


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

        log_forwarding_rule = LogForwardingRule(name=rule['rule_name'],
                                                s3_prefix_expression=compiled_regex,
                                                source=rule['source'],
                                                source_name=rule['source_name'], 
                                                annotations=rule['annotations'], 
                                                sinks=rule['sinks'])
    except KeyError as e:
        raise IncorrectLogForwardingRuleFormat(message=f"Missing attributes on log forwarding rule {rule}:", part=e)
    except ValueError:
        raise IncorrectLogForwardingRuleFormat(message="LogForwardingRule contains invalid attributes.")
    except Exception:
        raise IncorrectLogForwardingRuleFormat("Unable to create LogForwarding rule.")

    return log_forwarding_rule

