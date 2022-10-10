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

from datetime import datetime
import os
import gzip
import boto3
from botocore import credentials,session
import json


cli_cache = os.path.join(os.path.expanduser('~'),'.aws/cli/cache')
# Construct botocore session with cache
session = session.get_session()
session.get_component('credential_provider').get_provider('assume-role').cache = credentials.JSONFileCache(cli_cache)
s = boto3.Session(botocore_session=session)
s3_client = s.client('s3')

key= 'AWSLogs/012345678910/CloudTrail/us-east-1/2022/07/20/012345678910_CloudTrail_us-east-1_20220720T0735Z_I8jlargemodified.json.gz'
bucket = 'mylogsbucket'

resp = s3_client.get_object(Bucket=bucket, Key = key)

resp_j = json.loads(gzip.decompress(resp['Body'].read()).decode('utf-8'))

current_time = datetime.utcnow()

for obj in resp_j['Records']:
    obj['eventTime']=current_time.strftime('%Y-%m-%dT%H:%M:%SZ')

result = gzip.compress(json.dumps(resp_j).encode('utf-8'))
dest_bucket = "mylogsbucket"
dest_key = (f"AWSLogs/012345678910/CloudTrail/us-east-1/{current_time.strftime('%Y')}/{current_time.strftime('%m')}/{current_time.strftime('%m')}"
           f"/012345678910_CloudTrail_us-east-1_{current_time.strftime('%Y')}{current_time.strftime('%m')}{current_time.strftime('%d')}T"
           f"{current_time.strftime('%H')}{current_time.strftime('%M')}Z_I8jlargemodified.json.gz")

put_resp = s3_client.put_object(Bucket=dest_bucket, Key=dest_key, Body=result)

print(put_resp)