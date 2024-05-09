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


import logging
import os
import sys
import json
import re
import gzip
import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from aws_lambda_powertools.utilities import parameters
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit
from utils.helpers import ENCODING
from version import get_version

logger = logging.getLogger()

LOGV2_API_URL_SUFFIX = '/api/v2/logs/ingest'
ENVIRONMENT_AG_URL_PART = '/e/'

# Related documentation
# https://www.dynatrace.com/support/help/dynatrace-api/environment-api/log-monitoring-v2/post-ingest-logs
# https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/log-monitoring-limits

DYNATRACE_LOG_INGEST_CONTENT_MARK_TRIMMED = '[TRUNCATED]'
# CloudTrail messages can be up to 256KB!
# https://docs.aws.amazon.com/awscloudtrail/latest/userguide/WhatIsCloudTrail-Limits.html
DYNATRACE_LOG_INGEST_CONTENT_MAX_LENGTH = 8192

DYNATRACE_LOG_INGEST_ATTRIBUTE_MAX_LENGTH = 250
DYNATRACE_LOG_INGEST_PAYLOAD_MAX_SIZE = 5242880  # 5MB
DYNATRACE_LOG_INGEST_MAX_RECORD_AGE = 86340  # 1 day
DYNATRACE_LOG_INGEST_MAX_ENTRIES_COUNT = 5000

DYNATRACE_LOG_MESSAGE_MAX_ATTRIBUTES = 50

COMMA_SEPARATOR_LENGTH = 1
LIST_BRACKETS_LENGTH = 2

DYNATRACE_CONNECT_TIMEOUT = 3
DYNATRACE_READ_TIMEOUT = 12

metrics = Metrics()

default_headers = {
    "User-Agent" : f"dynatrace-aws-s3-log-forwarder/{get_version()}"
}

