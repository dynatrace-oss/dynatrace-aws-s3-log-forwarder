#!/bin/bash

# Deploy the dynatrace-aws-s3-log-forwarder for e2e validation.
# Usage: ./tests/e2e/deploy_forwarder.sh <layer|zip>

set -e

DEPLOY_TYPE="${1:?Usage: $0 <layer|zip>}"

TIMESTAMP_FORMAT='+%Y-%m-%dT%H:%M:%SZ'
log() {
    echo "[$(date -u "${TIMESTAMP_FORMAT}")] $*"
    return
}

log "Creating the SSM parameter"
aws ssm put-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                       --type SecureString --value $DT_TENANT_API_KEY

case "${DEPLOY_TYPE}" in
    zip)
        log "Building Lambda ZIP"
        ./scripts/build_docker.sh zip "dist/lambda.zip"

        log "Deploying the log forwarder template"
        aws cloudformation deploy --stack-name ${STACK_NAME} --parameter-overrides \
                        DynatraceEnvironment1URL=${DT_TENANT_URL} \
                        DynatraceEnvironment1ApiKeyParameter="/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key" \
                        EnableCrossRegionCrossAccountForwarding=true \
                        DeploymentPackageType=zip \
                        --template-file template.yaml --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
                        --role-arn ${CFN_ROLE_ARN}

        aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}

        FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} \
            --query 'Stacks[0].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
            --output text | rev | cut -d':' -f1 | rev)

        log "Updating Lambda function code for ${FUNCTION_NAME}"
        aws lambda update-function-code --function-name ${FUNCTION_NAME} \
            --zip-file "fileb://dist/lambda.zip"

        log "Waiting for function update to complete"
        aws lambda wait function-updated --function-name ${FUNCTION_NAME}
        ;;

    layer)
        LAYER_STACK_NAME="${STACK_NAME}-layer"

        log "Building Lambda Layer"
        ./scripts/build_docker.sh layer "dist/layer.zip"

        log "Packaging the Lambda Layer template"
        aws cloudformation package \
            --template-file dynatrace-aws-s3-log-forwarder-layer.yaml \
            --s3-bucket ${E2E_TESTING_BUCKET_NAME} \
            --s3-prefix cfn-packages/${STACK_NAME} \
            --output-template-file dist/packaged-layer.yaml \
            --role-arn ${CFN_ROLE_ARN}

        log "Deploying the Lambda Layer template"
        aws cloudformation deploy \
            --template-file dist/packaged-layer.yaml \
            --stack-name "${LAYER_STACK_NAME}" \
            --parameter-overrides \
                LayerName="dynatrace-aws-s3-log-forwarder-e2e" \
            --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
            --no-fail-on-empty-changeset \
            --role-arn ${CFN_ROLE_ARN}

        LAYER_ARN=$(aws cloudformation describe-stacks \
            --stack-name "${LAYER_STACK_NAME}" \
            --query "Stacks[0].Outputs[?OutputKey=='DynatraceS3LogForwarderLayerVersionArn'].OutputValue" \
            --output text)

        log "Layer ARN: ${LAYER_ARN}"

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
        ;;

    *)
        echo "ERROR: unknown deploy type '${DEPLOY_TYPE}'. Use 'layer' or 'zip'." >&2
        exit 1
        ;;
esac

log "Deploying the forwarder configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                --template-file dynatrace-aws-s3-log-forwarder-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}-configuration

log "Deploying the S3 bucket configuration template"
aws cloudformation deploy --stack-name ${STACK_NAME}-s3-bucket-configuration --parameter-overrides \
                DynatraceAwsS3LogForwarderStackName=${STACK_NAME} \
                LogsBucketName=${E2E_TESTING_BUCKET_NAME} \
                LogsBucketPrefix1=${E2E_TEST_PREFIX}/ \
                --capabilities CAPABILITY_IAM \
                --template-file dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml \
                --role-arn ${CFN_ROLE_ARN}

aws cloudformation wait stack-create-complete --stack-name ${STACK_NAME}-s3-bucket-configuration