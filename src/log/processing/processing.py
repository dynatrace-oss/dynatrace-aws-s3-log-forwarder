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


import gzip
import json
import logging
import sys
import time
from os import environ

import boto3
import jmespath
import jsonslicer
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

from log.processing.log_processing_rule import LogProcessingRule
from utils.helpers import ENCODING

logger = logging.getLogger()
metrics = Metrics()

EXECUTION_REMAINING_TIME_LIMIT = 10000


def _get_context_log_attributes(bucket: str, key: str):
    '''
    Returns context attributes to the log entry for troubleshooting purposes.
    '''
    return {
        'log.source.aws.s3.bucket.name': bucket,
        'log.source.aws.s3.key.name': key,
        'cloud.log_forwarder': environ['FORWARDER_FUNCTION_ARN']
    }

def _push_to_sinks(dt_log_message: dict, log_sinks: list, skip_content_attribute: bool):
    '''
    Helper method to push given log message to given log sinks, 
    taking into account whether or not to skip the content attribute
    '''
    def __without_content(log_message: dict) -> dict:
        clone_log_message = log_message.copy()
        clone_log_message['content'] = f'c.h={hash(frozenset(log_message.items()))}'
        return clone_log_message

    log_message =  __without_content(dt_log_message) if skip_content_attribute else dt_log_message
    
    for log_sink in log_sinks:
        log_sink.push(log_message)

def get_jsonslicer_path_prefix_from_jmespath_path(jmespath_expr: str):
    '''
    Given a jmespath entry (e.g. log.records), translates the expression into a tuple
    for processing with JsonSlicer. (this is a basic implementation, not jmespath spec compliant)
    '''
    jsonslicer_tuple = tuple(jmespath_expr.split('.'))
    jsonslicer_tuple += (None,)

    return jsonslicer_tuple

def get_log_entry_size(log_entry):
    '''
    Gets a log entry instance of type dict or bytes and returns its raw size
    '''
    if isinstance(log_entry,dict):
        size = sys.getsizeof(json.dumps(log_entry).encode(ENCODING))
    elif isinstance(log_entry,bytes):
        size = sys.getsizeof(log_entry)
    else:
        logger.warning("Can't determine the size of the log entry")
        size = 0

    return size

