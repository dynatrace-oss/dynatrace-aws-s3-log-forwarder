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

import json
import unittest

from log.s3_notification import (
    S3Notification,
    UnsupportedNotificationTypeError,
    parse_sqs_message_body,
    _detect_notification_type,
)


class TestDetectNotificationType(unittest.TestCase):
    def test_detect_eventbridge(self):
        notification = {
            "version": "0",
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {"bucket": {"name": "b"}, "object": {"key": "k"}}
        }
        self.assertEqual(_detect_notification_type(notification), 'eventbridge')

    def test_detect_sns(self):
        notification = {
            "Type": "Notification",
            "MessageId": "abc",
            "Message": "{}"
        }
        self.assertEqual(_detect_notification_type(notification), 'sns')

    def test_detect_s3_direct(self):
        notification = {
            "Records": [{
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {"bucket": {"name": "b"}, "object": {"key": "k"}}
            }]
        }
        self.assertEqual(_detect_notification_type(notification), 's3')

    def test_detect_legacy_eventbridge(self):
        notification = {
            "region": "us-east-1",
            "detail": {"bucket": {"name": "b"}, "object": {"key": "k"}, "requester": "test"}
        }
        self.assertEqual(_detect_notification_type(notification), 'eventbridge')

    def test_detect_unknown(self):
        notification = {"foo": "bar"}
        self.assertEqual(_detect_notification_type(notification), 'unknown')


class TestParseEventBridgeNotification(unittest.TestCase):
    def _make_eventbridge_body(self, bucket='my-bucket', key='path/to/object.log', region='us-east-1', requester='cloudtrail.amazonaws.com'):
        return json.dumps({
            "version": "0",
            "id": "test-id",
            "detail-type": "Object Created",
            "source": "aws.s3",
            "account": "012345678910",
            "time": "2022-07-12T16:29:18Z",
            "region": region,
            "resources": [f"arn:aws:s3:::{bucket}"],
            "detail": {
                "version": "0",
                "bucket": {"name": bucket},
                "object": {"key": key, "size": 950, "etag": "abc", "sequencer": "123"},
                "request-id": "REQ1",
                "requester": requester,
                "source-ip-address": "1.2.3.4",
                "reason": "PutObject"
            }
        })

    def test_parse_eventbridge_notification(self):
        body = self._make_eventbridge_body()
        result = parse_sqs_message_body(body)

        self.assertEqual(len(result), 1)
        n = result[0]
        self.assertIsInstance(n, S3Notification)
        self.assertEqual(n.bucket_name, 'my-bucket')
        self.assertEqual(n.key_name, 'path/to/object.log')
        self.assertEqual(n.region, 'us-east-1')
        self.assertEqual(n.requester, 'cloudtrail.amazonaws.com')
        self.assertEqual(n.source_type, 'eventbridge')

    def test_parse_eventbridge_preserves_region(self):
        body = self._make_eventbridge_body(region='eu-west-1')
        result = parse_sqs_message_body(body)
        self.assertEqual(result[0].region, 'eu-west-1')

    def test_parse_legacy_eventbridge_without_source_field(self):
        body = json.dumps({
            "region": "us-east-1",
            "detail": {
                "bucket": {"name": "legacy-bucket"},
                "object": {"key": "legacy/key.log"},
                "requester": "cloudtrail.amazonaws.com"
            }
        })
        result = parse_sqs_message_body(body)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].bucket_name, 'legacy-bucket')
        self.assertEqual(result[0].key_name, 'legacy/key.log')
        self.assertEqual(result[0].source_type, 'eventbridge')


