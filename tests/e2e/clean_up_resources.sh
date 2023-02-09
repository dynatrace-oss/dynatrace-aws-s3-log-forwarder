 #!/bin/bash

set -v

# Export Lambda CloudWatch Logs to S3 and delete the Log Group
PREFIX="test/${TRAVIS_BUILD_ID}/lambda-logs"
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query \
                         'Stacks[].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
                         --output text | cut -d':' -f7)
TO_TIME=$(($(date +%s000) + 900000))
FROM_TIME=$(($TO_TIME - 3600000))

EXPORT_TASK_ID=$(aws logs create-export-task --destination ${E2E_TESTING_BUCKET_NAME} \
                    --destination-prefix ${PREFIX} \
                    --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}" \
                    --from ${FROM_TIME} \
                    --to ${TO_TIME} --query 'taskId' --output text)

echo "Exporting logs of AWS Lambda Function ${LAMBDA_FUNCTION_NAME}. Task: ${EXPORT_TASK_ID}"

for i in {1..10}; 
do
    EXPORT_STATUS=$(aws logs describe-export-tasks --task-id ${EXPORT_TASK_ID} --query 'exportTasks[].status.code' --output text)
    if [[ $EXPORT_STATUS == "COMPLETED" ]];
    then
        echo "Export task marked as completed. Allowing 1 minute before deleting Log group"
        sleep 60
        echo "Deleting log group /aws/lambda/${LAMBDA_FUNCTION_NAME}"
        aws logs delete-log-group --log-group-name "/aws/lambda/${LAMBDA_FUNCTION_NAME}"
        break
    fi
    sleep 6
done

if [ $EXPORT_STATUS != "COMPLETED" ]; then echo "CloudWatch Logs export task didn't finish within 1 minute. CloudWatch Log group not deleted."; fi

# 

echo "Deleting Cloudformation Stack ${STACK_NAME}-s3-bucket-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}-s3-bucket-configuration
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}-s3-bucket-configuration
echo "Deleting Cloudformation Stack ${STACK_NAME}-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}-configuration
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}-configuration
echo "Deleting Cloudformation Stack ${STACK_NAME}-s3-bucket-configutation"
aws cloudformation delete-stack --stack-name ${STACK_NAME}
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}
echo "Deleting SSM parameter /dynatrace/s3-log-forwarder/${STACK_NAME}/api-key"
aws ssm delete-parameter --name "/dynatrace/s3-log-forwarder/${STACK_NAME}/api-key"