# dynatrace-aws-s3-log-forwarder

This project deploys a Serverless architecture to forward logs from Amazon S3 to Dynatrace.

![Architecture](docs/images/architecture.jpg)

## Support

This project is officially supported by Dynatrace. Before you create a ticket check the documentation in the `docs` folder. If you didn't find a solution please [contact Dynatrace support](https://www.dynatrace.com/support/contact-support/).

## Supported AWS Services

The `dynatrace-aws-s3-log-forwarder` supports out-of-the-box parsing and forwarding of logs for the following AWS Services:

* AWS Elastic Load Balancing access logs ([ALB](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-access-logs.html), [NLB](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-access-logs.html) and [Classic ELB](https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/access-log-collection.html))
* [Amazon CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html) access logs
* [AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-examples.html) logs
* [AWS Global Accelerator](https://docs.aws.amazon.com/global-accelerator/latest/dg/monitoring-global-accelerator.flow-logs.html) Flow logs
* [Amazon Managed Streaming for Kafka](https://docs.aws.amazon.com/msk/latest/developerguide/msk-logging.html) logs
* [AWS Network Firewall](https://docs.aws.amazon.com/network-firewall/latest/developerguide/logging-s3.html) alert and flow logs
* [Amazon Redshift](https://docs.aws.amazon.com/redshift/latest/mgmt/db-auditing.html#db-auditing-manage-log-files) audit logs
* [Amazon S3 access logs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html)
* [Amazon VPC DNS query logs](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resolver-query-logs.html)
* [Amazon VPC Flow logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-s3.html) (default logs)
* [AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/logging-s3.html) logs
* [AWS AppFabric](https://docs.aws.amazon.com/appfabric/latest/adminguide/getting-started-security.html) OCSF-JSON logs (Raw-JSON logs require a custom processing rule)

Additionally, you can ingest any generic text and JSON logs. For more information, visit [docs/log_forwarding.md](docs/log_forwarding.md).

> [!IMPORTANT]
> Log events with timestamps older than 24 hours are dropped by Dynatrace (see [docs](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/log-monitoring-v2/post-ingest-logs#request-body-objects))

## Deployment

To deploy `dynatrace-aws-s3-log-forwarder` in your AWS account, follow the [deployment guide](docs/deployment_guide.md).

## Upgrade

To upgrade existing deployment of `dynatrace-aws-s3-log-forwarder` to latest version, follow the [upgrade guide](docs/upgrade_guide.md).
