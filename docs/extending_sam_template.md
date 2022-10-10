# Extending the SAM template

You may need to ingest logs from additional Amazon S3 buckets or ship logs to more Dynatrace instances. This document walks you through how to extend the provided SAM template to fit your needs.

## Ingesting logs from additional S3 buckets

If you want to consume logs from additional S3 buckets you'll need to modify the SAM template to allow for additional S3 buckets. To do so, replicate the following CloudFormation objects:

* Parameters:

  ```yaml
  Parameters:
    LogsBucketXName:
      Description: "Name of the Amazon S3 bucket where your logs are to be consumed."
      Type: String
      AllowedPattern: "^[0-9a-z]+([0-9a-z-]{1,61}[0-9a-z])$"
    LogsBucketXPrefix:
      Description: "Prefix for S3 log object keys that you want to forward to Dynatrace (e.g. \"AWSLogs/\"). If you want to send notifications for all  objects created in the bucket, leave this value empty."
      Type: String
      Default: ""
      ...
  ```

* Resources:

  ```yaml
  Resources:
    ...
    LambdaS3BucketXAccessIAMPolicy:
      Type: AWS::IAM::Policy
      Properties:
        PolicyName: !Sub ${AWS::StackName}-ReadAccessBucketX
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Sid: "AllowReadAccessToBucketX"
              Effect: Allow
              Action:
                - s3:GetObject
                - s3:GetBucketLocation
                - s3:GetObjectVersion
              Resource:
                - !Join
                    - ":"
                    - - arn
                      - !Ref AWS::Partition
                      - s3
                      - ""
                      - ""
                      - !Ref LogsBucketXName
                - !Join
                    - ":"
                    - - arn
                      - !Ref AWS::Partition
                      - s3
                      - ""
                      - ""
                      - !Sub ${LogsBucketXName}/${LogsBucketXPrefix}*
        Roles: 
          - !Ref QueueProcessingFunctionRole
      
    LogsBucketXEventBridgeRule:
      Type: AWS::Events::Rule
      Properties:
        Name: !Sub ${AWS::StackName}-LogsBucketX-to-SQS
        EventBusName: default
        State: ENABLED
        EventPattern:
          source:
            - "aws.s3"
          detail-type:
            - "Object Created"
          detail:
            bucket:
              name: 
                - !Ref LogsBucketXName
            object:
              key:
              - prefix: !Ref LogsBucketXPrefix
        Targets:
          - Id: "SQSQueue"
            Arn: !GetAtt S3NotificationsQueue.Arn
    ...
  ```

For testing purposes you can add more buckets manually:

  1. Enable EventBridge notifications on your Bucket. Then Create an Amazon EventBridge rule that forwards "Object Created" events to the Amazon SQS queue that has been created by the CloudFormation stack. You'll see the Queue ARN on the outputs section of the SAM deploy command output. You can find instructions [here](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-targets.html). Sample `EventPattern` below:

      ```json
      {
        "source": ["aws.s3"],
        "detail-type": ["Object Created"],
        "detail": {
          "bucket": {
            "name": ["bucket_name"]
          },
          "object": {
            "key": [{
              "prefix": "AWSLogs/<account_id>/<service>/"
            }]
          }
        }
      }
      ```

      **Note:** Make sure your EventBridge rule name starts with {name_of_your_cfn_stack}-name_of_your_rule. The SQS queue policy allows any rule starting with {name_of_your_cfn_stack}-* prefix. Otherwise, you'll need to modify the queue policy to add additional permissions.

  1. Grant the following additional IAM permissions to the IAM Role of the Lambda function:

      * `s3:getObject` and `s3:getObjectVersion` permissions to the lambda function to access your bucket objects.
      * `s3:GetBucketLocation` permissions to your S3 bucket.

## Adding additional Dynatrace instances

The template supports forwarding logs to up to 2 Dynatrace instances. Should you require to ship logs to more Dynatrace instances, you can simply add additional Parameters and environment variables to the Lambda function.

* Parameters:

  ```yaml
  DynatraceEnvironmentXURL:
    Description: URL of your Dynatrace environment.
    Type: String
  DynatraceEnvironmentXApiKeyParameter:
    Description: Name of the SecureString Parameter in AWS Parameter Store storing the Dynatrace Environment 2 API Key.
    Type: String
    Default: ""
  ```

* Add additional environment variables to the Lambda function:

  ```yaml
  QueueProcessingFunction:
    Type: AWS::Serverless::Function
    Metadata:
      DockerTag: test
      DockerContext: .
      Dockerfile: Dockerfile
    Properties:
      PackageType: Image
      MemorySize: !Ref LambdaFunctionMemorySize
      Environment:
        Variables:
          DYNATRACE_1_ENV_URL: !Ref DynatraceEnvironment1URL
          DYNATRACE_1_API_KEY_PARAM: !Ref DynatraceEnvironment1ApiKeyParameter
          DYNATRACE_2_ENV_URL: !If [ SecondDTEnvironmentSpecified, !Ref DynatraceEnvironment2URL, !Ref "AWS::NoValue"]
          DYNATRACE_2_API_KEY_PARAM: !If [ SecondDTEnvironmentSpecified, !Ref DynatraceEnvironment2ApiKeyParameter, !Ref "AWS::NoValue"]
          DYNATRACE_X_ENV_URL: !Ref DynatraceEnvironmentXURL
          DYNATRACE_X_API_KEY_PARAM: !Ref DynatraceEnvironmentXApiKeyParameter
          QueueName: !GetAtt S3NotificationsQueue.QueueName
  ```
