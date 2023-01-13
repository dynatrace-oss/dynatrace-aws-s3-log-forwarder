# Log Forwarding rules

Log forwarding rules are stored within the `config/log_forwarding_rules` directory. You can also modify the location of log forarding rules declaring the environment variable `LOG_FORWARDING_RULES_PATH`. Each origin Amazon S3 bucket from which you want to forward logs from to Dynatrace requires a rule file within the directory with the format `<bucket_name>.yaml`. If the Lambda function receives an S3 Object created notification and the object S3 Key doesn't match any of the rules defined for the bucket, the object is dropped.

Log Forwarding rules allow you to define custom annotations you may want to add to your logs being forwarded from S3 as well as hinting the `dynatrace-aws-s3-log-forwarder` whether these are AWS-vended logs (source:aws), generic logs (source: generic) or other logs that you've defined log processing rules for (source: custom). The `dynatrace-aws-s3-log-forwarder` automatically annotates logs and extracts relevant attributes for supported AWS services with fields like `aws.account.id`, `aws.region`... The currently supported AWS-vended logs are:

* CloudTrail
* Application Load Balancer
* Network Load Balancer
* Classic Load Balancer

For any other logs you may want to ingest from S3, you can just ingest any text-based logs as `generic` logs (source: generic) and stream of JSON entries logs as `generic_json_stream` (source: generic, source_name: generic_json_stream). Then, you can [configure Dynatrace to process the logs at ingestion time](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing) to enrich them or parse them at query time with [DQL](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing/log-processing-commands). If you need extra-processing done on the Lambda function (e.g. extract log entries from a list in a JSON key), you can also extend the log processing functionality of this solution defining your own log processing rules. For more information, visit the [log_processing](log_processing.md) documentation.

## Configuring log forwarding rules

The format of a log forwarding rule is the following:

```yaml
- rule_name: Required[str]       # --> Name that identifies the rule
  prefix: Required[str]          # --> Regular expression that will be matched against each S3 Key name to determine whether the rule applies to it
  source: Required[str]          # --> valid values are 'aws', 'generic' or 'custom'
  source_name: Optional[str]     # --> this field is only required and used for 'custom' rules. 
  annotations: Optional[dict]    # --> contains user-defined key/value data to be added as attribute to the log entries
    key1: value
    key2: value
  sinks: Optional[list]          #--> list of dynatrace sink_ids to send these logs to. If not specified, default to sink '1'
    - '1'
    - '2'
```

As an example, if you consolidate logs under a single bucket for multiple accounts and services, the following rule would match any AWS supported log for any AWS account that logs to your bucket:

```yaml
- rule_name: fwd_ctral_and_elb_logs
  # Match any CloudTrail and ELB logs for any AWS account in this bucket
  prefix: "^AWSLogs/.*/(CloudTrail|elasticloadbalancing)/.*"
  sinks: 
    - '1'
    - '2'
  source: aws
  annotations: 
    environment: dev
```
  
With the above configuration, logs will be shipped to Dynatrace tenants configured on sinks `1` and `2` and log entries will have 'environment: dev' added as an attribute.

You can still ingest non-supported AWS-vended logs. When you specify `aws` as source, S3 keys are matched against the known S3 key format for the supported service logs. If the S3 keys don't match the known formats, the solution will still forward the logs as generic logs (i.e. without enriching the log with attributes).

If you're ingesting non-supported AWS-vended logs, we recommend you to configure the log source as `generic` so you can add a log.source annotation and use [Dynatrace log processing](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing) for attribute extraction. Sample rule below:

```yaml
- rule_name: fwd_vpc_flow_logs
  prefix: "^AWSLogs/.*/vpcflowlogs/.*"
  source: generic
  annotations: 
    log.source: aws.vpcflowlogs
```

