import unittest
from log.processing import log_processing_rules

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
                            'elbv2_id': 'app/k8s-podinfo-podinfoi-ffbc3dc280/82a34fae168ba1aa',
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
                            'uriparam': None,
                            'http_version': 'HTTP/1.1',
                            'user_agent': 'curl/7.79.1',
                            'ssl_cipher': None,
                            'ssl_protocol': None,
                            'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-1:012345678910:targetgroup/k8s-podinfo-frontend-b634dbe3b4/c0bcccc5dfc7c29c',
                            'x_amzn_trace_id': 'Root=1-63331692-0dd6b14130c01d3e378a6ea5',
                            'domain_name': None,
                            'chosen_cert_arn': None,
                            'matched_rule_priority': '1',
                            'request_creation_time': '2022-09-27T15:28:18.565000Z',
                            'actions_executed': 'forward',
                            'redirect_url': None,
                            'error_reason': None,
                            'target_port_list': '192.168.15.219:9898',
                            'target_status_code_list': '200',
                            'classification': None,
                            'classification_reason': None,
                            'severity': 'INFO'
                         }
    alb_processing_rule = processing_rules['aws']['ALB']

    def test_alb_attribute_extraction(self):
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(self.alb_test_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)
    
    def test_alb_attribute_extraction_http(self):
        log_entry = 'http 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 192.168.131.39:2817 10.0.0.1:80 0.000 0.001 0.000 200 200 34 366 "GET http://www.example.com:80/ HTTP/1.1" "curl/7.46.0" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337262-36d228ad5d99923122bbe354" "-" "-" 0 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.0.1:80" "200" "-" "-"'
        expected_attributes = { 'request_type': 'http',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'elbv2_id': 'app/my-loadbalancer/50dc6c495c0c9188',
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
                                'uriparam': None,
                                'http_version': 'HTTP/1.1',
                                'user_agent': 'curl/7.46.0',
                                'ssl_cipher': None,
                                'ssl_protocol': None,
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337262-36d228ad5d99923122bbe354',
                                'domain_name': None,
                                'chosen_cert_arn': None,
                                'matched_rule_priority': '0',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'redirect_url': None,
                                'error_reason': None,
                                'target_port_list': '10.0.0.1:80',
                                'target_status_code_list': '200',
                                'classification': None,
                                'classification_reason': None,
                                'severity': 'INFO'
                            }

        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_https(self):
        log_entry = 'https 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 192.168.131.39:2817 10.0.0.1:80 0.086 0.048 0.037 200 200 0 57 "GET https://www.example.com:443/ HTTP/1.1" "curl/7.46.0" ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2 arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337281-1d84f3d73c47ec4e58577259" "www.example.com" "arn:aws:acm:us-east-2:123456789012:certificate/12345678-1234-1234-1234-123456789012" 1 2018-07-02T22:22:48.364000Z "authenticate,forward" "-" "-" "10.0.0.1:80" "200" "-" "-"'
        expected_attributes = { 'request_type': 'https',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'elbv2_id': 'app/my-loadbalancer/50dc6c495c0c9188',
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
                                'uriparam': None,
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
                                'redirect_url': None,
                                'error_reason': None,
                                'target_port_list': '10.0.0.1:80',
                                'target_status_code_list': '200',
                                'classification': None,
                                'classification_reason': None,
                                'severity': 'INFO'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

    def test_alb_attribute_extraction_http2(self):
        log_entry = 'h2 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.1.252:48160 10.0.0.66:9000 0.000 0.002 0.000 200 200 5 257 "GET https://10.0.2.105:773/ HTTP/2.0" "curl/7.46.0" ECDHE-RSA-AES128-GCM-SHA256 TLSv1.2 arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337327-72bd00b0343d75b906739c42" "-" "-" 1 2018-07-02T22:22:48.364000Z "redirect" "https://example.com:80/" "-" "10.0.0.66:9000" "200" "-" "-"'
        expected_attributes = { 'request_type': 'h2', 
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'elbv2_id': 'app/my-loadbalancer/50dc6c495c0c9188',
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
                                'uriparam': None,
                                'http_version': 'HTTP/2.0',
                                'user_agent': 'curl/7.46.0',
                                'ssl_cipher': 'ECDHE-RSA-AES128-GCM-SHA256',
                                'ssl_protocol': 'TLSv1.2',
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337327-72bd00b0343d75b906739c42',
                                'domain_name': None,
                                'chosen_cert_arn': None,
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'redirect',
                                'redirect_url': 'https://example.com:80/',
                                'error_reason': None,
                                'target_port_list': '10.0.0.66:9000',
                                'target_status_code_list': '200',
                                'classification': None,
                                'classification_reason': None,
                                'severity': 'INFO' }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)
    
    def test_alb_attribute_extraction_ws(self):
        log_entry = 'ws 2018-07-02T22:23:00.186641Z app/my-loadbalancer/50dc6c495c0c9188 10.0.0.140:40914 10.0.1.192:8010 0.001 0.003 0.000 101 101 218 587 "GET http://10.0.0.30:80/ HTTP/1.1" "-" - - arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067 "Root=1-58337364-23a8c76965a2ef7629b185e3" "-" "-" 1 2018-07-02T22:22:48.364000Z "forward" "-" "-" "10.0.1.192:8010" "101" "-" "-"'
        expected_attributes = { 'request_type': 'ws',
                                'timestamp': '2018-07-02T22:23:00.186641Z',
                                'elbv2_id': 'app/my-loadbalancer/50dc6c495c0c9188',
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
                                'uriparam': None,
                                'http_version': 'HTTP/1.1',
                                'user_agent': '-',
                                'ssl_cipher': None,
                                'ssl_protocol': None,
                                'target_group_arn': 'arn:aws:elasticloadbalancing:us-east-2:123456789012:targetgroup/my-targets/73e2d6bc24d8a067',
                                'x_amzn_trace_id': 'Root=1-58337364-23a8c76965a2ef7629b185e3',
                                'domain_name': None,
                                'chosen_cert_arn': None,
                                'matched_rule_priority': '1',
                                'request_creation_time': '2018-07-02T22:22:48.364000Z',
                                'actions_executed': 'forward',
                                'redirect_url': None,
                                'error_reason': None,
                                'target_port_list': '10.0.1.192:8010',
                                'target_status_code_list': '101',
                                'classification': None,
                                'classification_reason': None,
                                'severity': 'INFO'
                            }
        extracted_attributes = self.alb_processing_rule.get_extracted_log_attributes(log_entry)
        self.assertEqual(expected_attributes,extracted_attributes)

