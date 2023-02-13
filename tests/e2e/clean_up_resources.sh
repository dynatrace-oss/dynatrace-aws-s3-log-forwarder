 #!/bin/bash

# Settings for CloudWatch Log Export job
PREFIX="test/${TRAVIS_BUILD_ID}/lambda-logs"
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query \
                         'Stacks[].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
                         --output text | cut -d':' -f7)


export_cloudwatch_logs () {
    # Export Lambda Logs from AWS CloudWatch Logs to S3 and delete Lambda CloudWatch Log Group

    TO_TIME=$(($(date +%s%N)/1000000))
    FROM_TIME=$(($(date -d "-1 hours" +%s%N)/1000000))

    EXPORT_TASK_ID=$(aws logs create-export-task --destination ${E2E_TESTING_BUCKET_NAME} \
                        --destination-prefix ${PREFIX} \
                        --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}" \
                        --from ${FROM_TIME} \
                        --to ${TO_TIME} --query 'taskId' --output text)

    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Exporting logs of AWS Lambda Function ${LAMBDA_FUNCTION_NAME}. Task: ${EXPORT_TASK_ID}"

    for i in {1..10}; 
    do
        EXPORT_STATUS=$(aws logs describe-export-tasks --task-id ${EXPORT_TASK_ID} --query 'exportTasks[].status.code' --output text)
        if [[ $EXPORT_STATUS == "COMPLETED" ]];
        then
            echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Export task marked as completed. Allow 30 seconds before deleting Log Group."
            sleep 30
            echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deleting log group /aws/lambda/${LAMBDA_FUNCTION_NAME}"
            aws logs delete-log-group --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}"
            break
        fi
        sleep 6
    done

    if [ $EXPORT_STATUS != "COMPLETED" ]; then echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] CloudWatch Logs export task didn't finish within 1 minute. CloudWatch Log group not deleted."; fi

}

# Delete resources

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deleting Cloudformation Stack ${STACK_NAME}-s3-bucket-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}-s3-bucket-configuration
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}-s3-bucket-configuration
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deleting Cloudformation Stack ${STACK_NAME}-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}-configuration
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}-configuration
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deleting Cloudformation Stack ${STACK_NAME}-s3-bucket-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Deleting SSM parameter /dynatrace/s3-log-forwarder/${STACK_NAME}/api-key"
aws ssm delete-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key"
# Export CloudWatch Logs
export_cloudwatch_logs