With the above rule, you can then create a rule in your Dynatrace tenant log processing that extracts attributes for any logs with attribute `log.source: aws.vpcflowlogs`. For more information, check the details on the [log_processing](log_processing.md#ingesting-logs-as-generic-and-perform-attribute-extraction-with-the-dynatrace-log-processing-pipeline) docs.

The Log forwarding rules allow also for fine-grained content filtering with the prefix field, which is a regular expression matched against the Amazon S3 Key name of your logs. While Amazon EvenBridge rules allows you to narrow down the S3 Object Created notifications that are sent to the `dynatrace-aws-s3-log-forwarder` to process; they don't allow for complex expressions (e.g. they don't support wildcard). See the [EventBridge documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns-content-based-filtering.html) for more details.  

For example, if you want to forward logs under the prefix `jenkins/` but only those log files with the `.log` extension, the narrowest Amazon EventBridge rule you can configure would be to get notifications for any file under `jenkins/*`. With a log forwarding rule, you can define a more specific rule that only matches files under `jenkins/` prefix but that have the `.log` extension, so the solution doesn't forward content of other files that may be under the same prefix:

```yaml
  source: custom
  # Match any file prefixed with "jenkins/"" and ending in ".log"
  prefix: "^jenkins/.*(\\.log)"
  annotations:
    log.source: jenkins
```

If you want to send all the logs matching the S3 Notification rules, simply add a single rule with prefix: ".*".

## Forwarding large log files to Dynatrace

