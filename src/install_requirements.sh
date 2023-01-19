#!/bin/bash

# ============================================================================
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
# ==============================================================================

set -e

function install_lambda_insights() {
    #https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Lambda-Insights-Getting-Started-docker.html
    EXPECTED_PUBLIC_KEY_FINGERPRINT='E0AF FA11 FFF3 5BD7 349E E222 479C 97A1 848A BDC8'

    curl -O https://lambda-insights-extension.s3-ap-northeast-1.amazonaws.com/lambda-insights-extension.gpg

    GPG_IMPORT_OUTPUT=$(gpg --import lambda-insights-extension.gpg 2>&1)

    DOWNLOADED_PUBLIC_KEY_FINGERPRINT=$(gpg --fingerprint $KEY | grep "fingerprint" | cut -d'=' -f2 | xargs)

    if [ "$DOWNLOADED_PUBLIC_KEY_FINGERPRINT" == "$EXPECTED_PUBLIC_KEY_FINGERPRINT" ]; then
      curl -O https://lambda-insights-extension.s3-ap-northeast-1.amazonaws.com/amazon_linux/lambda-insights-extension.rpm
      curl -O https://lambda-insights-extension.s3-ap-northeast-1.amazonaws.com/amazon_linux/lambda-insights-extension.rpm.sig
      gpg --verify lambda-insights-extension.rpm.sig lambda-insights-extension.rpm
      rpm -U lambda-insights-extension.rpm
      rm -f lambda-insights-extension.rpm
    else
      echo "ERROR! Invalid GPG Key Fingerprint for Lambda Insights extension. Aborting."
      exit -1
    fi
}

pip install --no-cache-dir --upgrade pip

# jsonslicer and pygrok have no wheel, add --use-pep517 https://github.com/pypa/pip/issues/8559
# https://github.com/AMDmi3/jsonslicer/issues/56
pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}" --use-pep517

if [[ $ENV == "DEV" ]]; then
  pip install --no-cache-dir -r requirements-dev.txt --target "${LAMBDA_TASK_ROOT}"
fi

if [[ $ENABLE_LAMBDA_INSIGHTS == "true" && $(uname -p) == "x86_64" ]]; then
  # No RPM for lambda insights for arm64
  # https://github.com/awsdocs/amazon-cloudwatch-user-guide/issues/97
  install_lambda_insights
fi