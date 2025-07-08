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
class TestCloudTrailAttributeExtraction(unittest.TestCase):
    cloudtrail_test_entry = {
                               "eventVersion": "1.08",
                               "userIdentity": {
                                   "type": "AssumedRole",
                                   
                                   "principalId": "AROATESTABCDEFGHIJQLM:dynatrace-monitoring-abc31363-CloudTestesintTeamAccount",
                                   "arn": "arn:local:sts::012345678910:assumed-role/test",
                                   "accountId": "012345678910",
                                   "accessKeyId": "ASIAXOQVZPGHSX4D6KG2",
                                   "sessionContext": {
                                       "sessionIssuer": {
                                           "type": "Role",
                                           "principalId": "AROATESTABCDEFGHIJQLM",
                                           "arn": "arn:aws:iam::012345678910:role/Dynatrace_monitoring_role",
                                           "accountId": "012345678910",
                                           "userName": "Dynatrace_monitoring_role"
                                       },
                                       "attributes": {
                                           "creationDate": "2022-09-08T08:26:04Z",
                                           "mfaAuthenticated": "false"
                                       }
                                   }
                               },
                               "eventTime": "2022-09-08T08:26:04Z",
                               "eventSource": "dynamodb.amazonaws.com",
                               "eventName": "ListTables",
                               "awsRegion": "ap-northeast-1",
                               "sourceIPAddress": "54.82.125.21",
                               "userAgent": "aws-sdk-java/1.11.789 Linux/5.11.0-1020-aws OpenJDK_64-Bit_Server_VM/11.0.13+8 java/11.0.13 vendor/Eclipse_Adoptium",
                               "requestParameters": "null",
                               "responseElements": "null",
                               "requestID": "COQOPOROSAEB78FISDHLR9FAHNVV4KQNSO5AEMVJF66Q9ASUAAJG",
                               "eventID": "e2fe1c6f-e5a2-4be3-a93f-fcca72092ada",
                               "readOnly": "true",
                               "eventType": "AwsApiCall",
                               "apiVersion": "2012-08-10",
                               "managementEvent": "true",
                               "recipientAccountId": "012345678910",
                               "eventCategory": "Management",
                               "tlsDetails": {
                                   "clientProvidedHostHeader": "dynamodb.ap-northeast-1.amazonaws.com"
                               }
                            }

    expected_attributes = {
                            "timestamp": cloudtrail_test_entry['eventTime'],
                            "audit.event_source": cloudtrail_test_entry['eventSource'],
                            "audit.action": cloudtrail_test_entry['eventName'],
                            "audit.read_only": cloudtrail_test_entry['readOnly'],
                            "audit.identity_type": cloudtrail_test_entry['userIdentity']['type'],
                            "audit.identity": cloudtrail_test_entry['userIdentity']['arn'],
                            "audit.result": "Succeeded",
                            "severity": 'INFO'                          
                          }

    def test_cloudtrail_attribute_extraction(self):
        cloudtrail_processing_rule = processing_rules['aws']['CloudTrail']

        extracted_attributes = cloudtrail_processing_rule.get_extracted_log_attributes(self.cloudtrail_test_entry)
        self.assertEqual(extracted_attributes,self.expected_attributes)

