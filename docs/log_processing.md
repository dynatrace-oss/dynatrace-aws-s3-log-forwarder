# Log Processing

Once a log S3 Object is marked to be forwarded to Dynatrace, its content is then pulled and processed before sending it to Dynatrace according to the defined log processing rules. Log processing rules, define attribute extraction and log enrichment directives.

The `dynatrace-s3-log-forwarder` supports processing plain text and JSON logs either gzipped or not. If the log is gzipped, its file extension must be `.gz`. If the log is in JSON format, the file extension must be `.json`.

For all processed logs, the forwarder enriches the entries with the following attributes:

* `log.source.forwarder`: the Amazon Resource Name (ARN) of the AWS Lambda function that shipped the log to Dynatrace
* `log.source.s3_bucket_name`: the name of the S3 bucket where the log comes from
* `log.source.s3_key_name`: the S3 key name the log comes from
* Any user-defined log attributes defined on the Log Forwarding Rule matched.

There are 3 different kinds of log processing rules:

* `generic`: Allows you to ingest any JSON or text log. When processed, logs are simply added the above attributes.
* `aws`: Allows you to ingest supported AWS-vended logs and extract relevant attributes for them. To determine the service vending the log and exact rule to apply, the S3 Key of the log object is matched against the known format. You can find the processing rules on the `src/processing/rules` folder with the details.
* `custom`: Allows you to ingest logs and apply user-defined processing rules. When using these rules, you also need to define the `source_name` attribute with the name that identifies your custom processing rule on the log_forwarding_rule.

If `aws` or `custom` is defined as source on the log_forwarding_rule and there're no matches against the processed log object, the dynatrace-s3-log-forwarder falls back to the `generic` processing rule.

## Built-in log processing rules

The solution currently supports log processing for:

* Amazon CloudTrail
* Amazon Classic Elastic Load Balancer
* Amazon Application Load Balancer
* Amazon Network Load Balancer

The processing rules for these logs are defined in `src/log/processing/rules`.

## Adding your own log processing rules

You can add your own log processing rules under `config/log_processing_rules` (or on a different location defined in the `LOG_PROCESSING_RULES_PATH` environment variable).

A log processing rule has the following format:

```yaml
name: Required[str]                   # --> name that uniquely identifies your processing rule
source: Required[str]                 # --> you'll normally use custom here, but valid values are 'custom', 'aws' and 'generic'
known_key_path_pattern: Required[str] # --> regular expression matching the file name pattern of your logs. To match anything, use "^.*$"
log_format: Required[str]             # --> valid values are 'text' or 'json'
log_entries_key: Optional[str]        # --> if your log is JSON and the entries are under a List inside the document, 
                                      #     put here the name of the JSON key containing the list of log entries. 
annotations: Optional[dict]           # --> key/value attributes to add to all log entries (e.g. log.source: nginx)
requester: Optional[List[str]]        # --> expected AWS Account ID pushing the logs (this field is not currently used, and it's for future se)
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
```
