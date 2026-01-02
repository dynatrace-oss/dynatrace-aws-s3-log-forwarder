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
import sys
import json
import gzip
import io
from unittest.mock import MagicMock, Mock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../src'))

from log.processing.processing import process_log_object
from log.processing.log_processing_rule import LogProcessingRule

os.environ['LOG_FORWARDER_CONFIGURATION_LOCATION'] = 'local'
os.environ['DEPLOYMENT_NAME'] = 'test'
os.environ['FORWARDER_FUNCTION_ARN'] = 'arn:aws:lambda:us-east-1:123456789012:function:test'

class TestProcessLogObject(unittest.TestCase):
    """Test process_log_object function with various JSON formats"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_lambda_context = Mock()
        self.mock_lambda_context.get_remaining_time_in_millis.return_value = 300000

        self.mock_log_sink = Mock()
        self.mock_log_sink.push = Mock()
        self.mock_log_sink.set_s3_source = Mock()

    def _create_s3_response(self, content, compressed=False, content_encoding=''):
        """Helper to create mock S3 response"""
        if compressed:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode='wb') as gz:
                gz.write(content.encode('utf-8') if isinstance(content, str) else content)
            body = io.BytesIO(buffer.getvalue())
        else:
            body = io.BytesIO(content.encode('utf-8') if isinstance(content, str) else content)

        return {
            'Body': body,
            'ContentLength': len(content),
            'ContentEncoding': content_encoding
        }

    @patch('boto3._get_default_session')
    def test_json_array_processing(self, mock_session):
        """Test processing a JSON array"""
        # Create test data - simple JSON array
        test_data = json.dumps([
            {"id": 1, "message": "First log entry"},
            {"id": 2, "message": "Second log entry"},
            {"id": 3, "message": "Third log entry"}
        ])

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule for JSON format
        log_rule = LogProcessingRule(
            name='test_json_array',
            source='test-source',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='test-key.json',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 3)
        self.assertEqual(self.mock_log_sink.push.call_count, 3)

    @patch('boto3._get_default_session')
    def test_json_with_nested_path(self, mock_session):
        """Test processing JSON with nested path"""
        # Create test data with nested structure
        test_data = json.dumps({
            "Records": [
                {"eventId": "1", "eventName": "CreateTable"},
                {"eventId": "2", "eventName": "DeleteTable"}
            ]
        })

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule for JSON with path
        log_rule = LogProcessingRule(
            name='test_cloudtrail',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key='Records',
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='cloudtrail.json',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 2)
        self.assertEqual(self.mock_log_sink.push.call_count, 2)

    @patch('boto3._get_default_session')
    def test_json_stream_processing(self, mock_session):
        """Test processing JSON stream (multiple root objects)"""
        # Create test data - multiple JSON objects (newline delimited)
        test_data = '''{"id": 1, "level": "INFO", "message": "First event"}
{"id": 2, "level": "WARN", "message": "Second event"}
{"id": 3, "level": "ERROR", "message": "Third event"}'''

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule for JSON stream
        log_rule = LogProcessingRule(
            name='test_json_stream',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json_stream',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='stream.jsonl',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 3)
        self.assertEqual(self.mock_log_sink.push.call_count, 3)

    @patch('boto3._get_default_session')
    def test_gzipped_json_processing(self, mock_session):
        """Test processing gzipped JSON file"""
        # Create test data
        test_data = json.dumps([
            {"timestamp": "2024-01-01T00:00:00Z", "message": "Log 1"},
            {"timestamp": "2024-01-01T00:00:01Z", "message": "Log 2"}
        ])

        # Mock S3 client with gzipped data
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data, compressed=True)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule
        log_rule = LogProcessingRule(
            name='test_gzipped',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='logs.json.gz',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 2)
        self.assertEqual(self.mock_log_sink.push.call_count, 2)

    @patch('boto3._get_default_session')
    def test_empty_json_array(self, mock_session):
        """Test processing empty JSON array"""
        test_data = json.dumps([])

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule
        log_rule = LogProcessingRule(
            name='test_empty',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='empty.json',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 0)
        self.assertEqual(self.mock_log_sink.push.call_count, 0)

    @patch('boto3._get_default_session')
    def test_deeply_nested_json_path(self, mock_session):
        """Test processing JSON with deeply nested path"""
        test_data = json.dumps({
            "data": {
                "logs": {
                    "events": [
                        {"id": 1, "text": "Event 1"},
                        {"id": 2, "text": "Event 2"}
                    ]
                }
            }
        })

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule with nested path
        log_rule = LogProcessingRule(
            name='test_nested',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key='data.logs.events',
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='nested.json',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 2)
        self.assertEqual(self.mock_log_sink.push.call_count, 2)

    @patch('boto3._get_default_session')
    def test_json_with_context_attributes(self, mock_session):
        """Test that context attributes are properly added to log entries"""
        test_data = json.dumps([{"message": "test"}])

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule
        log_rule = LogProcessingRule(
            name='test_attributes',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        process_log_object(
            log_processing_rule=log_rule,
            bucket='my-test-bucket',
            key='logs/2024/01/01/test.json',
            bucket_region='us-west-2',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify context attributes were added
        call_args = self.mock_log_sink.push.call_args[0][0]
        self.assertIn('log.source.aws.s3.bucket.name', call_args)
        self.assertEqual(call_args['log.source.aws.s3.bucket.name'], 'my-test-bucket')
        self.assertIn('log.source.aws.s3.key.name', call_args)
        self.assertEqual(call_args['log.source.aws.s3.key.name'], 'logs/2024/01/01/test.json')
        self.assertIn('cloud.log_forwarder', call_args)

    @patch('boto3._get_default_session')
    def test_large_json_array(self, mock_session):
        """Test processing large JSON array to ensure streaming works"""
        # Create large test data (1000 entries)
        test_data = json.dumps([{"id": i, "data": f"Entry {i}"} for i in range(1000)])

        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.get_object.return_value = self._create_s3_response(test_data)
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_s3_client
        mock_session.return_value = mock_session_instance

        # Create log processing rule
        log_rule = LogProcessingRule(
            name='test_large',
            source='s3',
            known_key_path_pattern='.*',
            log_format='json',
            log_entries_key=None,
            annotations={},
            attribute_extraction_jmespath_expression={}
        )

        # Process the log
        result = process_log_object(
            log_processing_rule=log_rule,
            bucket='test-bucket',
            key='large.json',
            bucket_region='us-east-1',
            log_sinks=[self.mock_log_sink],
            lambda_context=self.mock_lambda_context
        )

        # Verify results
        self.assertEqual(result, 1000)
        self.assertEqual(self.mock_log_sink.push.call_count, 1000)


if __name__ == '__main__':
    unittest.main()
