# Extending the SAM template

You may need to ingest logs into more than 2 Dynatrace tenants. This document walks you through how to extend the provided SAM template to fit your needs.

## Adding additional Dynatrace tenants

The template supports forwarding logs to up to 2 Dynatrace tenants. Should you require to forward logs to more Dynatrace tenants, you can simply add additional Parameters and environment variables to the Lambda function.

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
