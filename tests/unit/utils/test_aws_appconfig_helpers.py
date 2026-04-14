# Copyright 2024 Dynatrace LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import io
import unittest
from unittest.mock import MagicMock, patch

import utils.aws_appconfig_extension_helpers as helper


def _make_streaming_body(text):
    return io.BytesIO(text.encode('utf-8'))


class TestGetConfigurationFromAwsAppconfig(unittest.TestCase):

    def setUp(self):
        # Reset module-level state between tests
        helper._sessions.clear()
        helper._client = None

    def _make_client(self, initial_body='config-body', version='1', changed_body='', changed_version='2'):
        client = MagicMock()
        client.start_configuration_session.return_value = {
            'InitialConfigurationToken': 'initial-token'
        }
        first_response = {
            'Configuration': _make_streaming_body(initial_body),
            'NextPollConfigurationToken': 'next-token-1',
            'VersionLabel': version,
        }
        second_response = {
            'Configuration': _make_streaming_body(changed_body),
            'NextPollConfigurationToken': 'next-token-2',
            'VersionLabel': changed_version,
        }
        client.get_latest_configuration.side_effect = [first_response, second_response]
        return client

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_cold_start_starts_session_and_returns_config(self, mock_get_client):
        client = self._make_client(initial_body='my-yaml-config', version='3')
        mock_get_client.return_value = client

        result = helper.get_configuration_from_aws_appconfig('log-forwarding-rules')

        client.start_configuration_session.assert_called_once_with(
            ApplicationIdentifier=helper.appconfig_app_name,
            EnvironmentIdentifier=helper.appconfig_environment_name,
            ConfigurationProfileIdentifier='log-forwarding-rules',
            RequiredMinimumPollIntervalInSeconds=15,
        )
        client.get_latest_configuration.assert_called_once_with(ConfigurationToken='initial-token')
        self.assertEqual(result['Body'], 'my-yaml-config')
        self.assertEqual(result['Configuration-Version'], '3')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_subsequent_call_no_change_returns_cached_body(self, mock_get_client):
        # First call: cold start with full body; second call: empty body (no change)
        client = self._make_client(initial_body='original-config', version='1', changed_body='')
        mock_get_client.return_value = client

        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')
        result = helper.get_configuration_from_aws_appconfig('log-forwarding-rules')

        # start_configuration_session called only once (cold start)
        client.start_configuration_session.assert_called_once()
        # get_latest_configuration called twice: cold start + poll
        self.assertEqual(client.get_latest_configuration.call_count, 2)
        # Second poll used the NextPollConfigurationToken from the first response
        client.get_latest_configuration.assert_called_with(ConfigurationToken='next-token-1')
        # Body and version remain unchanged
        self.assertEqual(result['Body'], 'original-config')
        self.assertEqual(result['Configuration-Version'], '1')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_subsequent_call_with_change_returns_new_body(self, mock_get_client):
        # First call: cold start; second call: non-empty body (config changed)
        client = self._make_client(
            initial_body='original-config', version='1',
            changed_body='updated-config', changed_version='2',
        )
        mock_get_client.return_value = client

        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')
        result = helper.get_configuration_from_aws_appconfig('log-forwarding-rules')

        self.assertEqual(result['Body'], 'updated-config')
        self.assertEqual(result['Configuration-Version'], '2')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_session_token_advances_after_each_poll(self, mock_get_client):
        client = self._make_client(initial_body='body', version='1', changed_body='')
        mock_get_client.return_value = client

        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')  # cold start → token = next-token-1
        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')  # poll → token = next-token-2

        self.assertEqual(helper._sessions['log-forwarding-rules']['token'], 'next-token-2')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_independent_sessions_per_profile(self, mock_get_client):
        client = MagicMock()
        client.start_configuration_session.return_value = {'InitialConfigurationToken': 'tok'}
        client.get_latest_configuration.return_value = {
            'Configuration': _make_streaming_body('body'),
            'NextPollConfigurationToken': 'next-tok',
            'VersionLabel': '1',
        }
        mock_get_client.return_value = client

        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')
        helper.get_configuration_from_aws_appconfig('log-processing-rules')

        self.assertIn('log-forwarding-rules', helper._sessions)
        self.assertIn('log-processing-rules', helper._sessions)
        self.assertEqual(client.start_configuration_session.call_count, 2)

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_start_session_error_raises_error_accessing_appconfig(self, mock_get_client):
        from botocore.exceptions import ClientError
        client = MagicMock()
        client.start_configuration_session.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Not found'}},
            'StartConfigurationSession',
        )
        mock_get_client.return_value = client

        with self.assertRaises(helper.ErrorAccessingAppConfig):
            helper.get_configuration_from_aws_appconfig('log-forwarding-rules')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_get_latest_configuration_error_raises_error_accessing_appconfig(self, mock_get_client):
        from botocore.exceptions import ClientError
        client = MagicMock()
        client.start_configuration_session.return_value = {'InitialConfigurationToken': 'tok'}
        client.get_latest_configuration.side_effect = ClientError(
            {'Error': {'Code': 'BadRequestException', 'Message': 'Bad token'}},
            'GetLatestConfiguration',
        )
        mock_get_client.return_value = client

        with self.assertRaises(helper.ErrorAccessingAppConfig):
            helper.get_configuration_from_aws_appconfig('log-forwarding-rules')

    @patch('utils.aws_appconfig_extension_helpers._get_client')
    def test_poll_error_raises_error_accessing_appconfig(self, mock_get_client):
        from botocore.exceptions import ClientError
        client = MagicMock()
        client.start_configuration_session.return_value = {'InitialConfigurationToken': 'tok'}
        # First call succeeds, second raises
        client.get_latest_configuration.side_effect = [
            {
                'Configuration': _make_streaming_body('body'),
                'NextPollConfigurationToken': 'next-tok',
                'VersionLabel': '1',
            },
            ClientError(
                {'Error': {'Code': 'InternalServerException', 'Message': 'oops'}},
                'GetLatestConfiguration',
            ),
        ]
        mock_get_client.return_value = client

        helper.get_configuration_from_aws_appconfig('log-forwarding-rules')
        with self.assertRaises(helper.ErrorAccessingAppConfig):
            helper.get_configuration_from_aws_appconfig('log-forwarding-rules')


if __name__ == '__main__':
    unittest.main()
