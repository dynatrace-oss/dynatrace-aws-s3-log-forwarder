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
    'ipv4_address_pattern' : r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)',
    'aws_resource_name_pattern': r'[a-zA-Z0-9-_]{1,128}',
    'vpc_id_pattern': r'vpc-[0-9a-f]{8}(?:[0-9a-f]{9})?',
    'cloudfront_distribution_id_pattern': r'E[A-Z0-9]{13}',
    'vpc_flow_id_pattern': r'fl-[0-9a-f]{8}(?:[0-9a-f]{9})?',
    'aws_global_accelerator_id_pattern': r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
}

custom_grok_expressions = {
    # grab timestamp from CloudFront log (YYY-mm-dd\tHH:MM:SS)
    'CLOUDFRONTTIMESTAMP' : '%{YEAR}-%{MONTHNUM}-%{MONTHDAY}%{SPACE}%{TIME}'
}

def get_split_member(params,name):
    return name.split(params['delimiter'])[params['attribute_index']]

def get_string_found(params,name):
    for string in params["strings"]:
        if name.find(string) != -1:
            return string

    return ''

def get_attributes_from_cloudwatch_logs_data(log_group_name,log_stream_name):
    '''
    Extracts AWS attributes given a CloudWatch Logs Log Group and Log Stream names
    '''
    aws_service_cw_logs_attribute_map = {
        "eks": {
            # /aws/eks/cluster-name/cluster
            "log_group_name": {
                "aws.resource.id": {
                    "operation": "split",
                    "parameters": {
                        "delimiter" :"/",
                        "attribute_index": 3
                    }
                }
            },
            # kube-api-server
            "log_stream_name": {
                "log.source": {
                    "operation": "find_strings",
                    "parameters": {
                        "strings": [
                            "kube-apiserver-audit",
                            "kube-apiserver",
                            "authenticator",
                            "kube-controller-manager",
                            "kube-scheduler"
                        ]
                    }
                }

            }
        },
        "lambda": {
            "log_group_name": {
                "aws.resource.id": {
                    "operation": "split",
                    "parameters": {
                        "delimiter" :"/",
                        "attribute_index": 3
                    }
                }
            },
            "log_stream_name": {}
        }
    }

    options = {
        "split": get_split_member,
        "find_strings": get_string_found
    }

    aws_service_name = log_group_name.split("/")[2]

    cwl_attributes = {
        "log_group_name": log_group_name,
        "log_stream_name": log_stream_name
    }

    extracted_attributes = { 
        "aws.service": aws_service_name
    }

    if aws_service_name in aws_service_cw_logs_attribute_map:
        for i in ["log_group_name", "log_stream_name"]:
            for attribute,extraction_details in aws_service_cw_logs_attribute_map[aws_service_name][i].items():
                extracted_attributes[attribute] = options[extraction_details['operation']](
                                        extraction_details['parameters'], cwl_attributes[i])
    
    return extracted_attributes

def is_yaml_file(file: str):
    return file.endswith('.yaml') or file.endswith('.yml')