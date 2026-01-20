# Log Processing

Once a log S3 Object is marked to be forwarded to Dynatrace, its content is then pulled and processed before sending it to Dynatrace according to the defined log processing rules. Log processing rules, define attribute extraction and log enrichment directives.

The `dynatrace-aws-s3-log-forwarder` supports processing plain text and JSON logs (stream of JSON objects). It's possible to process gzipped logs, but the log file extension must be `.gz` or the S3 object needs to have `Content-Encoding` metadata set to `gzip`.

For all processed logs, the forwarder enriches the entries with the following contextual attributes:

* `log.source.forwarder`: the Amazon Resource Name (ARN) of the AWS Lambda function that shipped the log to Dynatrace
* `log.source.aws.s3.bucket.name`: the name of the S3 bucket where the log comes from
* `log.source.aws.s3.key.name`: the S3 key name the log comes from
* Any user-defined log attributes defined on the Log Forwarding Rule matched.

The processing rules are grouped into 3 main blocks (aka sources):

* `generic`: Allows you to ingest any text-formatted or stream of JSON objects log. When processed, logs are simply added the above attributes. You can use [Dynatrace log processing](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing) to do additional processing at ingestion time. For more information, look at the specific [section](log_processing.md#ingesting-logs-as-generic-and-perform-attribute-extraction-with-the-dynatrace-log-processing-pipeline) below.
* `aws`: Allows you to ingest supported AWS-vended logs and extract relevant attributes for them. To determine the service vending the log and exact rule to apply, the S3 Key of the log object is matched against the known format that AWS uses to deliver the logs. You can find the processing rules on the `src/processing/rules` folder with the details.
* `custom`: Allows you to ingest logs and apply user-defined processing rules. When using these rules, you also need to define the `source_name` attribute with the name that identifies your custom processing rule on the log_forwarding_rule.

If `aws` or `custom` is defined as source on the log_forwarding_rule and there're no matches against the processed log object, the dynatrace-aws-s3-log-forwarder falls back to the `generic` processing rule.

It's possible to define your own log-processing-rules by adding them to the log-processing-rules AWS AppConfig configuration profile. You can update the `dynatrace-aws-s3-log-forwarder` CloudFormation [template](../dynatrace-aws-s3-log-forwarder-configuration.yaml#L81) with your own log processing rules.

## Built-in log processing rules

### AWS-vended logs to Amazon S3

The list of supported AWS services is maintained [here](../README.md#supported-aws-services).

The processing rules for these services' logs are defined in `src/log/processing/rules`.

### Generic log ingestion

The solution provides a set of built-in processing rules for generic ingestion:

* `text`: Reads log entries line by line in text format. To use it, your Log Forwarding Rule need to include `source`: `generic`
* `json_stream`: Reads a stream of JSON objects, where each object is a log entry. To use it, your Log Forwarding Rule need to include `source`: `generic`, `source_name`: `generic_json_stream`)

## Ingesting logs as generic and perform attribute extraction with the Dynatrace Log Processing Pipeline

You can ingest any text and JSON-array logs into Dynatrace as generic logs and use the Dynatrace Log Processing pipeline to do attribute extraction. To showcase this, please see the step by step example below on how to ingest VPC Flow Logs from Amazon S3.

1. Configure an AWS VPC to publish flow logs to S3 following the instructions [here](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3.html).

1. Create a generic log forwarding rule for the S3 bucket where VPC Flow Logs are pushed in the log-forwarding-rules AWS AppConfig configuration profile. Add an annotation "log.source" with value "aws.vpcflowlogs" so we can use this field in Dynatrace to filtern and process these logs.

    ```yaml
    ---
    bucket_name: my_vpc_flow_logs-bucket
    log_forwarding_rules:
        - name: fwd_vpcflowlogs
          prefix: "^AWSLogs/.*/vpcflowlogs/.*"
          source: generic
          annotations: 
            log.source: aws.vpcflowlogs
    ```

1. If S3 Object created notifications are not yet configured for the bucket / prefix where VPC Flow Logs are delivered, deploy the `dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml` CloudFormation template with the details of your S3 bucket. Also, enable S3 Event Bridge notifications as per description [here](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-event-notifications-eventbridge.html).

1. On your Dynatrace tenant, go to Manage -> Settings -> Log Monitoring -> Log Processing and click on "Add processing rule". Fill your processing rule with the following data:

    **Processor name:** "AWS VPC Flow Logs"

    **Matcher:** matchesValue(log.source,"aws.vpcflowlogs")

    **Processor definition:**

    ```bash
    PARSE(content,"INT: version,SPACE,STRING: aws.account.id, SPACE,STRING: aws.eni.interfaceid,SPACE,(IPADDR: srcaddr | STRING),SPACE,(IPADDR: dstaddr|STRING),SPACE,(INT: srcport | STRING),SPACE,(INT: dstport|STRING),SPACE,(INT: protocol|STRING),SPACE,(INT: packets|STRING),SPACE,(INT: bytes|STRING),SPACE,TIMESTAMP('s'): timestamp,SPACE,TIMESTAMP('s'): end_time,SPACE,STRING: action,SPACE,STRING: log_status,EOL")
    ```

1. Click on the "Save Changes" button on the bottom-left corner.

At this stage, any logs ingested in your Dynatrace tenant with the attribute log.source == "aws.vpcflowlogs" will go through the pipeline to do attribute extraction. For more information, visit the [Dynatrace log processing documentation](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-monitoring/acquire-log-data/log-processing).

Note that you can also parse log entries directly on your queries without the need of processing using [Dynatrace Query Language](https://www.dynatrace.com/support/help/how-to-use-dynatrace/log-management-and-analytics/logs-on-grail-examples).

## Adding your own log processing rules

If you really need to do custom log processing on the AWS Lambda function, you can add your own log processing rules on the log-processing-rules AWS AppConfig configuration profile. You can update the rules modifying the `dynatrace-aws-s3-log-forwarder-configuration.yaml` CloudFormation [template](../dynatrace-aws-s3-log-forwarder-configuration.yaml#L81).

A log processing rule has the following format:

```yaml
---
name: Required[str]                       # --> name that uniquely identifies your processing rule
source: Required[str]                     # --> you'll normally use custom here, but valid values are 'custom', 'aws' and 'generic'
known_key_path_pattern: Required[str]     # --> regular expression matching the file name pattern of your logs. To match anything, use "^.*$"
log_format: Required[str]                 # --> valid values are 'text' (UTF-8) or 'json' (Array of JSON objects) or 'json_stream' (set of JSON objects)
filter_json_objects_key: Optional[str]    # --> valid only for json_stream processing. Filters log JSON objects with the specified key (value is mandatory if a key is specified)
filter_json_objects_value: Optional[str]  # --> valid only for json_stream processing. Filters log JSON objects with the specified value for the above key. 
log_entries_key: Optional[str]            # --> if your log is json or json_stream format and the entries are under a List inside a Key, 
                                          #     put here the name of the JSON key containing the list of log entries. 
annotations: Optional[dict]               # --> key/value attributes to add to all log entries (e.g. log.source: nginx)
requester: Optional[List[str]]            # --> expected AWS Account ID pushing the logs (this field is not currently used, and it's for future se)
attribute_extraction_from_key_name: Optional[dict]       # --> attribute_name: regular expression to apply to the S3 Key Name 
                                                         #     to extract an attribute. You can use pre-defined regular expressions 
                                                         #     in src/utils/helpers (e.g. {aws_account_id_pattern}, {aws_region_pattern})
                                                         #     e.g. if your S3 key is AWSLog/[aws account id]/[service]/[region]
                                                         #       aws.account.id: {aws_account_id_pattern}
                                                         #       aws.region: {aws_region_pattern}
attribute_extraction_grok_expression: Optional[str]      # --> Grok expression to apply to a text log to extract attributes
attribute_extraction_jmespath_expression: Optional[dict] # --> JMESPATH expressions to extract attributes from a JSON log 
                                                         #     if defined, jmespath expressions are applied after grok expressions
                                                         #
                                                         #     Example to map the 'eventTime' value in a JSON log, to 'timestamp' 
                                                         #     (recognized field in Dynatrace for event timestamp):
                                                         #       - timestamp: eventTime 
attribute_extraction_from_top_level_json: Optional[dict] # --> valid only for json_stream processing with array of log entries inside. Adds as attributes the defined JSON keys to 
                                                         #     all the log entries
attribute_mapping_from_json_keys: Optional[dict]         # --> (Experimental) Allows to define which original JSON keys should be converted into log attributes 
                                                         #     and whether a custom prefix/postfix should be appended to them.
                                                         #     It is especially useful when processing rule is used for different JSON schemas.
                                                         #
                                                         #     Set of JSON keys for further processing is configured by either one of the mandatory keys 'include'/'exclude'
                                                         #     Adding prefix or postfix to the keys is optional and can be configured by corresponding keys 'prefix'/'postfix'
                                                         #
                                                         #     Notes:
                                                         #     - As of now only top level attributes of JSON could be selected for the mapping.
                                                         #     - If defined, logic is applied after grok expressions.
                                                         #
                                                         #     Example:
                                                         #     Map the values of all keys except for 'exec_time' and 'process_time' in a JSON log. 
                                                         #     Additionally add custom prefix and postfix so that final attributes would match pattern 'my.*_mapped'
                                                         #
                                                         #     attribute_mapping_from_json_keys:
                                                         #        exclude: ['exec_time', 'process_time']
                                                         #        prefix: 'my.'
                                                         #        postfix: '_mapped'
```

You can find an example custom processing rule under `config/log-processing-rules.yaml` used to process [VPC DNS Query logs](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-query-logs.html) from AWS.

## Alternate IJSON parsing backend

The `dynatrace-aws-s3-log-forwarder` uses the [ijson](https://pypi.org/project/ijson/) library to parse JSON logs.
By default, it uses the fastest backend (yajl2_c). To switch to other backend for testing purposes set the environment variable `IJSON_BACKEND` to available [ijson backend](https://github.com/ICRAR/ijson?tab=readme-ov-file#backends) on the Lambda function configuration.
