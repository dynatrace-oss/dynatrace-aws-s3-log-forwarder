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
import time
from datetime import datetime, timezone, timedelta

OAUTH_SCOPES = "storage:buckets:read storage:logs:read"

def check_required_env_variables():
    required = ["DT_TENANT_PLATFORM_URL", "DT_SSO_URL", "DT_OAUTH_CLIENT_ID", "DT_OAUTH_CLIENT_SECRET"]
    return all(var in os.environ for var in required)

def get_oauth_bearer_token():
    token_url = f"{os.environ['DT_SSO_URL']}/sso/oauth2/token"
    client_id = os.environ['DT_OAUTH_CLIENT_ID']
    client_secret = os.environ['DT_OAUTH_CLIENT_SECRET']

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": OAUTH_SCOPES,
    }

    resp = requests.post(
        token_url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

POLL_INTERVAL_SECONDS = 10
POLL_MAX_ATTEMPTS = 18

def get_logs_from_dynatrace(source_bucket_name,source_key_name):
    base_url = os.environ['DT_TENANT_PLATFORM_URL']
    execute_url = f"{base_url}/platform/storage/query/v1/query:execute"
    poll_url = f"{base_url}/platform/storage/query/v1/query:poll"

    dql_query = (
        f'fetch logs'
        f' | filter log.source.aws.s3.bucket.name == "{source_bucket_name}"'
        f' AND log.source.aws.s3.key.name == "{source_key_name}"'
        f' | limit 1'
    )

    now = datetime.now(timezone.utc)
    five_minutes_ago = now - timedelta(minutes=5)

    body = {
        "query": dql_query,
        "defaultTimeframeStart": five_minutes_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "defaultTimeframeEnd": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "defaultScanLimitGbytes": -1,
    }

    bearer_token = get_oauth_bearer_token()

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    # Start the query
    resp = requests.post(execute_url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    state = result.get("state")
    request_token = result.get("requestToken")

    # Poll until the query completes
    attempts = 0
    while state == "RUNNING" and attempts < POLL_MAX_ATTEMPTS:
        time.sleep(POLL_INTERVAL_SECONDS)
        attempts += 1

        poll_resp = requests.get(
            poll_url,
            params={"request-token": request_token},
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30,
        )
        poll_resp.raise_for_status()

        result = poll_resp.json()
        state = result.get("state")

    return result

def main():

    parser = argparse.ArgumentParser(description="Check if log entries exist for bucket_name and key_name")
    parser.add_argument("--bucket", type=str,required=True)
    parser.add_argument("--key",type=str,required=True)

    args = parser.parse_args()

    result = get_logs_from_dynatrace(args.bucket, args.key)

    print("Query result: " + str(result))

    state = result.get("state")
    if state != "SUCCEEDED":
        print(f"Error. Query did not succeed. Final state: {state}")
        exit(1)

    records = result.get("result", {}).get("records", [])
    if len(records) > 0:
        print("Success. Log entries found!")
        exit(0)

    print("Error. No log entries found for given bucket and key")
    exit(1)

if __name__ == "__main__":
    main()
