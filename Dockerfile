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

FROM public.ecr.aws/lambda/python:3.9-${ARCH}

ARG ENV 
ARG ENABLE_LAMBDA_INSIGHTS

RUN yum update -y
RUN yum install -y yajl-devel gcc gcc-c++ unzip

# Copy function code
ADD src ${LAMBDA_TASK_ROOT}
WORKDIR ${LAMBDA_TASK_ROOT} 

# Install the function's dependencies using file requirements.txt
# from your project folder. If enabled, install Lambda Insights
RUN ./install_requirements.sh

# Install the AppConfig extension (needs to be downloaded beforehand)
# arm64:
#   aws lambda get-layer-version-by-arn \
#      --arn arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension-Arm64:15 \
#      | jq -r '.Content.Location' \
#      | xargs curl -o .tmp/appconfig-extension.zip  
# x86_64:
#   aws lambda get-layer-version-by-arn \
#      --arn arn:aws:lambda:us-east-1:027255383542:layer:AWS-AppConfig-Extension:82 \
#      | jq -r '.Content.Location' \
#      | xargs curl -o .tmp/appconfig-extension.zip  

COPY .tmp/appconfig-extension.zip extension.zip
RUN unzip extension.zip -d /opt \
    && rm -f extension.zip

RUN yum remove -y gcc gcc-c++ unzip

# Copy configuration
ADD config ${LAMBDA_TASK_ROOT}/config

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app.lambda_handler" ]
