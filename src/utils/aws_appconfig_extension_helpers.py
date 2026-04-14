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

import logging
import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()

appconfig_app_name = os.environ.get('DEPLOYMENT_NAME') + '-app-config'
appconfig_environment_name = os.environ.get('DEPLOYMENT_NAME')

# Module-level boto3 client, initialised once per Lambda execution environment.
_client = None

# Per-profile session state: {profile_name: {'token': str, 'version': str, 'body': str}}
# Tokens are single-use; each successful get_latest_configuration call returns the next one.
_sessions = {}


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client('appconfigdata')
    return _client


def get_configuration_from_aws_appconfig(configuration_profile_name):
    '''
    Retrieves a configuration profile from AWS AppConfig using the appconfigdata SDK.
    Returns a dict:
        {
            'Configuration-Version': str,
            'Body': str  (YAML text of the configuration)
        }

    On the first call for a given profile (cold start), starts a new configuration session
    and fetches the full configuration body.

    On subsequent calls, polls using the stored session token. If the configuration has not
    changed, the cached body and version are returned. If it has changed, the new body and
    version are stored and returned.
    '''
    client = _get_client()

    if configuration_profile_name not in _sessions:
        _start_session_and_fetch(client, configuration_profile_name)
    else:
        _poll_for_updates(client, configuration_profile_name)

    session = _sessions[configuration_profile_name]
    return {
        'Configuration-Version': session['version'],
        'Body': session['body'],
    }


def _start_session_and_fetch(client, profile_name):
    '''Starts a new AppConfig session and performs the initial configuration fetch.'''
    logger.debug("Starting AppConfig session for profile '%s' (app: %s, env: %s)",
                 profile_name, appconfig_app_name, appconfig_environment_name)
    try:
        session_resp = client.start_configuration_session(
            ApplicationIdentifier=appconfig_app_name,
            EnvironmentIdentifier=appconfig_environment_name,
            ConfigurationProfileIdentifier=profile_name,
            RequiredMinimumPollIntervalInSeconds=15,
        )
        token = session_resp['InitialConfigurationToken']
    except (BotoCoreError, ClientError) as ex:
        logger.exception("Failed to start AppConfig session for profile '%s'", profile_name)
        raise ErrorAccessingAppConfig from ex

    try:
        config_resp = client.get_latest_configuration(ConfigurationToken=token)
        body = config_resp['Configuration'].read().decode('utf-8')
        version = config_resp.get('VersionLabel', '1')
        next_token = config_resp['NextPollConfigurationToken']
    except (BotoCoreError, ClientError) as ex:
        logger.exception("Failed to fetch initial configuration for profile '%s'", profile_name)
        raise ErrorAccessingAppConfig from ex

    logger.info("Loaded AppConfig profile '%s' version '%s'", profile_name, version)
    _sessions[profile_name] = {'token': next_token, 'version': version, 'body': body}


def _poll_for_updates(client, profile_name):
    '''Polls AppConfig for configuration updates using the stored session token.'''
    session = _sessions[profile_name]
    logger.debug("Polling AppConfig for updates to profile '%s'", profile_name)
    try:
        config_resp = client.get_latest_configuration(ConfigurationToken=session['token'])
        next_token = config_resp['NextPollConfigurationToken']
        new_body = config_resp['Configuration'].read().decode('utf-8')
    except (BotoCoreError, ClientError) as ex:
        logger.exception("Failed to poll AppConfig for profile '%s'", profile_name)
        raise ErrorAccessingAppConfig from ex

    # Always update the token (tokens are single-use)
    session['token'] = next_token

    if new_body:
        # Non-empty body means the configuration has changed
        new_version = config_resp.get('VersionLabel', session['version'])
        logger.info("AppConfig profile '%s' updated to version '%s'", profile_name, new_version)
        session['version'] = new_version
        session['body'] = new_body


class ErrorAccessingAppConfig(Exception):
    pass