# dynatrace-aws-s3-log-forwarder function metrics

The function publishes the following metrics to CloudWatch under a metric namespace named as your SAM StackName:

* `LogFilesProcessed` (Sum): Number of log files that have been correctly processed and ingested to Dynatrace.
* `LogProcessingFailures` (Sum): Number of failures processing log files. (If there's a failure, the function retries up to 3 times; so a single file failure may be 3 Failures here).
* `DroppedObjectsNotMatchingFwdRules` (Sum): Number of S3 objects that the function has received an ObjectCreated notification for, but that don't match any of the defined forwarded rules, so they've been dropped.
* `LogMessagesTrimmed` (Sum): Number of log messages trimmed due to hitting the Dynatrace limit.
* `ReceivedUncompressedLogFileSize`(Avg): Size in bytes of the uncompressed log file that's being processed.
* `DynatraceHTTP204Success` (Sum): Number of succesful POST requests to Dynatrace.
* `DynatraceHTTP200PartialSuccess` (Sum): Number of partially successful POST requests to Dynatrace.
* `DynatraceHTTP429Throttled` (Sum): Number of throttled POST requests to Dynatrace.
* `DynatraceHTTPErrors` (Sum): Number of HTTP errors received from Dynatrace (includding throttles).
* `UncompressedLogDTPayloadSize` (Avg / Min / Max): Size of the uncompressed Payload successfully posted to Dynatrace.
* `LogProcessingTime`(Avg / Min / Max): Time taken in seconds to process logs (iterate to generate attributes and trim, doesn't include batching and posting to Dynatrace).
* `DTIngestionTime` (Avg / Min / Max): Time taken to ingest the log file into Dynatrace (includes batching, compressing and POST'ing).

All the metrics above are produced with the `deployment` dimension which matches the given CloudFormation StackName, so if there're multiple deployments of the same function in the same AWS Account and Region, each function publishes its own set of metrics.
