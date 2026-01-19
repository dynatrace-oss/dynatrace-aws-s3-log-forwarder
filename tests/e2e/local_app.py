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
import sys
import boto3
import os
import json
import hashlib
import gzip
from jinja2 import Environment, BaseLoader, select_autoescape
from datetime import datetime, timedelta, timezone
import yaml
import pprint



pp = pprint.PrettyPrinter(indent=4)


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# log to stdout
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def next_log_timestamp_gen(date_format_str):
    log_timestamp = datetime.now(timezone.utc) - timedelta(hours=2, minutes=55)
    while True:
        log_timestamp = log_timestamp - timedelta(seconds=1)
        yield log_timestamp.strftime(date_format_str)


def load_s3_test_data_from_disk():
    event_records = []

    S3_TEST_DATA_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '../test_data/'
    )

    for (dir_path, dir_names, file_names) in os.walk(S3_TEST_DATA_PATH):
        if '_test_setup.yaml' in file_names:
            logger.debug(f'found test config in {dir_path}')

            with open(f'{dir_path}/_test_setup.yaml') as f:
                try:
                    setup = yaml.safe_load(f)
                    
                    for file, config in setup['files'].items():
                        logger.debug(f'preparing test data {dir_path}/{file}')
                        
                        bucket = config['bucket']
                        account_id = config['account_id']
                        key = config['key']
                        
                        if 'requester' in config:
                            requester = config['requester']
                        else:
                            requester = 'none'

                        f = open(f'{dir_path}/{file}', 'rb')
                        data = f.read()
                        f.close()

                        env = Environment(
                            loader=BaseLoader(),
                            autoescape=select_autoescape()
                        )

                        if 'pipeline' in config:
                            for step in config['pipeline']:
                                pp.pprint(step)
                                if isinstance(step, dict):
                                    step_name = list(step.keys())[0]
                                    args = step[step_name]['args']
                                    step = step_name
                                
                                step = step.lower()
                                if step == 'gz':
                                    if isinstance(data, str):
                                        data = data.encode('utf-8')
                                    data = gzip.compress(data)
                                elif step == 'update_timestamps':
                                    if isinstance(data, bytes):
                                        data = data.decode('utf-8')
                                    template = env.from_string(data)
                                    time_format = args[0]
                                    data = template.render(
                                        next_log_timestamp=lambda: next(
                                            next_log_timestamp_gen(time_format)))
                                elif step == 'print':
                                    print(data)
                                else:
                                    raise Exception(
                                        f'processing steps ${step} not implemented')                            

                        logger.debug(f'saving data mock s3 {bucket}/{key}')
                        s3 = boto3.client('s3')
                        s3.create_bucket(Bucket=bucket)
                        s3.put_object(Bucket=bucket, Key=key, Body=data, ExpectedBucketOwner = account_id)

                        event_records.append('{"messageId": "' + hashlib.md5(key.encode('utf-8')).hexdigest() +
                                        '","body": "{\\"region\\":\\"us-east-1\\",\\"detail\\":{\\"bucket\\":{\\"name\\":\\"' + bucket + '\\"},\\"object\\":{\\"key\\":\\"' + key + '\\"},\\"requester\\":\\"' + requester + '\\"}}"}')
                except:
                    logger.exception('an unforseen issue occured')
   
    return '{"Records":[' + ",".join(event_records) + ']}'


if os.environ['AWS_SAM_LOCAL'] == 'True':
    logger.warning('mocking boto3 S3')
    logger.warning('mocking boto3 SSM')
    
    from moto import mock_s3, mock_ssm

    def save_test_ssm_parameters():
        client = boto3.client('ssm')
        api_key_parameter = os.environ['DYNATRACE_1_API_KEY_PARAM']
        client.put_parameter(Name=api_key_parameter, Type='SecureString',
                             Value=os.environ['DYNATRACE_1_API_KEY'])

    class test_context():
        def __init__(self):
            self.invoked_function_arn = 'test'

        def get_remaining_time_in_millis(self):
            return(25000)

    @mock_s3
    @mock_ssm
    def run_locally():
        # import here so S3 is mocked
        # http://docs.getmoto.org/en/latest/docs/getting_started.html#what-about-those-pesky-imports
        from app import lambda_handler

        save_test_ssm_parameters()
        events = load_s3_test_data_from_disk()
        
        lambda_handler(json.loads(events), test_context())

if __name__ == '__main__':
    run_locally()
