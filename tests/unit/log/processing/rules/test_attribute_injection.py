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
import os
from log.processing import log_processing_rules

os.environ['LOG_FORWARDER_CONFIGURATION_LOCATION'] = 'local'
os.environ['DEPLOYMENT_NAME'] = 'test'

processing_rules, _ = log_processing_rules.load()

cloudtrail_key_name = 'random_prefix/AWSLogs/012345678910/CloudTrail/us-east-1/2022/09/23/012345678910_CloudTrail_us-east-1_20220923T2350Z_noxkMtWv70h0LEES.json.gz'
alb_key_name = 'random_prefix/AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_app.k8s-podinfo-podinfoi-ffbc3dc280.82a34fae168ba1aa_20220721T1440Z_192.168.122.18_3okvlwdx.log.gz'
classic_elb_key_name = 'random_prefix/AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_a2e8277e0e09143fbb06db5dcd2a14c2_20220730T2350Z_192.168.36.65_31av101p.log'
nlb_key_name = 'random_prefix/AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_net.k8s-podinfo-frontend-352ef7564b.809b86b470cfa0ff_20220927T1715Z_bbb0861d.log.gz'
waf_key_name = 'random_prefix/AWSLogs/012345678910/WAFLogs/eu-west-1/my-web-acl/2023/02/15/14/30/012345678910_waflogs_us-east-1_my-web-acl_20230215T1430Z_ec507835.log.gz'
cloudfront_key_name = 'example/E1SFLUZKKLSP61.2023-02-16-14.e519cdee.gz'
vpcflowlog_key_name = 'optional_prefix/AWSLogs/012345678910/vpcflowlogs/us-east-1/2023/02/14/012345678910_vpcflowlogs_us-east-1_fl-07f38b767c7cd46e3_20230214T0000Z_129a0cf7.log.gz'
network_firewall_key_name = 'random_prefix/AWSLogs/012345678910/network-firewall/flow/us-east-1/my-test-firewall/2023/02/20/16/012345678910_network-firewall_flow_us-east-1_my-test-firewall_202302201610_e5c84094.log.gz'
msk_key_name = 'AWSLogs/012345678910/KafkaBrokerLogs/us-east-1/demo-cluster-2-043b6d76-352c-494a-9eee-fbff5cc1687d-20/2023-02-20-17/Broker-1_17-05_5b17f696.log.gz'
global_accelerator_key_name = 'myprefix/AWSLogs/012345678910/globalaccelerator/us-west-2/2023/02/21/012345678910_globalaccelerator_f0154cf1-4ac0-451b-87a2-5b2ce89142e6_20230221T1305Z_2e13fabb.log.gz'

