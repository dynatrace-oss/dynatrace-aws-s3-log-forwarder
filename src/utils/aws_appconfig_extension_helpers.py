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
import requests

logger = logging.getLogger()

appconfig_app_name = os.environ.get('DEPLOYMENT_NAME') + '-app-config'
appconfig_environment_name = os.environ.get('DEPLOYMENT_NAME')
aws_appconfig_url = f"http://localhost:2772/applications/{appconfig_app_name}/environments/{appconfig_environment_name}/configurations"

def get_configuration_from_aws_appconfig(configuration_profile_name):
    '''
    Pulls the log_forwarding_rules from AWS AppConfig. Returns a dict:
        {
            'Configuration-Version': 1,
            'Body': configuration_object
        }
    '''
    try:
        logger.debug("Pulling configuration %s from AWS AppConfig...", appconfig_app_name)
        resp = requests.get(aws_appconfig_url + f"/{configuration_profile_name}", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as ex:
        logger.exception("Request to pull %s from AWSAppConfig Lambda extension returned an error", configuration_profile_name)
        raise ErrorAccessingAppConfig from ex
    except requests.exceptions.Timeout as ex:
        logger.exception("Request to pull %s from AWS AppConfig Lambda extension timed out", configuration_profile_name)
        raise ErrorAccessingAppConfig from ex
    except requests.exceptions.ConnectionError as ex:
        logger.exception("Failed to connect to the AWS AppConfig Lambda extension endpoint while pulling %s", configuration_profile_name)
        raise ErrorAccessingAppConfig from ex

    return {
        'Configuration-Version': int(resp.headers['Configuration-Version']),
        'Body': resp.text
    }

class ErrorAccessingAppConfig(Exception):
    pass