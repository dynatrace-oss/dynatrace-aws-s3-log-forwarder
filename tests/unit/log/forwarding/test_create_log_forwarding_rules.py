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

import unittest
from log.forwarding import log_forwarding_rules

class TestForwardingRules(unittest.TestCase):

    def test_create_valid_log_forwarding_rules(self):
        '''
        Test that valid log forwarding rules are correctly created.
        '''

        valid_rules = [ 
            {   
                'rule_name': 'Send CloudTrail and ELB logs',
                'prefix': '^AWSLogs/.*/(CloudTrail|elasticloadbalancing)/.*',
                'source': 'aws',
                'annotations': {'test':'true'},
                'sinks': ['1']
            },
            {
                'rule_name': 'Send Jenkins Logs',
                'prefix': '^jenkins/.*(\\.log)',
                'source': 'generic',
                'sinks': ['1','2']
            }
        ]

        for rule in valid_rules:
            with self.subTest(valid_rule=rule):
                try:
                    self.assertIsInstance(log_forwarding_rules._create_log_forwarding_rule_object(rule),
                                          log_forwarding_rules.LogForwardingRule)
                except Exception:
                    self.fail("LogForwardingRule wasn't successfully created.")

    def test_create_invalid_log_forwarding_rules(self):
        '''
        Test that we catch invalid forwarding rules on creating time.
        '''
        invalid_rules = [
            {
                'prefix': '^AWSLogs/.*/(CloudTrail|elasticloadbalancing)/.*',
                'source': 'random',
                'annotations': {'test':'true'},
                'sinks': ['1']
            }
        ]

        for rule in invalid_rules:
            with self.subTest(invalid_rule=rule):
                with self.assertRaises(log_forwarding_rules.IncorrectLogForwardingRuleFormat):
                    log_forwarding_rules._create_log_forwarding_rule_object(rule)

if __name__ == '__main__':
    unittest.main()