import unittest
from log.processing import log_processing_rules
from log.processing import processing

processing_rules = log_processing_rules.load()

cloudtrail_key_name = 'AWSLogs/012345678910/CloudTrail/us-east-1/2022/09/23/012345678910_CloudTrail_us-east-1_20220923T2350Z_noxkMtWv70h0LEES.json.gz'
alb_key_name = 'AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_app.k8s-podinfo-podinfoi-ffbc3dc280.82a34fae168ba1aa_20220721T1440Z_192.168.122.18_3okvlwdx.log.gz'
classic_elb_key_name = 'AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_a2e8277e0e09143fbb06db5dcd2a14c2_20220730T2350Z_192.168.36.65_31av101p.log'
nlb_key_name = 'AWSLogs/012345678910/elasticloadbalancing/us-east-1/2022/09/23/012345678910_elasticloadbalancing_us-east-1_net.k8s-podinfo-frontend-352ef7564b.809b86b470cfa0ff_20220927T1715Z_bbb0861d.log.gz'


expected_attributes = {
                        'aws.account.id': '012345678910',
                        'aws.region': 'us-east-1'
                      }

class TestAWSAttributeInjection(unittest.TestCase):
    def test_cloudtrail_attributes(self):
        cloudtrail_processing_rule = processing_rules['aws']['CloudTrail']
        attributes = cloudtrail_processing_rule.get_attributes_from_s3_key_name(cloudtrail_key_name)
        self.assertEqual(attributes,expected_attributes)

    def test_alb_attributes(self):
        alb_processing_rule = processing_rules['aws']['ALB']
        attributes = alb_processing_rule.get_attributes_from_s3_key_name(alb_key_name)
        self.assertEqual(attributes,expected_attributes)
    
    def test_classic_attributes(self):
        classic_elb_processing_rule = processing_rules['aws']['Classic-ELB']
        attributes = classic_elb_processing_rule.get_attributes_from_s3_key_name(classic_elb_key_name)
        self.assertEqual(attributes,expected_attributes)

    def test_nlb_attributes(self):
        nlb_processing_rule = processing_rules['aws']['NLB']
        attributes = nlb_processing_rule.get_attributes_from_s3_key_name(nlb_key_name)
        self.assertEqual(attributes,expected_attributes)


if __name__ == '__main__':
    unittest.main()