 #!/bin/bash

set -v

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