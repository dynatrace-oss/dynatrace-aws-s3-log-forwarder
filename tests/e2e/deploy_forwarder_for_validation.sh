#!/bin/bash

set -e

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Creating the SSM parameter"
# e2e tests: Deploy dynatrace-aws-s3-log-forwarder stack
aws ssm put-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                       --type SecureString --value $DT_TENANT_API_KEY

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Building Lambda ZIP"
mkdir -p build
./scripts/build_lambda_zip.sh build/lambda.zip

# Step 1: Deploy CloudFormation template (with inline dummy function code)
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deploying the log forwarder template"
aws cloudformation deploy --stack-name ${STACK_NAME} --parameter-overrides \
                DynatraceEnvironment1URL=${DT_TENANT_URL} \
                DynatraceEnvironment1ApiKeyParameter="/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                EnableCrossRegionCrossAccountForwarding=true \
                DeploymentPackageType=zip \
                --template-file template.yaml --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}

# Step 2: Update Lambda function code with the built ZIP (using local artifact)
FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
    --output text | rev | cut -d':' -f1 | rev)

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Updating Lambda function code for ${FUNCTION_NAME}"
aws lambda update-function-code --function-name ${FUNCTION_NAME} \
    --zip-file fileb://build/lambda.zip

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Waiting for function update to complete"
aws lambda wait function-updated --function-name ${FUNCTION_NAME}

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
                LogsBucketPrefix1=${E2E_TEST_PREFIX}/ \
                --capabilities CAPABILITY_IAM \
                --template-file dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}
        
aws cloudformation wait stack-create-complete  --stack-name ${STACK_NAME}-s3-bucket-configuration