class TestALBAttributeExtraction(unittest.TestCase):
    alb_test_entry = 'http 2022-09-27T15:28:18.612792Z app/k8s-podinfo-podinfoi-ffbc3dc280/82a34fae168ba1aa 54.25.124.220:63763 192.168.15.219:9898 0.016 0.001 0.000 200 200 134 543 "GET http://k8s-podinfo-podinfoi-ffbc3dc280-1325129400.us-east-1.elb.amazonaws.com:80/ HTTP/1.1" "curl/7.79.1" - - arn:aws:elasticloadbalancing:us-east-1:012345678910:targetgroup/k8s-podinfo-frontend-b634dbe3b4/c0bcccc5dfc7c29c "Root=1-63331692-0dd6b14130c01d3e378a6ea5" "-" "-" 1 2022-09-27T15:28:18.565000Z "forward" "-" "-" "192.168.15.219:9898" "200" "-" "-"'
    expected_attributes = {
                            'request_type': 'http',
                            'timestamp': '2022-09-27T15:28:18.612792Z',
                            'client_ip': '54.25.124.220',
                            'client_port': 63763,
                            'target_ip': '192.168.15.219',
                            'target_port': 9898,
                            'request_processing_time': 0.016,
                            'target_processing_time': 0.001,
                            'response_processing_time': 0.0,
                            'elb_status_code': 200,
                            'target_status_code': 200,
                            'received_bytes': 134,
                            'sent_bytes': 543,
                            'http_method': 'GET',
                            'uriproto': 'http',
                            'urihost': 'k8s-podinfo-podinfoi-ffbc3dc280-1325129400.us-east-1.elb.amazonaws.com:80',
                            'port': '80',
                            'uripath': '/',
                            'http_version': 'HTTP/1.1',
                            'user_agent': 'curl/7.79.1',
                            'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-1:012345678910:targetgroup/k8s-podinfo-frontend-b634dbe3b4/c0bcccc5dfc7c29c',
                            'x_amzn_trace_id': 'Root=1-63331692-0dd6b14130c01d3e378a6ea5',
                            'matched_rule_priority': '1',
                            'request_creation_time': '2022-09-27T15:28:18.565000Z',
                            'actions_executed': 'forward',
                            'target_port_list': '192.168.15.219:9898',
                            'target_status_code_list': '200',
                            'severity': 'INFO',
                            'aws.resource.id': 'app/k8s-podinfo-podinfoi-ffbc3dc280/82a34fae168ba1aa'
                         }
    alb_processing_rule = processing_rules['aws']['ALB']

    def test_alb_attribute_extraction(self):
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(self.alb_test_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)
    
    def test_alb_attribute_extraction_http(self):
        log_entry = 'http 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 192.168.131.39:2817 10.0.0.1:80 0.000 0.001 0.000 200 200 34 366 "GET http://www.example.com:80/ HTTP/1.1" "curl/7.46.0" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337262-36d228ad5d99923122bbe354" "-" "-" 0 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.0.1:80" "200" "-" "-"'
        expected_attributes = { 'request_type': 'http',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '192.168.131.39',
                                'client_port': 2817,
                                'target_ip': '10.0.0.1',
                                'target_port': 80,
                                'request_processing_time': 0.0,
                                'target_processing_time': 0.001,
                                'response_processing_time': 0.0,
                                'elb_status_code': 200,
                                'target_status_code': 200,
                                'received_bytes': 34,
                                'sent_bytes': 366,
                                'http_method': 'GET',
                                'uriproto': 'http',
                                'urihost': 'www.example.com:80',
                                'port': '80',
                                'uripath': '/',
                                'http_version': 'HTTP/1.1',
                                'user_agent': 'curl/7.46.0',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337262-36d228ad5d99923122bbe354',
                                'matched_rule_priority': '0',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'target_port_list': '10.0.0.1:80',
                                'target_status_code_list': '200',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                            }

        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_https(self):
        log_entry = 'https 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 192.168.131.39:2817 10.0.0.1:80 0.086 0.048 0.037 200 200 0 57 "GET https://www.example.com:443/ HTTP/1.1" "curl/7.46.0" ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2 arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337281-1d84f3d73c47ec4e58577259" "www.example.com" "arn:aws:acm:us-east-2:123456789012:certificate/12345678-1234-1234-1234-123456789012" 1 2018-07-02T22:22:48.364000Z "authenticate,forward" "-" "-" "10.0.0.1:80" "200" "-" "-"'
        expected_attributes = { 'request_type': 'https',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '192.168.131.39',
                                'client_port': 2817,
                                'target_ip': '10.0.0.1',
                                'target_port': 80,
                                'request_processing_time': 0.086,
                                'target_processing_time': 0.048,
                                'response_processing_time': 0.037,
                                'elb_status_code': 200,
                                'target_status_code': 200,
                                'received_bytes': 0,
                                'sent_bytes': 57,
                                'http_method': 'GET',
                                'uriproto': 'https',
                                'urihost': 'www.example.com:443',
                                'port': '443',
                                'uripath': '/',
                                'http_version': 'HTTP/1.1',
                                'user_agent': 'curl/7.46.0',
                                'ssl_cipher': 'ECDHE-RSA-AES128-GCM-SHA256',
                                'ssl_protocol': 'TLSv1.2',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337281-1d84f3d73c47ec4e58577259',
                                'domain_name': 'www.example.com',
                                'chosen_cert_arn': 'arn:aws:acm:us-east-2:123456789012:certificate/12345678-1234-1234-1234-123456789012',
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'authenticate,forward',
                                'target_port_list': '10.0.0.1:80',
                                'target_status_code_list': '200',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_http2(self):
        log_entry = 'h2 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.1.252:48160 10.0.0.66:9000 0.000 0.002 0.000 200 200 5 257 "GET https://10.0.2.105:773/ HTTP/2.0" "curl/7.46.0" ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2 arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337327-72bd00b0343d75b906739c42" "-" "-" 1 2018-07-02T22:22:48.364000Z "redirect" "https://example.com:80/" "-" "10.0.0.66:9000" "200" "-" "-"'
        expected_attributes = { 'request_type': 'h2', 
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '10.0.1.252',
                                'client_port': 48160,
                                'target_ip': '10.0.0.66',
                                'target_port': 9000,
                                'request_processing_time': 0.0,
                                'target_processing_time': 0.002,
                                'response_processing_time': 0.0,
                                'elb_status_code': 200,
                                'target_status_code': 200,
                                'received_bytes': 5,
                                'sent_bytes': 257,
                                'http_method': 'GET',
                                'uriproto': 'https',
                                'urihost': '10.0.2.105:773',
                                'port': '773',
                                'uripath': '/',
                                'http_version': 'HTTP/2.0',
                                'user_agent': 'curl/7.46.0',
                                'ssl_cipher': 'ECDHE-RSA-AES128-GCM-SHA256',
                                'ssl_protocol': 'TLSv1.2',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337327-72bd00b0343d75b906739c42',
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'redirect',
                                'redirect_url': 'https://example.com:80/',
                                'target_port_list': '10.0.0.66:9000',
                                'target_status_code_list': '200',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188' }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)
    
    def test_alb_attribute_extraction_ws(self):
        log_entry = 'ws 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.0.140:40914 10.0.1.192:8010 0.001 0.003 0.000 101 101 218 587 "GET http://10.0.0.30:80/ HTTP/1.1" "-" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337364-23a8c76965a2ef7629b185e3" "-" "-" 1 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.1.192:8010" "101" "-" "-"'
        expected_attributes = { 'request_type': 'ws',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '10.0.0.140',
                                'client_port': 40914,
                                'target_ip': '10.0.1.192',
                                'target_port': 8010,
                                'request_processing_time': 0.001,
                                'target_processing_time': 0.003,
                                'response_processing_time': 0.0,
                                'elb_status_code': 101,
                                'target_status_code': 101,
                                'received_bytes': 218,
                                'sent_bytes': 587,
                                'http_method': 'GET',
                                'uriproto': 'http',
                                'urihost': '10.0.0.30:80',
                                'port': '80',
                                'uripath': '/',
                                'http_version': 'HTTP/1.1',
                                'user_agent': '-',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337364-23a8c76965a2ef7629b185e3',
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'target_port_list': '10.0.1.192:8010',
                                'target_status_code_list': '101',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_no_http_method(self):
        log_entry = 'https 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.0.140:40914 10.0.1.192:8010 0.001 0.003 0.000 101 101 218 587 "- http://10.0.0.30:80/ HTTP/1.1" "-" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337364-23a8c76965a2ef7629b185e3" "-" "-" 1 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.1.192:8010" "101" "-" "-"'
        expected_attributes = { 'request_type': 'https',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '10.0.0.140',
                                'client_port': 40914,
                                'target_ip': '10.0.1.192',
                                'target_port': 8010,
                                'request_processing_time': 0.001,
                                'target_processing_time': 0.003,
                                'response_processing_time': 0.0,
                                'elb_status_code': 101,
                                'target_status_code': 101,
                                'received_bytes': 218,
                                'sent_bytes': 587,
                                'http_method': '-',
                                'uriproto': 'http',
                                'urihost': '10.0.0.30:80',
                                'port': '80',
                                'uripath': '/',
                                'http_version': 'HTTP/1.1',
                                'user_agent': '-',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337364-23a8c76965a2ef7629b185e3',
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'target_port_list': '10.0.1.192:8010',
                                'target_status_code_list': '101',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_dash_instead_of_path(self):
        log_entry = 'https 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.0.140:40914 10.0.1.192:8010 0.001 0.003 0.000 101 101 218 587 "- http://10.0.0.30:80- -" "-" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337364-23a8c76965a2ef7629b185e3" "-" "-" 1 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.1.192:8010" "101" "-" "-"'
        expected_attributes = {'request_type': 'https',
                               'timestamp': '2018-07-02T22:23:00.186641Z',
                               'client_ip': '10.0.0.140',
                               'client_port': 40914,
                               'target_ip': '10.0.1.192',
                               'target_port': 8010,
                               'request_processing_time': 0.001,
                               'target_processing_time': 0.003,
                               'response_processing_time': 0.0,
                               'elb_status_code': 101,
                               'target_status_code': 101,
                               'received_bytes': 218,
                               'sent_bytes': 587,
                               'http_method': '-',
                               'uriproto': 'http',
                               'urihost': '10.0.0.30:80',
                               'port': '80',
                               'http_version': '-',
                               'user_agent': '-',
                               'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                               'x_amzn_trace_id': 'Root=1-58337364-23a8c76965a2ef7629b185e3',
                               'matched_rule_priority': '1',
                               'request_creation_time': '2018-07-02T22:22:48.364000Z',
                               'actions_executed': 'forward',
                               'target_port_list': '10.0.1.192:8010',
                               'target_status_code_list': '101',
                               'severity': 'INFO',
                               'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                               }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes, extracted_attributes)

    def alb_attribute_extraction_complicated_uri_param_base_test(self, uriparam):
        log_entry = f'https 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.0.140:40914 10.0.1.192:8010 0.001 0.003 0.000 101 101 218 587 "POST http://10.0.0.30:80/index.php?{uriparam} HTTP/1.1" "-" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337364-23a8c76965a2ef7629b185e3" "-" "-" 1 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.1.192:8010" "101" "-" "-"'
        expected_attributes = { 'request_type': 'https',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'client_ip': '10.0.0.140',
                                'client_port': 40914,
                                'target_ip': '10.0.1.192',
                                'target_port': 8010,
                                'request_processing_time': 0.001,
                                'target_processing_time': 0.003,
                                'response_processing_time': 0.0,
                                'elb_status_code': 101,
                                'target_status_code': 101,
                                'received_bytes': 218,
                                'sent_bytes': 587,
                                'http_method': 'POST',
                                'uriproto': 'http',
                                'urihost': '10.0.0.30:80',
                                'port': '80',
                                'uripath': '/index.php',
                                'uriparam': uriparam,
                                'http_version': 'HTTP/1.1',
                                'user_agent': '-',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337364-23a8c76965a2ef7629b185e3',
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'target_port_list': '10.0.1.192:8010',
                                'target_status_code_list': '101',
                                'severity': 'INFO',
                                'aws.resource.id': 'app/my-loadbalancer/50dc6c495c0c9188'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_function_call_in_uri_param(self):
        self.alb_attribute_extraction_complicated_uri_param_base_test("s=/index/\x5Ca\x5Capp/invokefunction&function=call_user_func_array&vars[0]=md5&vars[1][]=Hello")

    def test_alb_attribute_extraction_code_injection_attack_in_uri_param(self):
        self.alb_attribute_extraction_complicated_uri_param_base_test("lang=../../../../../../../../usr/local/lib/php/applecmd&+config-create+/&/<?echo(md5(\x23hellp\x23));?>+/tmp/index2.php")

    def test_alb_attribute_extraction_sql_injection_in_uri_param(self):
        self.alb_attribute_extraction_complicated_uri_param_base_test("user=-1+union+select+1,2,3,4,5,6,7,8,9,(SELECT+group_concat(table_name)+from+information_schema.tables+where+table_schema=database())")


class TestClassicELBAttributeExtraction(unittest.TestCase):
    classic_elb_test_entry = '2022-09-27T22:48:26.330387Z a2e8277e0e09143fbb06db5dcd2a14c2 3.67.7.163:8596 192.168.18.161:32728 0.000042 0.004504 0.000036 404 404 0 1086 "GET http://a2e8277e0e09143fbb06db5dcd2a14c2-1086714162.us-east-1.elb.amazonaws.com:80/n9BxiYVakde9.php HTTP/1.1" "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)" - -'
    expected_attributes = { "timestamp": "2022-09-27T22:48:26.330387Z",
                            "client_ip": "3.67.7.163",
                            "client_port": 8596,
                            "backend_ip": "192.168.18.161",
                            "backend_port": 32728,
                            "request_processing_time": 4.2e-05,
                            "backend_processing_time": 0.004504,
                            "response_processing_time": 3.6e-05,
                            "elb_status_code": 404,
                            "backend_status_code": 404,
                            "received_bytes": 0,
                            "sent_bytes": 1086,
                            "verb": "GET",
                            "request": "http://a2e8277e0e09143fbb06db5dcd2a14c2-1086714162.us-east-1.elb.amazonaws.com:80/n9BxiYVakde9.php",
                            "proto": "http",
                            "urihost": "a2e8277e0e09143fbb06db5dcd2a14c2-1086714162.us-east-1.elb.amazonaws.com:80",
                            "port": "80",
                            "path": "/n9BxiYVakde9.php",
                            "httpversion": "1.1",
                            "user_agent": "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)",
                            "severity": "WARN",
                            "aws.resource.id": "a2e8277e0e09143fbb06db5dcd2a14c2"
                          }

    classic_elb_processing_rule = processing_rules['aws']['Classic-ELB']

    def test_classic_elb_attribute_extraction(self):
        extracted_attributes = self.classic_elb_processing_rule.get_extracted_log_attributes(self.classic_elb_test_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)


class TestNLBAttributeExtraction(unittest.TestCase):
    nlb_test_entry = 'tls 2.0 2022-09-27T17:10:23 net/k8s-podinfo-frontend-352ef7564b/809b86b470cfa0ff f0f22c45225e4663 192.168.18.161:60808 192.168.103.168:443 24 16 140 518 - arn:aws:acm:us-east-1:012345678910:certificate/ae6e87cd-9848-465b-9433-b0d34850a685 - ECDHE-RSA-AES128-GCM-SHA256 tlsv12 - k8s-podinfo-frontend-352ef7564b-809b86b470cfa0ff.elb.us-east-1.amazonaws.com - - -'
    expected_attributes = { 'listener_type': 'tls',
                            'version': '2.0',
                            'timestamp': '2022-09-27T17:10:23',
                            'listener': 'f0f22c45225e4663',
                            'client_ip': '192.168.18.161',
                            'client_port': '60808',
                            'destination_ip': '192.168.103.168',
                            'destination_port': '443',
                            'connection_time': '24',
                            'tls_handshake_time': '16',
                            'received_bytes': '140',
                            'sent_bytes': '518',
                            'chosen_cert_arn': 'arn:aws:acm:us-east-1:012345678910:certificate/ae6e87cd-9848-465b-9433-b0d34850a685',
                            'tls_cipher': 'ECDHE-RSA-AES128-GCM-SHA256',
                            'tls_protocol_version': 'tlsv12',
                            'domain_name': 'k8s-podinfo-frontend-352ef7564b-809b86b470cfa0ff.elb.us-east-1.amazonaws.com',
                            'aws.resource.id': 'net/k8s-podinfo-frontend-352ef7564b/809b86b470cfa0ff'
                        }
    nlb_processing_rule = processing_rules['aws']['NLB']

    def test_nlb_attribute_extraction(self):
        extracted_attributes = self.nlb_processing_rule.get_extracted_log_attributes(self.nlb_test_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)

class TestS3AccessLogsAttributeExtraction(unittest.TestCase):
    s3_access_log_entry = '79a59df900b949e55d96a1e698fbacedfd6e09d98eacf8f8d5218e7cd47ef2be DOC-EXAMPLE-BUCKET1 [06/Feb/2019:00:00:38 +0000] 192.0.2.3 79a59df900b949e55d96a1e698fbacedfd6e09d98eacf8f8d5218e7cd47ef2be 3E57427F3EXAMPLE REST.GET.VERSIONING - "GET /DOC-EXAMPLE-BUCKET1?versioning HTTP/1.1" 200 - 113 - 7 - "-" "S3Console/0.4" - s9lzHYrFp76ZVxRcpX9+5cjAnEH2ROuNkd2BHfIa6UkFVdtjf5mKR3/eTPFvsiP/XV/VLi31234= SigV4 ECDHE-RSA-AES128-GCM-SHA256 AuthHeader DOC-EXAMPLE-BUCKET1.s3.us-west-1.amazonaws.com TLSV1.2 arn:aws:s3:us-west-1:123456789012:accesspoint/example-AP Yes'

    expected_attributes = {
        'aws.resource.id': 'DOC-EXAMPLE-BUCKET1',
        'timestamp': '2019-02-06T00:00:38+00:00'
    }

    s3_processing_rule = processing_rules['aws']['s3']

    def test_s3_attribute_extraction(self):
        extracted_attributes = self.s3_processing_rule.get_extracted_log_attributes(self.s3_access_log_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)

class TestWAFLogAttributeExtraction(unittest.TestCase):
    waf_log_entry = {"timestamp":1668191404453,"formatVersion":1,"webaclId":"arn:aws:wafv2:us-east-1:012345678910:regional/webacl/my-web-acl/5b291f89-a9c6-496f-bc56-28fe34178f25","terminatingRuleId":"Default_Action","terminatingRuleType":"REGULAR","action":"ALLOW","terminatingRuleMatchDetails":[],"httpSourceName":"ALB","httpSourceId":"012345678910-app/my-lb/083081a32688b957","ruleGroupList":[{"ruleGroupId":"AWS#AWSManagedRulesKnownBadInputsRuleSet","terminatingRule":None,"nonTerminatingMatchingRules":[],"excludedRules":None,"customerConfig":None},{"ruleGroupId":"AWS#AWSManagedRulesLinuxRuleSet","terminatingRule":None,"nonTerminatingMatchingRules":[],"excludedRules":None,"customerConfig":None},{"ruleGroupId":"AWS#AWSManagedRulesPHPRuleSet","terminatingRule":None,"nonTerminatingMatchingRules":[],"excludedRules":None,"customerConfig":None},{"ruleGroupId":"AWS#AWSManagedRulesSQLiRuleSet","terminatingRule":None,"nonTerminatingMatchingRules":[],"excludedRules":None,"customerConfig":None}],"rateBasedRuleList":[],"nonTerminatingMatchingRules":[],"requestHeadersInserted":None,"responseCodeSent":None,"httpRequest":{"clientIp":"1.2.3.4","country":"ES","headers":[{"name":"Host","value":"my-lb-123456.us-east-1.elb.amazonaws.com"},{"name":"User-Agent","value":"curl/7.79.1"},{"name":"Accept","value":"*/*"}],"uri":"/index.php","args":"","httpVersion":"HTTP/1.1","httpMethod":"GET","requestId":"1-636e94ac-0955431c62e36012512d103e"}}

    expected_attributes = {
        "aws.arn": 'arn:aws:wafv2:us-east-1:012345678910:regional/webacl/my-web-acl/5b291f89-a9c6-496f-bc56-28fe34178f25',
        "audit.action": 'ALLOW',
        "timestamp": 1668191404453
    }

    waf_processing_rule = processing_rules['aws']['waf']

    def test_waf_attribute_extraction(self):
        extracted_attributes = self.waf_processing_rule.get_extracted_log_attributes(self.waf_log_entry)
        self.assertEqual(extracted_attributes, self.expected_attributes)

class TestVPCDNSquerylogs(unittest.TestCase):
    log_entry = {
          "version": "1.100000",
          "account_id": "012345678910",
          "region": "us-east-1",
          "vpc_id": "vpc-0123456789abcdef12",
          "query_timestamp": "2023-02-15T18:33:54Z",
          "query_name": "ec2messages.us-east-1.amazonaws.com.",
          "query_type": "A",
          "query_class": "IN",
          "rcode": "NOERROR",
          "answers": [
            {
              "Rdata": "5.6.7.8",
              "Type": "A",
              "Class": "IN"
            }
          ],
          "srcaddr": "1.2.3.4",
          "srcport": "38900",
          "transport": "UDP",
          "srcids": {
            "instance": "i-0db59e1c912332372"
          }
        }

    expected_attributes = {
        "timestamp": '2023-02-15T18:33:54Z',
        "aws.account.id": "012345678910",
        "aws.region": "us-east-1",
        "aws.resource.id": "vpc-0123456789abcdef12",
        #"net.host.name": "ec2messages.us-east-1.amazonaws.com.",
        "severity": "INFO"
    }

    vpcdnsquery_processing_rule = processing_rules['aws']['vpcdnsquerylogs']

    def test_vpcdnsquerylogs_attribute_extraction(self):
        extracted_attributes = self.vpcdnsquery_processing_rule.get_extracted_log_attributes(self.log_entry)
        self.assertEqual(extracted_attributes, self.expected_attributes)

class testCloudFrontLogs(unittest.TestCase):
    log_entry = '2023-02-16	14:11:45	HEL50-C2	926	213.27.198.18	GET	d2p3hufu2xzzmv.cloudfront.net	/	200	-	curl/7.79.1	-	-	Hit	4hywY-pj7l9Wpc1WaHT2rUoyuuxTe_GT7aY2CkbFxOhYrC_qbqRTtQ==	d2p3hufu2xzzmv.cloudfront.net	https	51	0.026	-	TLSv1.3	TLS_AES_128_GCM_SHA256	Hit	HTTP/2.0	-	-	9428	0.026	Hit	text/html	615	-	-'

    expected_attributes = {
        'timestamp': '2023-02-16T14:11:45'
    }

    cloudfront_processing_rule = processing_rules['aws']['cloudfront']

    def test_cloudfrontlogs_attribute_extraction(self):
        extracted_attributes = self.cloudfront_processing_rule.get_extracted_log_attributes(self.log_entry)
        self.assertEqual(extracted_attributes, self.expected_attributes)

class testMSKLogs(unittest.TestCase):
    log_entry = '[2023-02-20 17:10:36,845] INFO App info kafka.consumer for consumer-consumer-lag-19 unregistered (org.apache.kafka.common.utils.AppInfoParser)'

    expected_attributes = {
        'timestamp': '2023-02-20T17:10:36.845000',
        'severity': 'INFO'
    }

    msk_processing_rule = processing_rules['aws']['msk']

    def test_msk_logs(self):
        extracted_attributes = self.msk_processing_rule.get_extracted_log_attributes(self.log_entry)
        self.assertEqual(extracted_attributes,self.expected_attributes)

class testGlobalAcceleratorLogs(unittest.TestCase):
    log_entry = '2.0 012345678910 f0154cf1-4ac0-451b-87a2-5b2ce89142e6 1.2.3.4 57825 5.6.7.8 80 172.31.25.4 80 TCP IPV4 0 0 1676984801 1676984809 ACCEPT OK - 0 us-east-1 JFK6-2 INGRESS vpc-01234567891abcdef'

    expected_attributes = {
        'timestamp': '1676984801'
    }

    global_accelerator_processing_rule = processing_rules['aws']['global-accelerator']

    def test_global_accelerator_logs(self):
        extracted_attributes = self.global_accelerator_processing_rule.get_extracted_log_attributes(self.log_entry)
        self.assertEqual(extracted_attributes,self.expected_attributes)

class testVpcFlowLogs(unittest.TestCase):
    log_entry = '2 012345678910 eni-02454058ae64a0b4e 172.31.6.100 67.220.242.48 59308 443 6 15 5338 1677665646 1677665674 ACCEPT OK'

    expected_attributes = {
        'timestamp': '1677665646'
    }

    vpc_flow_logs_processing_rule = processing_rules['aws']['vpcflowlogs']

    def test_vpc_flow_logs(self):
        extracted_attributes = self.vpc_flow_logs_processing_rule.get_extracted_log_attributes(self.log_entry)
        self.assertEqual(extracted_attributes,self.expected_attributes)

class testCWLtoFirehoseLogs(unittest.TestCase):

    def test_route53_public_query_logs(self):
        log_entry = {
            'content': '1.0 2023-02-21T16:34:06Z Z0195849T189REVYAU10 test.ivallho.com A NOERROR UDP MAD51-C2 79.157.104.114 -',
            'aws.log_group': '/aws/route53/public/example.com',
            'aws.log_stream': 'Z0195849T189REVYAU10/MAD51-C2',
            'aws.log_event_id': '37398288281683578257046633068901495458990097452373442560',
            'timestamp': '2023-02-21T16:34:06Z'
        }
        expected_attributes = {
            'timestamp':'2023-02-21T16:34:06Z',
            'aws.service': 'route53',
            'aws.resource.id': 'Z0195849T189REVYAU10',
            'aws.edge_location': 'MAD51-C2'
        }

        extracted_attributes = processing_rules['custom']['cwl_to_fh'].get_extracted_log_attributes(log_entry)
        self.assertEqual(extracted_attributes,expected_attributes)

    def test_eks_control_plane_logs(self):

        log_entry = {
            'content': 'I0221 18:41:59.098346      10 cleaner.go:172] Cleaning CSR "csr-lrn9z" as it is more than 1h0m0s old and approved.',
            'aws.log_group': '/aws/eks/my-cluster-name/cluster',
            'aws.log_stream': 'kube-controller-manager-1e770729c82dc68998d47f9f28408516',
            'aws.log_event_id': '37398288281683578257046633068901495458990097452373442560',
            'timestamp': '2023-02-21T16:34:06Z'
        }

        expected_attributes = {
            'timestamp':'2023-02-21T16:34:06Z',
            'aws.service': 'eks',
            'aws.resource.id': 'my-cluster-name',
            'log.source': 'kube-controller-manager'
        }

        extracted_attributes = processing_rules['custom']['cwl_to_fh'].get_extracted_log_attributes(log_entry)
        self.assertEqual(extracted_attributes,expected_attributes)

class testAppFabricLogs(unittest.TestCase):

    def test_appfabric_logs(self):
        log_entry = {
          "activity_id": 99,
          "activity_name": "Update",
          "actor": {
            "user": {
              "email_addr": "akua_mansa@example.com",
              "name": "fabric test",
              "type": "User",
              "type_id": 1,
              "uid": "12817214158477"
            }
          },
          "category_name": "Identity & Access Management",
          "category_uid": 3,
          "class_name": "Account Change",
          "class_uid": 3001,
          "device": {
            "ip": "52.91.153.203",
            "type": "Unknown",
            "type_id": 0
          },
          "http_request": {},
          "message": "Started 30-day deletion",
          "metadata": {
            "event_code": "user_update",
            "log_provider": "AWS AppFabric",
            "log_version": "2023-06-27",
            "product": {
              "name": "Zendesk",
              "uid": "zendesk",
              "vendor_name": "Zendesk"
            },
            "profiles": [
              "host"
            ],
            "uid": "17297609041293",
            "version": "v1.0.0-rc.3"
          },
          "raw_data": "{\"url\":\"https://fabric5385.zendesk.com/api/v2/audit_logs/17297609041293.json\",\"id\":17297609041293,\"action_label\":\"Updated\",\"actor_id\":12817214158477,\"source_id\":17297601029773,\"source_type\":\"user\",\"source_label\":\"Customer: 5683 charlie\",\"action\":\"update\",\"change_description\":\"Started 30-day deletion\",\"ip_address\":\"52.91.153.203\",\"created_at\":\"2023-07-04T00:13:19Z\",\"actor_name\":\"fabric test\"}",
          "severity_id": 0,
          "status": "Success",
          "status_id": 1,
          "time": 1688429599000,
          "type_name": "Account Change: Update",
          "type_uid": 300199,
          "user": {
            "name": "Customer: 5683 charlie",
            "type": "User",
            "type_id": 1,
            "uid": "17297601029773"
          }
        }
        expected_attributes = {
            "timestamp": 1688429599000,
            "log.source": "zendesk",
            "audit.identity": "akua_mansa@example.com",
            "audit.action": "Account Change: Update"
        }

        extracted_attributes = processing_rules['aws']['appfabric-ocsf-json'].get_extracted_log_attributes(log_entry)
        self.assertEqual(extracted_attributes,expected_attributes)

if __name__ == '__main__':
    unittest.main()

    