class TestAWSAttributeInjection(unittest.TestCase):
    def test_cloudtrail_attributes(self):
        cloudtrail_processing_rule = processing_rules['aws']['CloudTrail']
        expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'us-east-1'
                      }

        attributes = cloudtrail_processing_rule.get_attributes_from_s3_key_name(cloudtrail_key_name)
        self.assertEqual(attributes,expected_attributes)

    def test_alb_attributes(self):
        alb_processing_rule = processing_rules['aws']['ALB']
        expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'us-east-1'
                      }

        attributes = alb_processing_rule.get_attributes_from_s3_key_name(alb_key_name)
        self.assertEqual(attributes,expected_attributes)
    
    def test_classic_attributes(self):
        classic_elb_processing_rule = processing_rules['aws']['Classic-ELB']
        expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'us-east-1'
                      }

        attributes = classic_elb_processing_rule.get_attributes_from_s3_key_name(classic_elb_key_name)
        self.assertEqual(attributes,expected_attributes)

    def test_nlb_attributes(self):
        nlb_processing_rule = processing_rules['aws']['NLB']
        expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'us-east-1'
                      }

        attributes = nlb_processing_rule.get_attributes_from_s3_key_name(nlb_key_name)
        self.assertEqual(attributes,expected_attributes)

    def test_waf_attributes(self):
        waf_processing_rule = processing_rules['aws']['waf']
        attributes = waf_processing_rule.get_attributes_from_s3_key_name(waf_key_name)
        expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'eu-west-1',
                        'aws.resource.id': 'my-web-acl'
                      }
        
        self.assertEqual(attributes,expected_attributes)

    def test_cloudfront_attributes(self):
        expected_attributes = {'aws.resource.id': 'E1SFLUZKKLSP61'}
        cloudfront_processing_rule = processing_rules['aws']['cloudfront']
        attributes = cloudfront_processing_rule.get_attributes_from_s3_key_name(cloudfront_key_name)

        self.assertEqual(attributes,expected_attributes)

    def test_vpcflowlog_attributes(self):
        expected_attributes = {
            'log.source': 'fl-07f38b767c7cd46e3',
            'aws.account.id': '012345678910',
            'aws.region': 'us-east-1'
        }

        vpcflowlogs_processing_rule = processing_rules['aws']['vpcflowlogs']
        attributes = vpcflowlogs_processing_rule.get_attributes_from_s3_key_name(vpcflowlog_key_name)

        self.assertEqual(attributes,expected_attributes)
    
    def test_networkfirewall_attributes(self):
        expected_attributes = {
            'log.type': 'flow',
            'aws.account.id': '012345678910',
            'aws.region': 'us-east-1',
            'aws.resource.id': 'my-test-firewall'
        }

        netfw_processing_rule = processing_rules['aws']['network-firewall']
        attributes = netfw_processing_rule.get_attributes_from_s3_key_name(network_firewall_key_name)

        self.assertEqual(attributes,expected_attributes)
    
    def test_msk_attributes(self):
        expected_attributes = {
            'aws.account.id': '012345678910',
            'aws.region': 'us-east-1',
            'aws.resource.id': 'demo-cluster-2-043b6d76-352c-494a-9eee-fbff5cc1687d-20',
            'aws.msk.broker': 'Broker-1'
        }

        msk_processing_rule = processing_rules['aws']['msk']
        attributes = msk_processing_rule.get_attributes_from_s3_key_name(msk_key_name)
        self.assertEqual(attributes,expected_attributes)
    
    def test_global_accelerator_attributes(self):
        expected_attributes = {
            'aws.account.id': '012345678910',
            'aws.region': 'us-west-2',
            'aws.resource.id': 'f0154cf1-4ac0-451b-87a2-5b2ce89142e6'
        }

        global_accelerator_processing_rule = processing_rules['aws']['global-accelerator']
        attributes = global_accelerator_processing_rule.get_attributes_from_s3_key_name(global_accelerator_key_name)
        self.assertEqual(attributes,expected_attributes)

class TestS3KeyMatchingExpression(unittest.TestCase):

    def test_cloudtrail_s3_key(self):
        self.assertTrue(processing_rules['aws']['CloudTrail'].match_s3_key(cloudtrail_key_name))

    def test_alb_s3_key(self):
        self.assertTrue(processing_rules['aws']['ALB'].match_s3_key(alb_key_name))

    def test_classic_elb_s3_key(self):
        self.assertTrue(processing_rules['aws']['Classic-ELB'].match_s3_key(classic_elb_key_name))

    def test_nlb_s3_key(self):
        self.assertTrue(processing_rules['aws']['NLB'].match_s3_key(nlb_key_name))

    def test_waf_s3_key(self):
        self.assertTrue(processing_rules['aws']['waf'].match_s3_key(waf_key_name))

    def test_cloudfront_s3_key(self):
        self.assertTrue(processing_rules['aws']['cloudfront'].match_s3_key(cloudfront_key_name))

    def test_vpcflowlogs_s3_key(self):
        self.assertTrue(processing_rules['aws']['vpcflowlogs'].match_s3_key(vpcflowlog_key_name))
    
    def test_s3accesslogs_s3_key(self):
        s3_key_name = 'optional-prefix/2022-10-03-10-13-50-A211246203787B7F'
        self.assertTrue(processing_rules['aws']['s3'].match_s3_key(s3_key_name))
    
    def test_vpcdnsquerylogs_s3_key(self):
        vpcdnsquerylog_key_name = 'OptionalPrefix/AWSLogs/012345678910/vpcdnsquerylogs/vpc-0123456789abcdf12/2023/02/15/vpc-0123456789abcdf12_vpcdnsquerylogs_012345678910_20230215T0000Z_213be99c.log.gz'
        self.assertTrue(processing_rules['aws']['vpcdnsquerylogs'].match_s3_key(vpcdnsquerylog_key_name))
    
    def test_network_firewall_s3_key(self):
        self.assertTrue(processing_rules['aws']['network-firewall'].match_s3_key(network_firewall_key_name))
    
    def test_msk_s3_key(self):
        self.assertTrue(processing_rules['aws']['msk'].match_s3_key(msk_key_name))

    def test_global_accelerator_s3_key(self):
        self.assertTrue(processing_rules['aws']['global-accelerator'].match_s3_key(global_accelerator_key_name))

if __name__ == '__main__':
    unittest.main()