def process_log_object(log_processing_rule: LogProcessingRule, bucket: str, key: str, bucket_region: str, log_sinks: list,
                       lambda_context, user_defined_annotations: dict = None, session: boto3.Session = None):
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

    if user_defined_annotations is None:
        user_defined_annotations = {}

    s3_client = session.client('s3')

    log_obj_http_response = s3_client.get_object(Bucket=bucket, Key=key)

    log_obj_http_response_body = log_obj_http_response['Body']
    log_obj_http_response_content_encoding = log_obj_http_response.get('ContentEncoding', '').lower()

    logger.debug("s3://%s/%s Object size: %i KB",bucket,key,log_obj_http_response['ContentLength']/1024)

    if key.endswith('.gz') or log_obj_http_response_content_encoding == 'gzip':
        log_stream = gzip.GzipFile(
            mode='rb', fileobj=log_obj_http_response_body)
    else:
        log_stream = log_obj_http_response_body

    # Get log_format from processing rule and generate iterable log_entries

    # if JSON (we expect either a list[dict] or a JSON obj with a list of log entries in a key)
    if log_processing_rule.log_format == 'json':
        if log_processing_rule.log_entries_key is not None:
            json_slicer_path_prefix = get_jsonslicer_path_prefix_from_jmespath_path(
                log_processing_rule.log_entries_key)
        else:
            json_slicer_path_prefix = (None, )
        log_entries = jsonslicer.JsonSlicer(
            log_stream, json_slicer_path_prefix)

    # if it's a stream of JSON objects, create an iterable list of dicts
    elif log_processing_rule.log_format == 'json_stream':
        # if the rule is cw_to_fh, need to decompress data
        if log_processing_rule.name == "cwl_to_fh":
            json_stream = gzip.GzipFile(mode='rb', fileobj=log_stream)
        else:
            json_stream = log_stream

        json_slicer_path_prefix = []
        log_entries = jsonslicer.JsonSlicer(
            json_stream, json_slicer_path_prefix, yajl_allow_multiple_values=True)

    # if it's text, either iterate the GzipFile if compressed or botocore response body iter_lines() if plain text
    elif log_processing_rule.log_format == 'text':
        if type(log_stream) is gzip.GzipFile:
            log_entries = log_stream
        else:
            log_entries = log_stream.iter_lines()

    # catch-all? this should never happen
    else:
        log_entries = []

    context_log_attributes = {}

    # Add custom log annotations from log forwarding rule
    context_log_attributes.update(user_defined_annotations)

    # Add context annotations
    context_log_attributes.update(_get_context_log_attributes(bucket, key))
    context_log_attributes.update(
        log_processing_rule.get_attributes_from_s3_key_name(key))
    context_log_attributes.update(
        log_processing_rule.get_processing_log_annotations())

    # Count log entries (can't len() a stream)
    num_log_entries = 0
    decompressed_log_object_size = 0

    for log_entry in log_entries:

        dt_log_message = {}

        # calculate raw log entry size
        decompressed_log_object_size += get_log_entry_size(log_entry)

        # start with the json_list within json_stream case as it requires a
        # second level of iteration
        if (log_processing_rule.log_format == 'json_stream' and
                log_processing_rule.log_entries_key is not None):
            if isinstance(log_entry, dict):
                # check if we need to process this entry, or not
                if log_processing_rule.filter_json_objects_key is not None:
                    if log_entry[log_processing_rule.filter_json_objects_key] != log_processing_rule.filter_json_objects_value:
                        continue

                # check if we need to inherit attributes from top level object
                top_level_json_attributes = {}

                if log_processing_rule.attribute_extraction_from_top_level_json:
                    for k, v in log_processing_rule.attribute_extraction_from_top_level_json.items():
                        attr_value = jmespath.search(k, log_entry)
                        if attr_value:
                            top_level_json_attributes[v] = attr_value
                        else:
                            logger.warning(
                                'No matches found for %s in top level json.', k)

                # iterate through list of log entries in json obj within json stream
                for sub_entry in log_entry[log_processing_rule.log_entries_key]:
                    dt_log_message = {}
                    dt_log_message['content'] = json.dumps(sub_entry)

                    dt_log_message.update(context_log_attributes)
                    dt_log_message.update(top_level_json_attributes)

                    # add cwl attributes to subentry for additional extraction
                    sub_entry.update(top_level_json_attributes)
                    dt_log_message.update(
                        log_processing_rule.get_extracted_log_attributes(sub_entry, dt_log_message))

                    # if the aws.region is not found, infer region from bucket
                    if "aws.region" not in dt_log_message:
                        dt_log_message['aws.region'] = bucket_region

                    # Push to destination sink(s)
                    _push_to_sinks(dt_log_message, log_sinks, log_processing_rule.skip_content_attribute)

                    num_log_entries += 1
            else:
                logger.error(
                    'Log entry was expected to be dict, but is %s', type(log_entry))
                metrics.add_metric(name='FilesWithInvalidLogEntries',
                                   unit=MetricUnit.Count, value=1)
                raise ValueError("Json Stream message didn't return a dict")

            # if we're processing a large log file, check remaining execution time
            # do this here, since we continue for json-stream + list
            if num_log_entries % 1000 == 0:
                logger.debug("Processed %s entries", str(num_log_entries))
                # Check remaining execution time for Lambda function
                if lambda_context.get_remaining_time_in_millis() <= EXECUTION_REMAINING_TIME_LIMIT:
                    raise NotEnoughExecutionTimeRemaining
            # continue to next JSON object in stream
            continue

        # if log is text, json list or json stream
        elif log_processing_rule.log_format == 'text':
            # check if we need to skip header lines
            if num_log_entries+1 <= log_processing_rule.skip_header_lines:
                num_log_entries +=1
                continue
            if isinstance(log_entry, bytes):
                log_entry = log_entry.decode(ENCODING)
                if log_entry == '':
                    logger.debug('skipping empty log line')
                    continue
                dt_log_message['content'] = log_entry
            else:
                metrics.add_metric(name='FilesWithInvalidLogEntries',
                                   unit=MetricUnit.Count, value=1)
                raise ValueError(
                    f'Log entry was expected to be bytes, but is {type(log_entry)}')

        # if JSON or Stream of JSONs (without subentries)
        elif (log_processing_rule.log_format == 'json' or
              (log_processing_rule.log_format == 'json_stream' and not log_processing_rule.log_entries_key)):
            if isinstance(log_entry, dict):
                dt_log_message['content'] = json.dumps(log_entry)
            else:
                metrics.add_metric(name='FilesWithInvalidLogEntries',
                                   unit=MetricUnit.Count, value=1)
                raise ValueError(
                    f'Log entry was expected to be dict, but is {type(log_entry)}')

        # add context and custom annotations to log message
        dt_log_message.update(context_log_attributes)

        # Add extracted attributes and log annotations from log processing rule
        dt_log_message.update(
            log_processing_rule.get_extracted_log_attributes(log_entry, dt_log_message))

        # if the aws.region is not found, infer region from bucket
        if "aws.region" not in dt_log_message:
            dt_log_message['aws.region'] = bucket_region

        # Push to destination sink(s)
        _push_to_sinks(dt_log_message, log_sinks, log_processing_rule.skip_content_attribute)

        num_log_entries += 1

        # if we're processing a large log file, check remaining execution time
        if num_log_entries % 1000 == 0:
            logger.debug("Processed %s entries", str(num_log_entries))
            # Check remaining execution time for Lambda function
            if lambda_context.get_remaining_time_in_millis() <= EXECUTION_REMAINING_TIME_LIMIT:
                raise NotEnoughExecutionTimeRemaining

    logger.info("Total log entries processed: %s", str(num_log_entries))

    end_time = time.time()
    metrics.add_metric(name='LogProcessingTime',
                       unit=MetricUnit.Seconds, value=(end_time - start_time))
    metrics.add_metric(name='ReceivedUncompressedLogFileSize',
                       unit=MetricUnit.Bytes, value=decompressed_log_object_size)

    # return number of log entries processed
    return (num_log_entries)


class NotEnoughExecutionTimeRemaining(Exception):
    '''
    Exception for running out of Lambda execution time
    '''
    pass
