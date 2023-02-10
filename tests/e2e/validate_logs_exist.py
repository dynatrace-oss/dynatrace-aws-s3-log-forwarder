#!/usr/bin/env python

# Copyright 2023 Dynatrace LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import argparse
import requests
import os

def check_required_env_variables():
    return "DT_TENANT_URL" in os.environ and "DT_TENANT_API_KEY" in os.environ

def get_logs_from_dynatrace(source_bucket_name,source_key_name):
    url = f"{os.environ['DT_TENANT_URL']}/api/v2/logs/search"

    params = {
        "from": "now-5m",
        "query": f'log.source.aws.s3.bucket.name="{source_bucket_name}" AND log.source.aws.s3.key.name="{source_key_name}"'
    }

    headers = {
        "Authorization": f"Api-Token {os.environ.get('DT_TENANT_API_KEY')}"
    }

    resp = requests.get(url,params=params,headers=headers,timeout=3)

    return resp

def main():

    parser = argparse.ArgumentParser(description="Check if log entries exist for bucket_name and key_name")
    parser.add_argument("--bucket", type=str,required=True)
    parser.add_argument("--key",type=str,required=True)

    args = parser.parse_args()

    results = get_logs_from_dynatrace(args.bucket,args.key)
    
    print("API Response: " + results.text)

    if results.status_code == 200 and results.json().get('sliceSize',0) == 1:
        print("Success. Log entries found!")
        exit(0)
    else:
        print("Error. No log entries found for given bucket and key")
        exit(1)

if __name__ == "__main__":
    main()