class TestClassicELBAttributeExtraction(unittest.TestCase):
    classic_elb_test_entry = '2022-09-27T22:48:26.330387Z a2e8277e0e09143fbb06db5dcd2a14c2 3.67.7.163:8596 192.168.18.161:32728 0.000042 0.004504 0.000036 404 404 0 1086 "GET http://a2e8277e0e09143fbb06db5dcd2a14c2-1086714162.us-east-1.elb.amazonaws.com:80/n9BxiYVakde9.php HTTP/1.1" "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)" - -'
    expected_attributes = { "timestamp": "2022-09-27T22:48:26.330387Z",
                            "elb": "a2e8277e0e09143fbb06db5dcd2a14c2",
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
                            "params": None,
                            "httpversion": "1.1",
                            "rawrequest": None,
                            "user_agent": "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)",
                            "ssl_cipher": None,
                            "ssl_protocol": None,
                            "severity": "WARN"
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
                            'elb_id': 'net/k8s-podinfo-frontend-352ef7564b/809b86b470cfa0ff',
                            'listener': 'f0f22c45225e4663',
                            'client_ip': '192.168.18.161',
                            'client_port': '60808',
                            'destination_ip': '192.168.103.168',
                            'destination_port': '443',
                            'connection_time': '24',
                            'tls_handshake_time': '16',
                            'received_bytes': '140',
                            'sent_bytes': '518',
                            'incoming_tls_alert': None,
                            'chosen_cert_arn': 'arn:aws:acm:us-east-1:012345678910:certificate/ae6e87cd-9848-465b-9433-b0d34850a685',
                            'chosen_cert_serial': None,
                            'tls_cipher': 'ECDHE-RSA-AES128-GCM-SHA256',
                            'tls_protocol_version': 'tlsv12',
                            'tls_named_group': None,
                            'domain_name': 'k8s-podinfo-frontend-352ef7564b-809b86b470cfa0ff.elb.us-east-1.amazonaws.com',
                            'alpn_fe_protocol': None,
                            'alpn_be_protocol': None,
                            'alpn_client_preference_list': None
                        }
    nlb_processing_rule = processing_rules['aws']['NLB']

    def test_nlb_attribute_extraction(self):
        extracted_attributes = self.nlb_processing_rule.get_extracted_log_attributes(self.nlb_test_entry)
        self.assertEqual(self.expected_attributes,extracted_attributes)

if __name__ == '__main__':
    unittest.main()