class TestParseSnsNotification(unittest.TestCase):
    def _make_s3_event(self, bucket='my-bucket', key='path/to/object.log',
                       region='us-east-1', principal='AWS:AIDA1234', event_name='ObjectCreated:Put'):
        return {
            "Records": [{
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": region,
                "eventTime": "2022-07-12T16:29:18Z",
                "eventName": event_name,
                "userIdentity": {"principalId": principal},
                "requestParameters": {"sourceIPAddress": "1.2.3.4"},
                "responseElements": {},
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "config-1",
                    "bucket": {
                        "name": bucket,
                        "ownerIdentity": {"principalId": "EXAMPLE"},
                        "arn": f"arn:aws:s3:::{bucket}"
                    },
                    "object": {
                        "key": key,
                        "size": 950,
                        "eTag": "abc",
                        "sequencer": "123"
                    }
                }
            }]
        }

    def _make_sns_body(self, s3_event=None, **kwargs):
        if s3_event is None:
            s3_event = self._make_s3_event(**kwargs)
        return json.dumps({
            "Type": "Notification",
            "MessageId": "sns-msg-id",
            "TopicArn": "arn:aws:sns:us-east-1:012345678910:s3-events",
            "Subject": "Amazon S3 Notification",
            "Message": json.dumps(s3_event),
            "Timestamp": "2022-07-12T16:29:19.000Z",
            "SignatureVersion": "1",
            "Signature": "EXAMPLE",
            "SigningCertURL": "https://sns.example.com/cert.pem",
            "UnsubscribeURL": "https://sns.example.com/unsub"
        })

    def test_parse_sns_notification(self):
        body = self._make_sns_body(bucket='logs-bucket', key='logs/file.gz')
        result = parse_sqs_message_body(body)

        self.assertEqual(len(result), 1)
        n = result[0]
        self.assertIsInstance(n, S3Notification)
        self.assertEqual(n.bucket_name, 'logs-bucket')
        self.assertEqual(n.key_name, 'logs/file.gz')
        self.assertEqual(n.region, 'us-east-1')
        self.assertEqual(n.requester, 'AWS:AIDA1234')
        self.assertEqual(n.source_type, 'sns')

    def test_parse_sns_notification_multiple_records(self):
        s3_event = self._make_s3_event(bucket='b1', key='k1')
        # Add a second record
        second_record = self._make_s3_event(bucket='b2', key='k2')['Records'][0]
        s3_event['Records'].append(second_record)

        body = self._make_sns_body(s3_event=s3_event)
        result = parse_sqs_message_body(body)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].bucket_name, 'b1')
        self.assertEqual(result[1].bucket_name, 'b2')

    def test_parse_sns_notification_skips_non_creation_events(self):
        body = self._make_sns_body(event_name='ObjectRemoved:Delete')
        result = parse_sqs_message_body(body)
        self.assertEqual(len(result), 0)

    def test_parse_sns_notification_invalid_message(self):
        body = json.dumps({
            "Type": "Notification",
            "MessageId": "sns-msg-id",
            "Message": "not-json"
        })
        result = parse_sqs_message_body(body)
        self.assertEqual(len(result), 0)


class TestParseS3DirectNotification(unittest.TestCase):
    def _make_s3_direct_body(self, bucket='my-bucket', key='path/to/object.log',
                             region='us-east-1', principal='AWS:AIDA1234',
                             event_name='ObjectCreated:Put'):
        return json.dumps({
            "Records": [{
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": region,
                "eventTime": "2022-07-12T16:29:18Z",
                "eventName": event_name,
                "userIdentity": {"principalId": principal},
                "requestParameters": {"sourceIPAddress": "1.2.3.4"},
                "responseElements": {},
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "config-1",
                    "bucket": {
                        "name": bucket,
                        "ownerIdentity": {"principalId": "EXAMPLE"},
                        "arn": f"arn:aws:s3:::{bucket}"
                    },
                    "object": {
                        "key": key,
                        "size": 950,
                        "eTag": "abc",
                        "sequencer": "123"
                    }
                }
            }]
        })

    def test_parse_s3_direct_notification(self):
        body = self._make_s3_direct_body()
        result = parse_sqs_message_body(body)

        self.assertEqual(len(result), 1)
        n = result[0]
        self.assertIsInstance(n, S3Notification)
        self.assertEqual(n.bucket_name, 'my-bucket')
        self.assertEqual(n.key_name, 'path/to/object.log')
        self.assertEqual(n.region, 'us-east-1')
        self.assertEqual(n.requester, 'AWS:AIDA1234')
        self.assertEqual(n.source_type, 's3')

    def test_parse_s3_direct_skips_non_creation_events(self):
        body = self._make_s3_direct_body(event_name='ObjectRemoved:Delete')
        result = parse_sqs_message_body(body)
        self.assertEqual(len(result), 0)

    def test_parse_s3_direct_url_decodes_key(self):
        body = self._make_s3_direct_body(key='path/to/my+log+file.gz')
        result = parse_sqs_message_body(body)
        self.assertEqual(result[0].key_name, 'path/to/my log file.gz')

    def test_parse_s3_direct_url_decodes_percent_encoded_key(self):
        body = self._make_s3_direct_body(key='path/to/my%20log%20file.gz')
        result = parse_sqs_message_body(body)
        self.assertEqual(result[0].key_name, 'path/to/my log file.gz')


class TestParseEdgeCases(unittest.TestCase):
    def test_invalid_json_returns_empty(self):
        result = parse_sqs_message_body('not json at all')
        self.assertEqual(result, [])

    def test_empty_string_returns_empty(self):
        result = parse_sqs_message_body('')
        self.assertEqual(result, [])

    def test_unsupported_type_raises_error(self):
        body = json.dumps({"some": "random", "data": True})
        with self.assertRaises(UnsupportedNotificationTypeError):
            parse_sqs_message_body(body)

    def test_s3_notification_repr(self):
        n = S3Notification('b', 'k', 'r', 'req', 'eventbridge')
        self.assertIn('b', repr(n))
        self.assertIn('eventbridge', repr(n))


if __name__ == '__main__':
    unittest.main()