The `dynatrace-aws-s3-log-forwarder` solution is able to handle large log files as data is streamed in chunks from Amazon S3 as it's processed and forwarded to Dynatrace. Even if the solution is able to do this with very low memory footprint, allocating low memory to the function means also low CPU and bandwidth resources and your Lambda function execution may timeout (the configured lambda execution timeout configuration is 300 seconds). Note that the files are processed chunk by chunk sequentially as they're forwarded to Dynatrace (no threading). If you require ingesting large log files, increase the memory allocation of your Lambda function and if needed, increase the Lambda function execution timeout. If you increase the Lambda Execution timeout, make sure you also increase the `VisibilityTimeout` value on the SQS queue `S3NotificationsQueue` to a value slightly higher than the Lambda visibility timeout. For more information, refer to the AWS Lambda [documentation](https://docs.aws.amazon.com/lambda/latest/operatorguide/computing-power.html).

## Forward logs to multiple Dynatrace tenants

It is possible to send logs matching a single forwarding rule to multiple Dynatrace instances with the `sinks` attribute.

```yaml
- rule_name: fwd_ctral_and_elb_logs
  # Match any CloudTrail and ELB logs for any AWS account in this bucket
  prefix: "^AWSLogs/.*/(CloudTrail|elasticloadbalancing)/.*"
  source: aws
  sinks: 
    - '1'
    - '2'
  annotations: 
    environment: dev
```

The sink attribute contains a list of sink ids to forward logs to, each representing a Dynatrace instance. The template allows you to configure forwarding to up to 2 Dynatrace instances, although you can extend it for more (visit the [extending_sam_template](extending_sam_template.md) docs). The configuration for each Dynatrace instance is passed to the log forwarding Lambda function with 2 environment variables:

* DYNATRACE_{sink_id}_ENV_URL
* DYNATRACE_{sink_id}_API_KEY_PARAM

Please ensure that the SSM parameter identified by DYNATRACE_{sink_id}_API_KEY_PARAM exists (refer to section Deploy the solution).

For simplicity, the SAM template uses numeric {sink_id} identifiers (i.e. `DYNATRACE_1_ENV_URL`/`DYNATRACE_1_API_KEY_PARAM` and `DYNATRACE_2_ENV_URL`/`DYNATRACE_2_API_KEY_PARAM`), but you can use a string too to provide more meaningful identifiers. If you decide to use string identifiers though, you'll have to specify the `sinks` attribute on all the forwarding rules, since the default value when the attribute is not present is `1`.

## Forward logs from S3 buckets on different AWS regions

You may want to forward logs from S3 buckets in a different AWS region to the one where you have deployed the `dynatrace-aws-s3-log-forwarder`. To achieve this you have two options:

1. Deploy an instance of the `dynatrace-aws-s3-log-forwarder` on each AWS region where you have S3 buckets with logs.
2. Deploy Amazon EventBridge rules on the regions where the S3 buckets are to forward events to the AWS region where you deployed the `dynatrace-aws-s3-log-forwarder`.

Considering that all the AWS components used on the solution are serverless and only incur AWS costs if used (aka you won't pay for them if they're idle), option 1 is likely best if you're deployed across a small number of AWS regions.

If you have S3 buckets with logs across a large number of AWS regions, you may want to centralize log forwarding on a single AWS region to avoid the overhead of deploying and managing multiple S3 log forwarders. In this case, you will need to configure Amazon EventBridge rules on each region to forward S3 Object Created notifications for the required buckets to the default event bus on the AWS region where you have deployed the `dynatrace-aws-s3-log-forwarder`.

For each S3 bucket located in a different AWS region, follow the below steps:

1. Deploy the `eventbridge-cross-region-forward-rules.yaml` CloudFormation template. This template will deploy an Amazon EventBridge rule to forward S3 Object Created notifications for the bucket and optional prefixes defined, as well as a required IAM role for EventBridge to forward the notifications to the destination region. You can deploy the template executing the following command:

    ```bash
    aws cloudformation deploy \
      --template-file eventbridge-cross-region-forward-rules.yaml \
      --stack-name dynatrace-aws-s3-log-forwarder-cross-region-notifications-<name-of-your-s3-bucket> \
      --parameter-overrides DynatraceAwsS3LogForwarderAwsRegion=<aws-region-where-the-dynatrace-aws-s3-log-forwarder-is-deployed> \
          LogsBucketName=<name-of-your-s3-bucket> \
          LogsBucketPrefix1=<your_s3_prefix1>/ \
          LogsBucketPrefix2=<your_s3_prefix2>/ \
          ...
          LogsBucketPrefix10=<your_s3_prefix1>10/ \
      --capabilities CAPABILITY_IAM \
      --region <aws-region-where-the-s3-bucket-is>
    ```

    **NOTE:** LogBucketPrefix# parameters are optional. If you don't specify any, S3 Object Created notifications will be sent for any object created on the S3 bucket.

1. Once the above stack is deployed, go to your S3 bucket(s) and enable notifications via EventBridge following instructions [here](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-event-notifications-eventbridge.html).

1. Last, deploy the `s3-log-forwarder-bucket-config-template.yaml` CloudFormation template on the AWS region where the `dynatrace-aws-s3-log-forwarder` is deployed. This template will deploy the required local Amazon EventBridge rules to send the cross-region forwarded notifications to the S3 forwarder Amazon SQS queue, as well as grant IAM permissions to the AWS Lambda function to access your S3 bucket. If you have defined prefixes on the first step, make sure you specify the same prefixes when deploying this stack.

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
        --capabilities CAPABILITY_IAM \
        --region <region-where-your-s3-log-forwarder-instance-is-deployed>
      ```

1. Create a log forwarding rules configuration file for your bucket and deploy it.

**NOTE:** In this case you'll incurr cross-region data transfer costs between the region where AWS Lambda forwarder function runs and the region where the S3 bucket is located, on top of data transfer between AWS Lambda and the Dynatrace tenant. For more detailed information, check the [AWS Pricing website](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer).

## Forward logs from S3 buckets on different AWS accounts

On multi-account scenarios, you may want to centralize log forwarding to Dynatrace on a specific AWS account. In order to have the `dynatrace-aws-s3-log-forwarder` forwarding logs from a bucket in a different AWS, you need to configure the following (**IMPORTANT NOTE**: this example configuration and the CloudFormation templates provided use the default event bus of Amazon EventBridge. On a complex and large multi-account setup, you may want to create a dedicated Event bus for S3 log forwarding cross-account and cross-region):

1. The S3 bucket on the source AWS account must be configured with [ACLs disabled](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-ownership-existing-bucket.html), so you can use an S3 bucket policy to grant permissions to the log forwarder function IAM role on the central account. Your bucket policy will look like this:

    ```yaml
    {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowDTS3LogFwderAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<aws_account_id_where_the_log_forwarder_is>:role/<your_s3_log_forwarder_iam_role_name>"
            },
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::<bucket_name>/*"
            ]
        }
      ]
    }
    ```

    **NOTE:** If your S3 bucket has ACLs enabled, the above policy only takes effect for objects owned by the bucket owner. As AWS logs are delivered by AWS-owned accounts, who are the owners of the log objects, the permissions granted by the bucket policy don´t apply. Disabling ACLs should meet the wide majority of use cases. If you have ACLs enabled, read the [AWS documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-ownership-existing-bucket.html) carefully before disabling them. The `dynatrace-aws-s3-log-forwarder` doesn't support accessing buckets assuming an IAM role on the destination account.

1. You need to create a policy on the default event bus for Amazon EventBridge on the AWS account and region where the `dynatrace-aws-s3-log-forwarder` runs to grant permissions to the account where the bucket with the logs is to forward events. Follow the instructions [here](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-cross-account.html#eb-receiving-events-from-another-account). Your policy should look like the one below:

    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
      
          "Sid": "allow_account_to_put_events",
          "Effect": "Allow",
          "Principal": {
            "AWS": "<aws_account_id_where_the_s3_bucket_is>"
          },
          "Action": "events:PutEvents",
          "Resource": "arn:aws:events:<aws_region_where_the_forwarder_runs>:<aws_account_id_where_the_forwarder_runs>:event-bus/default"
        }
      ]
    }
    ```

    **NOTE:** If you have a large number of AWS accounts, you can permissions to all the AWS accounts in your AWS Organization with the aws:PrincipalOrgID condition:

    ```yaml
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "allow_all_accounts_from_organization_to_put_events",
          "Effect": "Allow",
          "Principal": "*",
          "Action": "events:PutEvents",
          "Resource": "arn:aws:events:<aws_region_where_your_log_forwarder_is>:<aws_account_id_where_your_log_forwarder_is>:event-bus/default",
          "Condition": {
            "StringEquals": {
              "aws:PrincipalOrgID": "<ORGANIZATION_ID>"
              }
          }
        }  
      ]
    }  
    ````

1. On the AWS account where the S3 bucket is, [enable S3 notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-event-notifications-eventbridge.html) to Amazon EventBridge on the bucket. Then create an EventBridge rule that forwards S3 Object Created notifications to the default event bus in the AWS account and region where the log forwarder is deployed. You can do so deploying the following CloudFormation template:

    ```yaml
    aws cloudformation deploy \
          --template-file eventbridge-cross-account-forward-rules.yaml \
          --stack-name dynatrace-aws-s3-log-forwarder-cross-account-notifications-<s3_bucket_name> \
          --parameter-overrides DynatraceAwsS3LogForwarderAwsRegion={aws-region} \
              DynatraceAwsS3LogForwarderAwsAccountId={aws_account_id} \
              LogsBucketName=<s3_bucket_name> \
              LogsBucketPrefix1=<your_s3_prefix1>/ \
              LogsBucketPrefix2=<your_s3_prefix2>/ \
              LogsBucketPrefix3=<your_s3_prefix3>/  \
              (...)
              LogsBucketPrefix10=<your_s3_prefix10>/ \
          --capabilities CAPABILITY_IAM \
          --region {region_of_your_s3-bucket}
    ```

1. Now, on the AWS account and region where the `dynatrace-aws-s3-log-forwarder` is running, deploy the `s3-log-forwarder-bucket-config-template.yaml` CloudFormation template to configure the local EventBridge rule to forward notifications to SQS for the log forwarder to pick them up.

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

1. Create a forwarding rules file on your log forwarder configuration with the required rules, and deploy it.
