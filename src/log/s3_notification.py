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
import logging
from urllib.parse import unquote_plus


logger = logging.getLogger()


class S3Notification:
    def __init__(self, bucket_name: str, key_name: str, region: str, requester: str, source_type: str):
        self.bucket_name = bucket_name
        self.key_name = key_name
        self.region = region
        self.requester = requester
        self.source_type = source_type

    def __repr__(self):
        return (f"S3Notification(bucket_name={self.bucket_name!r}, key_name={self.key_name!r}, "
                f"region={self.region!r}, requester={self.requester!r}, source_type={self.source_type!r})")


class UnsupportedNotificationTypeError(Exception):
    pass


def parse_sqs_message_body(body: str) -> list:
    try:
        notification = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning('Dropping message, body is not valid JSON: %s', exc.doc)
        return []

    notification_type = _detect_notification_type(notification)

    if notification_type == 'eventbridge':
        return [_parse_eventbridge_notification(notification)]
    elif notification_type == 'sns':
        return _parse_sns_notification(notification)
    elif notification_type == 's3':
        return _parse_s3_notification(notification)
    else:
        raise UnsupportedNotificationTypeError(
            f'Unable to determine notification type from message body: {json.dumps(notification)[:200]}'
        )


def _detect_notification_type(notification: dict) -> str:
    if notification.get('source') == 'aws.s3' and 'detail' in notification:
        return 'eventbridge'

    detail = notification.get('detail')
    if isinstance(detail, dict) and 'bucket' in detail and 'object' in detail:
        return 'eventbridge'

    if notification.get('Type') == 'Notification' and 'Message' in notification:
        return 'sns'

    records = notification.get('Records')
    if isinstance(records, list) and len(records) > 0:
        if records[0].get('eventSource') == 'aws:s3':
            return 's3'

    return 'unknown'


def _parse_eventbridge_notification(notification: dict) -> S3Notification:
    detail = notification['detail']
    return S3Notification(
        bucket_name=detail['bucket']['name'],
        key_name=detail['object']['key'],
        region=notification.get('region', ''),
        requester=detail.get('requester', 'unknown'),
        source_type='eventbridge'
    )


def _parse_sns_notification(notification: dict) -> list:
    try:
        s3_event = json.loads(notification['Message'])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning('Unable to parse SNS Message field: %s', exc)
        return []

    records = s3_event.get('Records', [])
    if not isinstance(records, list):
        logger.warning('SNS Message does not contain valid S3 event Records')
        return []

    return _extract_s3_records(records, source_type='sns')


def _parse_s3_notification(notification: dict) -> list:
    records = notification.get('Records', [])
    return _extract_s3_records(records, source_type='s3')


def _extract_s3_records(records: list, source_type: str = 's3') -> list:
    notifications = []
    for record in records:
        event_name = record.get('eventName', '')
        # Only process object creation events
        if not event_name.startswith('ObjectCreated'):
            logger.debug('Skipping non-creation S3 event: %s', event_name)
            continue

        try:
            s3_info = record['s3']
            key_name = unquote_plus(s3_info['object']['key'])
            notifications.append(S3Notification(
                bucket_name=s3_info['bucket']['name'],
                key_name=key_name,
                region=record.get('awsRegion', ''),
                requester=record.get('userIdentity', {}).get('principalId', 'unknown'),
                source_type=source_type
            ))
        except KeyError:
            logger.warning('Skipping malformed S3 event record: %s', json.dumps(record)[:200])
            continue

    return notifications