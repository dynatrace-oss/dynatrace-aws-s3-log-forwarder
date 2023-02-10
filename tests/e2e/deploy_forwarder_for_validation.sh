#!/bin/bash

set -e

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Creating the SSM parameter"
# e2e tests: Deploy dynatrace-aws-s3-log-forwarder stack
aws ssm put-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                       --type SecureString --value $DT_TENANT_API_KEY

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deploying the log forwarder template"
aws cloudformation deploy --stack-name ${STACK_NAME} --parameter-overrides \
                DynatraceEnvironment1URL=${DT_TENANT_URL} \
                DynatraceEnvironment1ApiKeyParameter="/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                ContainerImageUri=${ECR_REPOSITORY_URL}/dynatrace-aws-s3-log-forwarder:${LAMBDA_ARCH}-${COMMIT} \
                EnableCrossRegionCrossAccountForwarding=true \
                ProcessorArchitecture=${LAMBDA_ARCH} \
                --template-file template.yaml --capabilities CAPABILITY_IAM \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete  --stack-name ${STACK_NAME}

# e2e tests: Deploy dynatrace-aws-s3-log-forwarder-configuration stack
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deploying the forwarder configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                --template-file dynatrace-aws-s3-log-forwarder-configuration.yaml  \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete  --stack-name ${STACK_NAME}-configuration

# Deploy the S3 Bucket Configuration stack
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deploying the S3 bucket configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-s3-bucket-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                LogsBucketName=${E2E_TESTING_BUCKET_NAME} \
                LogsBucketPrefix1=test/${TRAVIS_BUILD_ID}/validation/ \
                --capabilities CAPABILITY_IAM \
                --template-file dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}
        
aws cloudformation wait stack-create-complete  --stack-name ${STACK_NAME}-configuration