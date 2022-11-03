# dynatrace-aws-s3-log-forwarder

This project deploys a Serverless architecture to forward logs from Amazon S3 to Dynatrace.

> **Note**
> This product is not officially supported by Dynatrace but maintained on a best effort basis

![Architecture](docs/images/architecture.jpg)

## Deployment instructions

### Prerequisites

You'll need the following software installed:

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* Docker Engine

You'll also need:

* A [Dynatrace access token](https://www.dynatrace.com/support/help/dynatrace-api/basics/dynatrace-api-authentication) for your tenant with the `logs.ingest` APIv2 scope.

### Deploy the solution

1. Create an AWS SSM SecureString Parameter with your Dynatrace access token to ingest logs. The SAM template that you will deploy will grant AWS Lambda permissions to access SSM parameters on the hierarchy `/dynatrace/s3-log-forwarder/${AWS::StackName}/*`. This allows you to have multiple deployments of the forwarder, each using its own DT access token securely stored. You can also configure a single forwarder to route logs to multiple Dynatrace instances. Create a parameter within the hierarchy for each of the Dynatrace instances needed. Example:

    ```bash
    export PARAMETER_NAME="/dynatrace/s3-log-forwarder/<my-stack-name>/my-dynatrace-instance-id/api-key"
    export PARAMETER_VALUE=your_dynatrace_api_key_here
    aws ssm put-parameter --name $PARAMETER_NAME --type SecureString --value $PARAMETER_VALUE
    ```

    **NOTE:** Your API Key is stored encyrpted with the default AWS-managed key alias: `aws/ssm`. If you want to use a Customer-managed Key, you'll need to grant Decrypt permissions to AWS Lambda.

1. Clone this repository.

1. Under the `config/log_forwarding_rules` folder, create a `<bucket_name>.yaml` file for each Amazon S3 bucket you want this Lambda function to forward logs to Dynatrace. On the rules file, add the log source (i.e. `aws`,`generic` or `custom`), a `prefix` with a regular expression for the log prefixes you want to forward to Dynatrace and add any user-defined annotations (attributes) you may want to add to the log entries. . The following is an example log forwarding configuration file:

    ```yaml
    - rule_name: fwd_ctral_and_elb_logs
      # Match any CloudTrail and ELB logs for any AWS account in this bucket
      prefix: "^AWSLogs/.*/(CloudTrail|elasticloadbalancing)/.*"
      source: aws
      annotations: 
        environment: dev
    - rule_name: fwd_jenkins_logs
      # Match any file prefixed with "jenkins/"" and ending in ".log"
      prefix: "^jenkins/.*(\\.log)$"
      source: generic
      annotations:
        log.source: jenkins
    - rule_name: fwd_application_logs
      # Match any file prefixed with "app/"" and ending in ".log"
      prefix: "^app/.*(\\.log)$"
      source: generic
      annotations:
        log.source: app1
    ```

    **Note:** Log forwarding rules serve 2 purposes: The first is giving you the ability to define custom annotations to add to your logs which its file name matches the regular expression defined on the "prefix" field. If you ingest logs as "generic" you can use these attributes as "matcher" to do log attribute extraction on Dynatrace with [log processing rules](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing). The second goal of prefixes is to provide finer grained file filtering compared to S3 notifications for files created, as wildcards are not supported in EventBridge rules. This gives you the ability to discard logs you may not want ingested on Dynatrace, without having to create multiple complex EventBridge rules if your bucket aggregates logs for multiple services and AWS Accounts. If you want to send all the logs matching the S3 Notification rules, simply add a single rule with prefix: ".*" and optionally any annotations you may want to add. You can find more info and advanced instructions on the [forwarding rules docs](docs/log_forwarding.md).

1. From the project root directory, execute the following command to build the Serverless application:

    ```bash
    sam build 
    ```

    **NOTE:** We are using a container image to build the AWS Lambda function. By default, we set the processor architecture to arm64 to build the container image for the dynatrace-aws-s3-log-forwarder. If you are building the function on an x86 machine and OS that doesn't support arm64 emulation, you can build an amd64 container image overriding the default value of the `ProcessorArchitecture` parameter.

    ```bash
    sam build --parameter-overrides ProcessorArchitecture=x86_64
    ```

1. Execute the following command to deploy the log forwarding solution. You'll be prompted for the required configuration parameters, e.g. your Dynatrace tenant(s) URL(s) and the SSM Parameter Name(s) storing your Dynatrace API key created on step 1 (currently the SAM template supports up to 2 Dynatrace tenants, you can simply extend it to more if needed)... **You'll be prompted for a stack name, make sure you use the same StackName you've used before to create the SSM Parameter (`my-stack-name` on the example of step 1)**. If you've built the container image for x86_64 architecture make sure you set the `ProcessorArchitecture` parameter to `x86_64` here too.

    ```bash
    sam deploy --guided
    ```

    **Note:** You will also be prompted for your e-mail address, so you'll receive notifications when log files can't be processed and messages are arriving to the Dead Letter Queue.

1. At this stage, you have successfully deployed the `dynatrace-aws-s3-log-forwarder` solution with your desired configuration. Now, for each Amazon S3 bucket you want to forward logs to Dynatrace, deploy the `s3-log-forwarder-bucket-config-template.yaml` CloudFormation template with appropriate parameters. This template provides IAM permissions to the log forwarding Lambda Function to read objects from your S3 buckets and creates an Amazon EventBridge rule to send "Object Created" notifications for the S3 bucket to the log forwarding solution Amazon SQS queue.

    The template takes as parameters the log forwarder stack name you have deployed before and the S3 bucket name as mandatory parameters. Optionally, you can specify between 1 and 10 Amazon S3 key prefixes. If S3 Key prefixes are defined, IAM permissions are narrowed down to only these prefixes, as well the EventBridge rule will only send notifications for objects created within the specified prefixes.

    For each S3 bucket, execute the AWS CLI command below (substituting relevant parameters):

    ```bash
    aws cloudformation deploy \
      --template-file s3-log-forwarder-bucket-config-template.yaml \
      --stack-name dynatrace-aws-s3-log-forwarder-s3-bucket-configuration-<your_bucket_name> \
      --parameter-overrides DynatraceAwsS3LogForwarderStackName=<name_of_your_log_forwarder_stack> \
          LogsBucketName=<s3_bucket_name> \
          LogsBucketPrefix1=<your_s3_prefix1>/ \
          LogsBucketPrefix2=<your_s3_prefix2>/ \
          (...)
          LogsBucketPrefix10=<your_s3_prefix10>/ \
      --capabilities CAPABILITY_IAM
    ```

    Once the above stack is deployed, go to your S3 bucket(s) and enable notifications via EventBridge following instructions [here](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-event-notifications-eventbridge.html).

### Next steps

At this stage, your deployment should be already ingesting logs to your Dynatrace tenant. For more detailed information and advanced configuration details, visit the documentation in the `docs` folder.
