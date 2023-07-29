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

ARG ARCH
ARG ENABLE_LAMBDA_INSIGHTS
ARG LAMBDA_BASE_IMAGE_TAG

FROM public.ecr.aws/lambda/python:${LAMBDA_BASE_IMAGE_TAG} AS base

ARG ARCH
ARG ENV 

# Update and install OS dependencies
RUN yum update -y \
    && yum install -y yajl-devel gcc gcc-c++ unzip \
    && yum clean all \
    && rm -rf /var/cache/yum

# Install the AWS AppConfig extension (needs to be downloaded beforehand with get-required-lambda-layers.sh)
# COPY .tmp/${ARCH}/aws_appconfig_extension.zip /tmp/
# RUN unzip /tmp/aws_appconfig_extension.zip -d /opt \
#     && rm -f /tmp/aws_appconfig_extension.zip

#WORKDIR ${LAMBDA_TASK_ROOT} 

# Install the function's dependencies using file requirements.txt
# from your project folder. If enabled, install Lambda Insights
COPY src/requirements.txt src/requirements-dev.txt ${LAMBDA_TASK_ROOT}/

# jsonslicer and pygrok have no wheel, add --use-pep517 https://github.com/pypa/pip/issues/8559
# https://github.com/AMDmi3/jsonslicer/issues/56
# if dev, install development dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    if [[ ${ENV} == "DEV" ]]; then \
        pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt --target "${LAMBDA_TASK_ROOT}" --use-pep517; \
    else \
        pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}" --use-pep517; \
    fi \
    && yum remove -y gcc gcc-c++ 

# Copy function code
COPY src ${LAMBDA_TASK_ROOT}

# Copy local configuration
ADD config ${LAMBDA_TASK_ROOT}/config

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app.lambda_handler" ]

# Bundle Lambda Insights extensions if enabled
FROM base AS deploy_lambda_insights_true
ARG ARCH
COPY .tmp/${ARCH}/aws_lambda_insights_extension.zip /tmp/
RUN unzip /tmp/aws_lambda_insights_extension.zip -d /opt \
    && rm -f /tmp/aws_lambda_insights_extension.zip

FROM base AS deploy_lambda_insights_false
# do nothing

# Generate final image based on whether Lambda Insights is enabled or not
ARG ENABLE_LAMBDA_INSIGHTS
FROM deploy_lambda_insights_${ENABLE_LAMBDA_INSIGHTS}
