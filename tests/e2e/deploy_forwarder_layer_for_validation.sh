#!/bin/bash

# Deploy the dynatrace-aws-s3-log-forwarder using the Lambda Layer path for e2e testing.

set -e

LAYER_STACK_NAME="${STACK_NAME}-layer"

TIMESTAMP_FORMAT='+%Y-%m-%dT%H:%M:%SZ'
log() {
    echo "[$(date -u "${TIMESTAMP_FORMAT}")] $*"
    return
}

log "Creating the SSM parameter"
aws ssm put-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                       --type SecureString --value $DT_TENANT_API_KEY

# Step 1: Build the Lambda Layer
log "Building Lambda Layer"
./scripts/build_docker.sh layer dist/layer.zip

# Step 2: Package and deploy the Lambda Layer stack
log "Packaging the Lambda Layer template"
# Note: template assumes that the layer.zip is available in `dist/layer.zip`
aws cloudformation package \
    --template-file dynatrace-aws-s3-log-forwarder-layer.yaml \
    --s3-bucket "${E2E_TESTING_BUCKET_NAME}" \
    --s3-prefix "test/${LAYER_STACK_NAME}" \
    --output-template-file packaged-layer.yaml

log "Deploying the Lambda Layer stack"
aws cloudformation deploy \
    --template-file packaged-layer.yaml \
    --stack-name "${LAYER_STACK_NAME}" \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --role-arn ${CFN_ROLE_ARN} \
    --no-fail-on-empty-changeset

aws cloudformation wait stack-create-complete --stack-name ${LAYER_STACK_NAME}

# Step 3: Retrieve the Layer ARN
LAYER_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${LAYER_STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='DynatraceS3LogForwarderLayerVersionArn'].OutputValue" \
    --output text)

log "Layer ARN: ${LAYER_ARN}"

# Step 4: Deploy the main forwarder stack with the layer
log "Deploying the log forwarder template (layer mode)"
aws cloudformation deploy --stack-name ${STACK_NAME} --parameter-overrides \
                DynatraceEnvironment1URL=${DT_TENANT_URL} \
                DynatraceEnvironment1ApiKeyParameter="/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                EnableCrossRegionCrossAccountForwarding=true \
                DeploymentPackageType=layer \
                DynatraceS3LogForwarderLayerArn="${LAYER_ARN}" \
                --template-file template.yaml --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}

# Step 5: Deploy the configuration stack
log "Deploying the forwarder configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                --template-file dynatrace-aws-s3-log-forwarder-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}-configuration

# Step 6: Deploy the S3 Bucket Configuration stack
log "Deploying the S3 bucket configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-s3-bucket-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                LogsBucketName=${E2E_TESTING_BUCKET_NAME} \
                LogsBucketPrefix1=${E2E_TEST_PREFIX}/ \
                --capabilities CAPABILITY_IAM \
                --template-file dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}-s3-bucket-configuration

