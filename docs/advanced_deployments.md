# Advanced Deployments

This page contains guidance and considerations for large deployments.

## Log forwarding throughput

This solution has been tested to forward logs to Dynatrace at a throughput of 10 GB / min.

For high throughput scenarios you may need to adjust the `MaximumLambdaConcurrency` parameter. Look also at the [log_forwarding.md](log_forwarding.md#forwarding-large-log-files-to-dynatrace) documentation to understand how parameters influence the behavior of the log forwarding Lambda function.

## AWS Quotas to consider

### IAM Role Policy size limit

There's a hard-limit of the aggregate policy size of IAM policies in-line policies for an IAM role of 10,240 characters. The `dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml` CloudFormation template adds an in-line IAM policy to the IAM role used by AWS Lambda for each S3 bucket you configure to forward logs from. With the template provided as is, you can grant access to 20 - 25 Amazon S3 buckets (actual number will vary depending on bucket name size and whether or not you're restricting prefixes within the bucket(s)).

If you need to configure more S3 buckets, you may be able to optimize IAM policy space by building your own policy (the provided template is designed for ease of use, not scale). Also, if your buckets have common prefixes on their names, you can use wildcards on your policies to match multiple buckets with common prefix in the name.

For more details about this limit, check the IAM documentation [here](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html#reference_iam-quotas-entity-length).

### AWS AppConfig hosted configuration store size limit

By default, hosted configurations in AWS have a size limit of 1 MB. This limit can be adjusted upon request to AWS. For more information, visit the AWS AppConfig documentation [here](https://docs.aws.amazon.com/general/latest/gr/appconfig.html#limits_appconfig).

Note that, as we're managing the hosted configurations with CloudFormation passing configuration in-line, there's also [Cloudformation limits](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html) to take into account:

* Template body size in a request: 51,200 bytes: To use a larger template body, upload your template to Amazon S3.
* Template body size in an Amazon S3 Object: 1 MB

If your configuration is bigger than the above limits, you'll have to use S3-backed configurations. For more information, check the AWS AppConfig documentation [here](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile.html#appconfig-creating-configuration-and-profile-S3-source).