class DynatraceSink():
    def __init__(self, dt_url: str, dt_api_key_parameter: str, verify_ssl: bool = True):
        self._environment_url = dt_url
        self._api_key_parameter = dt_api_key_parameter
        self._approx_buffered_messages_size = LIST_BRACKETS_LENGTH
        self._messages = []
        self._batch_num = 1
        self._s3_source = ""

        retry_strategy = Retry(
            total = 3,
            status_forcelist = [429, 503],
            allowed_methods =['POST'],
            raise_on_status = False,
            backoff_factor = .5
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.mount("https://", adapter)

    def get_num_of_buffered_messages(self):
        return len(self._messages)

    def get_size_of_buffered_messages(self):
        return self._approx_buffered_messages_size

    def is_empty(self):
        return self.get_num_of_buffered_messages() <= 0

    def get_environment_url(self):
        return self._environment_url

    def set_s3_source(self, bucket: str, key: str):
        self._s3_source = f"{bucket}/{key}"

    def push(self, message: dict):
        # Validate that the message size doesn't reach DT limits. If so,
        # truncate the "content" field.

        self.check_log_message_size_and_truncate(message)

        # Check if we'd be exceeding limits before appending the message
        new_message_size = sys.getsizeof(json.dumps(message).encode(ENCODING))
        new_num_of_buffered_messages = self.get_num_of_buffered_messages() + 1
        new_approx_size_of_buffered_messages = (
                    self._approx_buffered_messages_size + new_message_size + COMMA_SEPARATOR_LENGTH)

        # If we'd exceed limits, flush before buffering
        if ( new_num_of_buffered_messages > DYNATRACE_LOG_INGEST_MAX_ENTRIES_COUNT or
             new_approx_size_of_buffered_messages > DYNATRACE_LOG_INGEST_PAYLOAD_MAX_SIZE ):
            self.flush()
            self._batch_num += 1

        # buffer log messages
        self._messages.append(message)
        self._approx_buffered_messages_size += new_message_size + COMMA_SEPARATOR_LENGTH

    def flush(self):
        if not self.is_empty():
            self.ingest_logs(self._messages, batch_num=self._batch_num,session=self.session)
        self._messages = []
        self._approx_buffered_messages_size = LIST_BRACKETS_LENGTH

    def empty_sink(self):
        self._messages = []
        self._approx_buffered_messages_size = LIST_BRACKETS_LENGTH
        self._batch_num = 1
        self._s3_source = ""

    def check_log_message_size_and_truncate(self, message: dict):
        '''
        Gets a Dynatrace LogMessageJson object. If message size exceeds Dynatrace limit, returns
        truncated message.
        '''
        if len(message['content']) > DYNATRACE_LOG_INGEST_CONTENT_MAX_LENGTH:
            trimmed_length = DYNATRACE_LOG_INGEST_CONTENT_MAX_LENGTH - \
                len(DYNATRACE_LOG_INGEST_CONTENT_MARK_TRIMMED)
            message['content'] = message['content'][0:trimmed_length] + \
                DYNATRACE_LOG_INGEST_CONTENT_MARK_TRIMMED
            metrics.add_metric(name='LogMessagesTrimmed',
                               unit=MetricUnit.Count, value=1)
        return message

    def post_logsv2(self, dt_url, dt_api_key, data,
                    compress=True, session=None):
        '''
        Does an HTTP POST request to the Logs V2 API. Compresses data by default.
        '''

        if session is None:
            session = requests.Session()

        headers = {}
        headers.update(default_headers)
        headers.update({
            'Authorization': f'Api-Token {dt_api_key}',
            'Content-Type': 'application/json; charset=utf-8'
        })


        request_data = data

        if compress:
            request_data = gzip.compress(data, compresslevel=6)
            headers['Content-Encoding'] = 'gzip'

        try:
            resp = session.post(dt_url, data=request_data, headers=headers,
                                timeout=(DYNATRACE_CONNECT_TIMEOUT, DYNATRACE_READ_TIMEOUT))
        except Exception:
            logger.exception('Error pushing logs to Dynatrace')
            raise

        return resp

    def ingest_logs(self, logs: list, session=None,
                    batch_num: int = -1):
        '''
        POSTs list of messages to the generic log ingress Dynatrace API.
        Creates batches if messages exceed LogV2 specifications.
        Returns a list of failed batch numbers.
        '''

        # Pull API Key from SSM / Cache for 2 mins
        dt_api_key = parameters.get_parameter(
            self._api_key_parameter, max_age=120, decrypt=True)

        tenant_id = extract_tenant_id_from_url(self._environment_url)

        logger.debug('Preparing log batches to post to Dynatrace: %s', tenant_id)

        # Create a session to re-use connections
        if session is None:
            session = self.session

        data = json.dumps(logs).encode(ENCODING)

        # POST to dynatrace
        start_time = time.time()

        # https://github.com/requests/requests-threads
        resp = self.post_logsv2(self._environment_url + LOGV2_API_URL_SUFFIX,
                                dt_api_key, data, session=session)

        if resp.status_code == 204:
            logger.debug('%s: Successfully posted batch %d. Ingested %.2f KB of log data to Dynatrace',
                         tenant_id, batch_num, (len(data) / 1024))
            metrics.add_metric(name='DynatraceHTTP204Success',
                               unit=MetricUnit.Count, value=1)
        elif resp.status_code == 200:
            logger.warning(
                '%s: Parts of batch %s were not successfully posted: %s. Source file: %s',tenant_id, batch_num, resp.text, self._s3_source)
            metrics.add_metric(
                name='DynatraceHTTP200PartialSuccess', unit=MetricUnit.Count, value=1)
        elif resp.status_code == 400:
            logger.warning(
                '%s: Parts of batch %s were not successfully posted: %s. Source file: %s',tenant_id, batch_num, resp.text, self._s3_source)
            metrics.add_metric(
                name='DynatraceHTTP400InvalidLogEntries', unit=MetricUnit.Count, value=1)
        elif resp.status_code == 429:
            logger.error("%s: Throttled by Dynatrace. Exhausted retry attempts... Source file: %s", tenant_id, self._s3_source)
            metrics.add_metric(name='DynatraceHTTP429Throttled',unit=MetricUnit.Count, value=1)
            metrics.add_metric(name='DynatraceHTTPErrors', unit=MetricUnit.Count, value=1)
            raise DynatraceThrottlingException
        elif resp.status_code == 503:
            logger.error("%s: Usable space limit reached. Exhausted retry attempts... Source file: %s", tenant_id, self._s3_source)
            metrics.add_metric(name='DynatraceHTTP503SpaceLimitReached',unit=MetricUnit.Count, value=1)
            metrics.add_metric(name='DynatraceHTTPErrors', unit=MetricUnit.Count, value=1)
            raise DynatraceThrottlingException
        else:
            logger.error(
                "%s: There was a HTTP %d error posting batch %d to Dynatrace. %s. Source file: %s",
                tenant_id,resp.status_code, batch_num, resp.text, self._s3_source)
            metrics.add_metric(name='DynatraceHTTPErrors',
                               unit=MetricUnit.Count, value=1)
            raise DynatraceIngestionException

        metrics.add_metric(name='UncompressedLogDTPayloadSize',
                           unit=MetricUnit.Bytes, value=sys.getsizeof(data))

        end_time = time.time()
        metrics.add_metric(name='DTIngestionTime',
                           unit=MetricUnit.Seconds, value=(end_time - start_time))


def load_sinks():
    '''
    Loads all configured sinks on environment variables. Returns a dict of sinks:
    {
        'sink1': DynatraceSink,
        'sink2': DynatraceSink
    }
    '''

    regex = r'^DYNATRACE_[A-Z0-9][A-Z0-9]*_ENV_URL$'
    sinks = {}

    verify_ssl = False if os.environ['VERIFY_DT_SSL_CERT'] == "false" else True

    for k, v in os.environ.items():
        if re.match(regex, k):
            sink_id = k.split('_')[1]
            if os.environ.get(f'DYNATRACE_{sink_id}_API_KEY_PARAM'):
                dt_url = v
                dt_api_key_parameter = os.environ[f'DYNATRACE_{sink_id}_API_KEY_PARAM']
                sinks[sink_id] = DynatraceSink(dt_url, dt_api_key_parameter, verify_ssl)
            else:
                logging.warning("No API key configured for sink id %s", sink_id)

    return sinks

def empty_sinks(sinks:list):
    '''
    Gets a list of DynatraceSink objects and empties its contents
    '''
    for _ , sink in sinks.items():
        sink.empty_sink()


def extract_tenant_id_from_url(environment_url: str):
    env_prefix_index = environment_url.find(ENVIRONMENT_AG_URL_PART)
    if env_prefix_index != -1:
        offset = len(ENVIRONMENT_AG_URL_PART)
        return environment_url[env_prefix_index + offset: environment_url.find("/", env_prefix_index + offset)]
    else:
        return environment_url[environment_url.find("//") + 2: environment_url.find(".")]


class DynatraceThrottlingException(Exception):
    pass

class DynatraceIngestionException(Exception):
    pass
