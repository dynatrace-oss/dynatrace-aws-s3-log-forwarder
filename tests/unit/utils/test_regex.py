import re
import unittest
import boto3
from utils.helpers import helper_regexes

class TestHelperRegex(unittest.TestCase):

    def test_aws_region(self):
        
        ssm_client = boto3.client('ssm',region_name='us-east-1')

        paginator = ssm_client.get_paginator('get_parameters_by_path')

        page_iterator = paginator.paginate(
            Path='/aws/service/global-infrastructure/regions'
        )

        region_list = []
        for page in page_iterator:
            region_list += page['Parameters']

        all_region_names = []
        matched_region_names = []
        for region in region_list:
            all_region_names.append(region['Value'])
            match = re.fullmatch(helper_regexes['aws_region_pattern'],region['Value'])
            if match:
                matched_region_names.append(region['Value'])

        self.assertListEqual(all_region_names,matched_region_names)