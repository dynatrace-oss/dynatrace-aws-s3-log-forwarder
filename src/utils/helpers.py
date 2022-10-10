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

ENCODING = 'utf-8'

# Collection of helper regular expressions to describe log key name patterns 
# and extract attributes from it

helper_regexes = {
    'aws_logs_prefix' : 'AWSLogs',
    'aws_account_id_pattern' : r'\d{12}',
    'year_pattern' : r'[2]\d{3}',
    'month_pattern' : r'(0[1-9]|1[012])',
    'day_pattern' : r'(0[1-9]|[12][0-9]|3[01])',
    'hour_pattern' : r'([0][0-9]|[1][0-9]|[2][0-3])',
    'minutes_pattern' : r'[0-5][0-9]',
    # https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html,
    'aws_region_pattern' : r'(us(-gov)?|ap|ca|cn|eu|sa|me|af)-(central|((north(east|west)?|south(east|west)?)|(east|west)))-\d{1}',
    'classic_load_balancer_id_pattern' : r'[a-zA-Z0-9][a-zA-Z0-9-]{0,30}[a-zA-Z0-9]',
    # ALB / NLB Load Balancer id can be up to 48 chars, and / is substituted with .,
    'elbv2_id_pattern' : r'[a-zA-Z0-9][a-zA-Z0-9-.]{0,46}[a-zA-Z0-9]',
    'ipv4_address_pattern' : r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
}

def is_yaml_file(file: str):
    return file.endswith('.yaml') or file.endswith('.yml')