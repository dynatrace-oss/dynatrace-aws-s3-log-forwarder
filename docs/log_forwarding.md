# Log Forwarding rules

Log forwarding rules are stored within the `config/log_forwarding_rules` directory. You can also modify the location of log forarding rules declaring the environment variable `LOG_FORWARDING_RULES_PATH`. Each origin Amazon S3 bucket from which you want to forward logs from to Dynatrace requires a rule file within the directory with the format `<bucket_name>.yaml`. If the Lambda function receives an S3 Object created notification and the object S3 Key doesn't match any of the rules defined for the bucket, the object is dropped.

Log Forwarding rules allow you to define custom annotations you may want to add to your logs being forwarded from S3 as well as hinting the dynatrace-s3-log-forwarder whether these are AWS-vended logs (source:aws), generic logs (source: generic) or other logs that you've defined log processing rules for (source: custom). The `dynatrace-s3-log-forwarder` automatically annotates logs and extracts relevant attributes for supported AWS services with fields like `aws.account.id`, `aws.region`... The currently supported AWS-vended logs are:
* CloudTrail
* Application Load Balancer
* Network Load Balancer
* Classic Load Balancer

You can extend this functionality defining your own log processing rules. For more information, visit the [log_processing_rules](log_processing_rules.md).

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

You can still ingest non-supported AWS-vended logs. When you specify `aws` as source, S3 keys are matched against the known S3 key format for the supported service logs. If the S3 keys don't match the known formats, the solution will still forward the logs as generic logs (i.e. without enriching the log with attributes). You can also define your own log processing rules to extend the existing functionality. You can find more information on the [log_processing](log_processing.md) logs. 

If you're ingesting non-supported AWS-vended logs, we recommend you to configure the log source as `generic` so you can add a log.source annotation and use [Dynatrace log processing](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing) for attribute extraction.  Sample rule below:

    ```yaml
    - rule_name: fwd_vpc_flow_logs
      # Match any CloudTrail and ELB logs for any AWS account in this bucket
      prefix: "^AWSLogs/.*/(vpcflowlogs)/.*"
      source: generic
      annotations: 
        log.source: aws.vpcflowlogs
        environment: dev
    ```

With the above rule, you can then create a rule in your Dynatrace tenant log processing that extracts attributes for any logs with attribute `log.source: aws.vpcflowlogs`

The Log forwarding rules allow also for fine-grained content filtering with the prefix field, which is a regular expression matched against the Amazon S3 Key name of your logs. While Amazon EvenBridge rules allows you to narrow down the S3 Object Created notifications that are sent to the `dynatrace-s3-log-forwarder` to process; they don't allow for complex expressions (e.g. they don't support wildcard). See the [EventBridge documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns-content-based-filtering.html) for more details.  

For example, if you want to forward logs under the prefix `jenkins/` but only those log files with the `.log` extension, the narrowest Amazon EventBridge rule you can configure would be to get notifications for any file under `jenkins/*`. With a log forwarding rule, you can define a more specific rule that only matches files under `jenkins/` prefix but that have the `.log` extension, so the solution doesn't forward content of other files that may be under the same prefix:

    ```yaml
      source: custom
      # Match any file prefixed with "jenkins/"" and ending in ".log"
      prefix: "^jenkins/.*(\\.log)"
      annotations:
        log.source: jenkins
    ```

 If you want to send all the logs matching the S3 Notification rules, simply add a single rule with prefix: ".*". 

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
