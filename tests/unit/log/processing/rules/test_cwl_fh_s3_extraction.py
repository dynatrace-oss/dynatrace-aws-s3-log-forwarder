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


class TestAttributeExtractionCWLFireHoseS3(unittest.TestCase):

    def test_lambda_logs(self):

        log_entry = {"aws.account.id": "012345678910", "aws.log_group": "/aws/lambda/hello-world-123",
                     "aws.log_stream": "2023/02/14/[$LATEST]6c9e8a41d018497aa1f38fe84092c97b",
                     "id": "37385399698484814707871715858877515407325547836143501312",
                     "timestamp": 1676419301941, "message": "Hello World!"}

        expected_attributes = {
            "timestamp": 1676419301941,
            "content": "Hello World!",
            "aws.log_event_id": "37385399698484814707871715858877515407325547836143501312",
            "aws.service": "lambda",
            "aws.resource.id": "hello-world-123"
        }

        rule = processing_rules['custom']['cwl_to_fh']

        extracted_attributes = rule.get_extracted_log_attributes(log_entry)

        self.assertEqual(expected_attributes, extracted_attributes)

    def test_eks_logs(self):

        log_entry = {"aws.account.id": "012345678910", "aws.log_group": "/aws/eks/my_cluster/cluster",
                    "aws.log_stream": "placeholder",
                    "id": "37385399698484814707871715858877515407325547836143501312",
                    "timestamp": 1676419301941, "message": "Hello World!"}

        expected_attributes = {
            "timestamp": 1676419301941,
            "content": "Hello World!",
            "aws.log_event_id": "37385399698484814707871715858877515407325547836143501312",
            "aws.service": "eks",
            "aws.resource.id": "my_cluster",
            "log.source": "placeholder"
        }

        rule = processing_rules['custom']['cwl_to_fh']

        for i in ["kube-apiserver", "kube-apiserver-audit", "authenticator",
                    "kube-controller-manager", "kube-scheduler"]:

            log_entry['aws.log_stream'] = i + \
                "-1234567890abcdef01234567890abcde"

            expected_attributes['log.source'] = i
            extracted_attributes = rule.get_extracted_log_attributes(log_entry)

            self.assertEqual(extracted_attributes, expected_attributes)
