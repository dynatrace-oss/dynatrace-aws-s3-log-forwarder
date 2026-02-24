#!/bin/bash

# Copyright 2023 Dynatrace LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#      https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Download AWS Lambda Layers for AWS AppConfig and AWS Lambda insights extensions

set -e

BASE_DIR=".tmp"

# AWS AppConfig Extension
# https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-integration-lambda-extensions.html
AWS_APPCONFIG_EXTENSION_X86_64="arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension:296"
AWS_APPCONFIG_EXTENSION_ARM64="arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension-Arm64:229"

# AWS Lambda Insights Extension
# https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights-extension-versions.html
AWS_LAMBDA_INSIGHTS_EXTENSION_X86_64="arn:aws:lambda:us-east-1:580247275435:layer:LambdaInsightsExtension:64"
AWS_LAMBDA_INSIGHTS_EXTENSION_ARM64="arn:aws:lambda:us-east-1:580247275435:layer:LambdaInsightsExtension-Arm64:31"

download_layer() {
    aws lambda get-layer-version-by-arn --arn "$1" --query 'Content.Location' | xargs curl -s -o $BASE_DIR/"$2"/"$3"_extension.zip
}

for arch in "X86_64" "ARM64"
do
    arch_to_lower=$(echo $arch | tr '[:upper:]' '[:lower:]')
    # if this is a travis build, download only the layers for the CPU architecture of the build
    if [ -n $LAMBDA_ARCH ] && [[ $LAMBDA_ARCH != $arch_to_lower ]]; then continue; fi
    mkdir -p $BASE_DIR/"$arch_to_lower"
    for extension in "AWS_APPCONFIG" "AWS_LAMBDA_INSIGHTS"
    do
        extension_to_lower=$(echo $extension | tr '[:upper:]' '[:lower:]')
        varname="${extension}"_EXTENSION_"${arch}"
        echo Downloading AWS Lambda Layer $varname: "${!varname}"
        download_layer "${!varname}" "${arch_to_lower}" "${extension_to_lower}"
    done
done
