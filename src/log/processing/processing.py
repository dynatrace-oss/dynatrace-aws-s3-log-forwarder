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
from os import environ
import time
import json
import gzip
import boto3
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit
import jsonslicer

from log.processing.log_processing_rule import LogProcessingRule
from utils.helpers import ENCODING

logger = logging.getLogger()
metrics = Metrics()


def _get_context_log_attributes(bucket: str, key: str):
    '''
    Returns context attributes to the log entry for troubleshooting purposes.
    '''
    return {
        'log.source.s3_bucket_name': bucket,
        'log.source.s3_key_name': key,
        'log.source.forwarder': environ['FORWARDER_FUNCTION_ARN']
    }

def get_jsonslicer_tuple_from_jmespath_path(jmespath:str):
    '''
    Given a jmespath entry (e.g. log.records), translates the expression into a tuple
    for processing with JsonSlicer. (this is a basic implementation, not jmespath spec compliant)
    '''
    jsonslicer_tuple = tuple(jmespath.split('.'))
    jsonslicer_tuple += (None,)

    return jsonslicer_tuple


def process_log_object(log_processing_rule: LogProcessingRule,bucket: str, key: str, user_defined_annotations: dict = {}, session: boto3.Session = None, log_sinks=None):
    '''
    Downloads a log from S3, decompresses and reads log messages within it and transforms the messages to Dynatrace LogV2 API format.
    Can read JSON logs (list of dicts) or text line by line (both gzipped or plain).
    The function also adds context, inferred and user-defined log attributes. Returns a the number of log entries processed.
    '''

    start_time = time.time()

    # https://ben11kehoe.medium.com/boto3-sessions-and-why-you-should-use-them-9b094eb5ca8e
    # https://github.com/boto/boto3/issues/2707
    if not session:
        session = boto3._get_default_session()

    s3_client = session.client('s3')

    log_obj_http_response = s3_client.get_object(Bucket=bucket, Key=key)

    botocore_log_stream = log_obj_http_response['Body']
    log_entries = []

    if key.endswith('.gz'):
        log_stream = gzip.GzipFile(mode='rb', fileobj=botocore_log_stream)
    else:
        log_stream = botocore_log_stream

    path_tuple = (None, )
    if key.endswith('.json.gz') or key.endswith('.json'):
        if log_processing_rule.log_entries_key is not None:
            path_tuple = get_jsonslicer_tuple_from_jmespath_path(log_processing_rule.log_entries_key)

        log_entries = jsonslicer.JsonSlicer(log_stream, path_tuple)
    else:
        if key.endswith('.gz'):
            log_entries = log_stream
        else:
            log_entries = log_stream.iter_lines()
            
    log_attributes = {}

    # Add custom log annotations from log forwarding rule
    log_attributes.update(user_defined_annotations)

    # Add context annotations
    log_attributes.update(_get_context_log_attributes(bucket, key))
    log_attributes.update(log_processing_rule.get_attributes_from_s3_key_name(key))
    log_attributes.update(log_processing_rule.get_processing_log_annotations())
    
    # Count log entries (can't len() a stream)
    num_log_entries = 0

    # catch if we can't find any valid log entries
    if log_entries:
        for log_entry in log_entries:
            dt_log_message = {}

            if isinstance(log_entry, bytes):
                log_entry = log_entry.decode(ENCODING)

            # add known and custom annotations to log message
            dt_log_message.update(log_attributes)

            # Add extracted attributes and log annotations from log processing rule
            dt_log_message.update(log_processing_rule.get_extracted_log_attributes(log_entry))

            # log.content
            if isinstance(log_entry, str):
                line = log_entry
                if line == '':
                    logger.debug('skipping empty log line')
                    continue

                dt_log_message['content'] = line

            elif isinstance(log_entry, dict):
                dt_log_message['content'] = json.dumps(log_entry)
            else:
                logger.warning("Log entry is not a dict")
                metrics.add_metric(name='InvalidLogEntries',
                    unit=MetricUnit.Count, value=1)

            # Push to destination sink(s)
            for log_sink in log_sinks:
                log_sink.push(dt_log_message)

            num_log_entries += 1

            if num_log_entries % 1000 == 0:
                logger.debug(f"Processed {num_log_entries} entries")

        logger.debug(f"Total log entries processed in batch: {num_log_entries}")
    else:
        logger.warning("Can't find log entries applying processing rule %s on s3://%s/%s",
                   log_processing_rule.name, bucket, key )
        metrics.add_metric(name='LogFilesWithoutLogEntries',
                   unit=MetricUnit.Count, value=1)

    end_time = time.time()
    metrics.add_metric(name='LogProcessingTime',
                       unit=MetricUnit.Seconds, value=(end_time - start_time))
    # return number of log entries processed
    return(num_log_entries)
