# dynatrace-aws-s3-log-forwarder — Customer Self-Service Troubleshooting Guide

Self-diagnosable and self-fixable issues for the `dynatrace-aws-s3-log-forwarder` (container-image Lambda + SQS, deployed with CloudFormation, for Dynatrace Classic). Work through the section that matches your symptom before raising a support ticket.

> [!NOTE]
> This guide is for the `dynatrace-aws-s3-log-forwarder`. You are using it if your main stack has the parameters `DynatraceEnvironment1URL`, `DynatraceEnvironment1ApiKeyParameter` and `ContainerImageUri`. For the Dynatrace AWS Cloud Platform Monitoring forwarder (`dynatrace-aws-platform-monitoring-s3-log-forwarder`) use the troubleshooting guide in that repository instead — its deployment, token storage, notification options and defaults differ.

Throughout this guide, `<STACK_NAME>` is the name of your main forwarder CloudFormation stack. A deployment consists of several stacks:

| Stack | Purpose |
|-------|---------|
| `<STACK_NAME>` | Lambda function, SQS queue and DLQ, alarms, dashboard, AppConfig application |
| `dynatrace-aws-s3-log-forwarder-configuration-<STACK_NAME>` | Log forwarding and processing rules (AppConfig) |
| `dynatrace-aws-s3-log-forwarder-s3-bucket-configuration-<BUCKET_NAME>` | One per S3 bucket: EventBridge rule and read permissions |
| `dynatrace-aws-s3-log-forwarder-cross-region-notifications-<BUCKET_NAME>` / `...-cross-account-notifications-<BUCKET_NAME>` | Optional, cross-region and cross-account buckets |

---

## 1. CloudFormation Deployment Fails

### 1a. Missing `iam:PassRole` permission

**Symptom:** CloudFormation stack creation fails with an error mentioning `iam:PassRole`.

**Cause:** The IAM role or user running the deployment cannot pass the Lambda execution role that the stack creates.

**Fix:** Add permission to the IAM role/user running the deployment, scoped to the forwarder's Lambda execution role. Use the role ARN reported in the `iam:PassRole` error (or retrieve it from IAM); CloudFormation can shorten generated role names, so do not reconstruct the name from `<STACK_NAME>`.

In this example, `<generated-role-name-prefix>` is the actual role name with its final `-<random suffix>` removed. Only that suffix is wildcarded to allow the role to be recreated:

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole", "Resource": "arn:aws:iam::<account-id>:role/<generated-role-name-prefix>-*",
  "Condition": {
    "StringEquals": { "iam:PassedToService": "lambda.amazonaws.com" }
  }
}
```

The failed event in CloudFormation names every other action that is denied (see 1c). The deployment also needs permissions for CloudFormation, Lambda, SQS, SNS, EventBridge, CloudWatch, IAM, SSM, AppConfig and ECR.

---

### 1b. "Already exists" errors (SQS queues, event source mapping)

**Symptom:** Stack creation fails with an error saying a resource already exists — for example the queue `<STACK_NAME>-S3NotificationsQueue` or `<STACK_NAME>-S3NotificationsDLQ`, or a Lambda event source mapping.

**Cause:** The queues have fixed names derived from the stack name. A queue left over from an earlier deployment blocks stack creation, and AWS does not allow re-using a deleted queue name for about a minute. A manually created event source mapping for the forwarder's queue and function causes the same kind of error.

**Fix:**

1. **AWS Console → SQS** — look for `<STACK_NAME>-S3NotificationsQueue` and `<STACK_NAME>-S3NotificationsDLQ`. If they belong to a deleted or failed deployment and you no longer need them, delete them. If you deleted them just now, wait about 60 seconds
2. **AWS Console → Lambda → Additional Resources → Event Source Mappings** — delete mappings that point to `<STACK_NAME>-S3NotificationsQueue` and were not created by the stack
3. Wait until the resources are fully deleted, then re-run the CloudFormation deployment

---

### 1c. Other deployment errors — check CloudFormation events

**Symptom:** Stack creation or update fails (`CREATE_FAILED`, `UPDATE_FAILED`, `ROLLBACK_COMPLETE`) with an error not covered here.

**Fix:** The failure reason is in the stack events. Check it before raising a support ticket.

**AWS Console:**

1. **CloudFormation → Stacks → your stack → Events**
2. Look for the event labeled **Likely root cause** (the label is shown in the console only) and read its **Status reason**. See [Determine the root cause for CloudFormation stack failures](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/determine-root-cause-for-stack-failures.html)
3. A deployment consists of several stacks (table above) — check the stack that failed

**AWS CLI:**

List only the failed events of the latest operation (requires a recent AWS CLI v2):

```bash
aws cloudformation describe-events \
  --stack-name <STACK_NAME> \
  --filters FailedEvents=true \
  --query 'OperationEvents[].{Time:Timestamp,Resource:LogicalResourceId,Type:ResourceType,Status:ResourceStatus,Reason:ResourceStatusReason}' \
  --output table
```

Alternatively, list failed events with `describe-stack-events` (the CLI has no root cause label, so read from the oldest failure — later failures are usually side effects of the rollback):

```bash
aws cloudformation describe-stack-events \
  --stack-name <STACK_NAME> \
  --query 'reverse(StackEvents[?contains(ResourceStatus, `FAILED`)].{Time:Timestamp,Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason})' \
  --output table
```

If a stack was already deleted, use its stack ID (`arn:aws:cloudformation:...`) instead of the name. Include the failed event's resource, status and reason when you raise a support ticket.

---

### 1d. Lambda container image errors

**Symptom:** The stack fails while creating or updating `QueueProcessingFunction` with an error about the image — for example the image does not exist, Lambda cannot access the ECR image, or the image manifest/architecture is not supported. Or the function is created, but every invocation fails right away (for example `exec format error`).

**Cause and fix:** The Lambda function runs the container image from the parameter `ContainerImageUri`:

- The image tag must exist in **your private ECR repository**, in the **same AWS account and region** as the stack. Pushing it is part of the deployment ([deployment_guide.md](deployment_guide.md), step 4) and of every update ([update_guide.md](update_guide.md), step 5). Check in **ECR → Repositories → dynatrace-aws-s3-log-forwarder** that the tag exists
- The `ECR login` step in the guides uses `--region us-east-1`. If you deploy to another region, log in to your region instead, otherwise `docker push` fails
- The image architecture must match the `ProcessorArchitecture` parameter (`x86_64` by default). The tag suffix `-x86_64` / `-arm64` must match it. If you want to use arm64, pull and push the `-arm64` tag and set `ProcessorArchitecture=arm64` in the same update
- If Lambda reports it has no permission to access the ECR image, make sure the identity deploying the stack can read the image (for example `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`) and that the repository is not restricted by a repository policy

---

### 1e. Deployment is rejected or cannot be changed

| Error | Cause and fix |
|-------|---------------|
| `InsufficientCapabilities` / "requires capabilities" | Add `--capabilities CAPABILITY_IAM` to the deploy command (all stacks, including the per-bucket stacks). |
| Resource or role names too long | The stack name must be **at most 53 characters** (see the note in the deployment guide). Use a shorter `<STACK_NAME>`. |
| Parameter validation error on `DynatraceEnvironment1URL` | SaaS: `https://<tenant-id>.live.dynatrace.com`. Managed: `https://<activegate-domain>:9999/e/<environment-id>`. No trailing path or `/`. |
| Parameter validation error on `LogsBucketName` (per-bucket stack) | Enter the bucket name only (lowercase letters, digits, `-` and `.`), not an ARN or `s3://` URL. |
| `DynatraceLogIngestContentMaxLength` rejected | Valid values are 8192 to 1048576. |
| Cannot delete or change the main stack: "Export ... is in use" | The configuration stack and every per-bucket stack import values from the main stack. Delete (or update) those stacks first. Find the importers with `aws cloudformation list-imports --export-name <STACK_NAME>:AppConfigApplicationId` and `--export-name <STACK_NAME>:S3NotificationsQueueArn` |
| Per-bucket stack fails with "Maximum policy size of 10240 bytes exceeded" | Each per-bucket stack adds an inline policy to the Lambda role; about 20–25 buckets fit. See [advanced_deployments.md](advanced_deployments.md#iam-role-policy-size-limit) |
| Configuration stack fails because the template is too large | The rules are embedded in the CloudFormation template (limit 51,200 bytes). See [advanced_deployments.md](advanced_deployments.md#aws-appconfig-hosted-configuration-store-size-limit) |

---

## 2. Lambda Errors / No Logs Ingested

The notification flow is: S3 object created → **Amazon EventBridge** rule (one per bucket, from the per-bucket stack) → SQS queue `<STACK_NAME>-S3NotificationsQueue` → Lambda. Start with the [Lambda logs](#lambda-logs) and the SQS queue metrics (section 7). If the queue never receives messages, the problem is in the notification wiring (2b, 2c). If messages arrive but nothing is ingested, check 2a and 2d–2i, then sections 3–5.

### 2a. Lambda fails with `KeyError: 'body'` or `KeyError: 'detail'`

**Symptom:** The [Lambda logs](#lambda-logs) show a `KeyError: 'body'` or `KeyError: 'detail'` traceback, or `Received invalid event (missing or invalid "Records" field)`. The invocation fails, the messages of the whole batch are retried, and they land in the DLQ (section 5). Other messages in the same batch are retried too.

**Cause:** This forwarder understands only **S3 → EventBridge → SQS** messages. Anything else breaks the invocation:

- `KeyError: 'body'` — the Lambda has an extra trigger (for example a direct S3 trigger); such events carry no SQS message body
- `KeyError: 'detail'` — a message in the queue is not an EventBridge "Object Created" event, for example a direct S3 → SQS notification, an SNS message, or a test message sent to the queue

Messages whose body is not valid JSON are dropped with `Dropping message ..., body is not valid JSON`.

**Fix:**

1. **AWS Console → Lambda → your function → Configuration → Triggers** — only the SQS trigger for `<STACK_NAME>-S3NotificationsQueue` should be present. Remove any other trigger
2. Make sure only EventBridge rules from the per-bucket stacks send messages to the queue — direct S3 → SQS and SNS notifications are not supported by this forwarder
3. Remove the offending messages from the queue (or let them move to the DLQ and delete them there), then verify with a new test file

---

### 2b. S3 notifications do not reach the SQS queue

**Symptom:** No logs forwarded; the SQS queue `<STACK_NAME>-S3NotificationsQueue` receives no messages.

**Fix:** Check each part of the chain:

1. **EventBridge notifications are enabled on the bucket** (**S3 → your bucket → Properties → Amazon EventBridge → Edit → On**) — see [deployment_guide.md](deployment_guide.md#step-8-configure-s3-buckets-to-send-s3-object-created-notifications-to-the-log-forwarder)
2. **A per-bucket stack exists for the bucket** (`dynatrace-aws-s3-log-forwarder-s3-bucket-configuration-<BUCKET_NAME>`), deployed in the same account and region as the forwarder, with `DynatraceAwsS3LogForwarderStackName=<STACK_NAME>` and `LogsBucketName` spelled exactly like the bucket. Bucket names are case-sensitive and must be the bucket name only
3. **The EventBridge rule is enabled** (**EventBridge → Rules → default event bus**, rule name `<STACK_NAME>-<suffix>`) and its target is the SQS queue. The queue only accepts messages from rules whose name starts with `<STACK_NAME>-`
4. **Prefix parameters:** always fill `LogsBucketPrefix1` first. If `LogsBucketPrefix1` is empty, the rule matches **all** objects in the bucket, even when other prefixes are set. Prefixes should end with `/`. In the current template the EventBridge rule ignores `LogsBucketPrefix7` — use another `LogsBucketPrefix#` slot instead
5. The object was created after the rule and the bucket notifications were enabled — existing objects are not forwarded

---

### 2c. S3 bucket in a different region or AWS account

**Symptom:** No logs from buckets that are not in the forwarder's own region and account.

**Cause:** The per-bucket rule sends events to the **default event bus of the forwarder's account and region**, so a standard per-bucket stack works for buckets in the same account and region only.

**Fix:** Set up cross-region/cross-account forwarding — [log_forwarding.md](log_forwarding.md#forward-logs-from-s3-buckets-on-different-aws-regions). Checklist:

1. Main stack: `EnableCrossRegionCrossAccountForwarding=true`; for other accounts also `AwsAccountsToReceiveLogsFrom` — the list **replaces** the previous value, so include all accounts
2. Deploy `eventbridge-cross-region-or-account-forward-rules.yaml` in the bucket's region/account and enable EventBridge notifications on the bucket
3. Deploy the per-bucket stack in the forwarder's region with `S3BucketIsCrossRegionOrCrossAccount=true`
4. Cross-account only: the bucket policy allows the forwarder's Lambda role `s3:GetObject` (the stack output `QueueProcessingFunctionIamRole` is the role name; the ARN is `arn:aws:iam::<account-id>:role/<role-name>`), and the bucket has ACLs disabled
5. Add an explicit log forwarding rule for the bucket unless a `default` rule exists — see 2e

---

### 2d. Lambda cannot read the S3 objects (AccessDenied, KMS)

**Symptom:** The [Lambda logs](#lambda-logs) show `Error processing message <id>` with `AccessDenied` for S3 `GetObject`, or a KMS access denied / decryption error. The message is retried and eventually lands in the DLQ (section 5).

**Fix:**

1. The bucket needs its per-bucket stack — it attaches the policy `<per-bucket-stack-name>-ReadAccessToBucket` to the Lambda role (limited to the stack's prefixes). Cross-account buckets also need the bucket policy from 2c
2. If objects are encrypted with a customer-managed KMS key (SSE-KMS), grant the Lambda role `kms:Decrypt` on that key (this forwarder has no stack parameter for it), and make sure the key policy allows the role to use the key. The role name is in the main stack output `QueueProcessingFunctionIamRole`:

```bash
aws cloudformation describe-stacks --stack-name <STACK_NAME> \
  --query 'Stacks[].Outputs[?OutputKey==`QueueProcessingFunctionIamRole`].OutputValue' --output text
```

---

### 2e. Objects are dropped: no matching log forwarding rule

**Symptom:** The [Lambda logs](#lambda-logs) show `Dropping object. s3://<bucket>/<key> doesn't match any forwarding rule`; the metric `DroppedObjectsNotMatchingFwdRules` is above 0.

**Cause:** Forwarding rules live in AWS AppConfig and are deployed by the configuration stack. The provided template contains a catch-all `default` rule. If you removed it, objects from buckets without an explicit rule — or whose key matches none of the rules — are discarded. The rule `prefix` is a **regular expression** matched against the whole S3 key, and rules are evaluated in order (the first match wins).

**Fix:** Add or correct the rule in `LogForwardingRulesHostedConfiguration` in `dynatrace-aws-s3-log-forwarder-configuration.yaml` and redeploy the configuration stack ([deployment_guide.md](deployment_guide.md#step-7-deploy-the-log-forwarding-configuration)). Use `.*` as `prefix` for a catch-all. Do not edit the rules in the AppConfig console (the next CloudFormation deployment overwrites them). The change applies within about a minute. See [log_forwarding.md](log_forwarding.md).

---

### 2f. Lambda fails at start-up: cannot read the AppConfig configuration

**Symptom:** Every invocation fails. The [Lambda logs](#lambda-logs) show `Request to pull log-forwarding-rules from AWSAppConfig Lambda extension returned an error`, `... timed out`, or `Failed to connect to the AWS AppConfig Lambda extension endpoint`. Messages end up in the DLQ.

**Cause:** By default (`LogForwarderConfigurationLocation=aws-appconfig`) the Lambda reads its rules from AppConfig when it starts. This fails if the **configuration stack was never deployed** (step 7 of the deployment guide) — there is no configuration version to read — or if its deployment failed or was rolled back.

**Fix:**

1. Check that the stack `dynatrace-aws-s3-log-forwarder-configuration-<STACK_NAME>` exists and is in `CREATE_COMPLETE` / `UPDATE_COMPLETE`. If not, deploy it ([deployment_guide.md](deployment_guide.md#step-7-deploy-the-log-forwarding-configuration)) or fix its failure (1c)
2. After a successful deployment, wait about a minute and test again. If AppConfig is temporarily unreachable while the function is already running, the log shows `Unable to reload log-... rules from AWS AppConfig` and the previously loaded rules stay active

---

### 2g. Logs are ingested twice

**Cause:**

- More than one per-bucket stack exists for the same bucket (for example one without prefixes and one with prefixes), so several EventBridge rules send the same notification to the queue
- SQS delivers messages at least once, so occasional duplicates are possible

**Fix:** Use one per-bucket stack per bucket and add all prefixes to it (`LogsBucketPrefix1` … `LogsBucketPrefix10`).

---

### 2h. Objects are dropped: not readable as UTF-8 text

**Symptom:** The [Lambda logs](#lambda-logs) show `Error decoding log object. Log contains non-UTF-8 characters. Dropping object s3://<bucket>/<key>`; the metric `DroppedObjectsDecodingErrors` is above 0.

**Cause:** The forwarder processes UTF-8 text and JSON logs. Gzipped logs are supported only if the key ends in `.gz` or the object has `Content-Encoding: gzip` metadata. Binary formats are not text logs.

**Fix:** Have the log source deliver plain text/JSON (or gzip with a `.gz` extension), see [log_processing.md](log_processing.md). For AWS services, choose a supported output format (see 4b).

---

### 2i. Old log entries are not ingested

**Symptom:** Some or all entries of a file are missing in Dynatrace. The [Lambda logs](#lambda-logs) show `Parts of batch <n> were not successfully posted: ...` (HTTP 200 or 400 from Dynatrace); the metrics `DynatraceHTTP200PartialSuccess` or `DynatraceHTTP400InvalidLogEntries` are above 0.

**Cause:** Dynatrace drops log events with timestamps older than 24 hours (see the note in the [README](../README.md#supported-aws-services)). This happens when log files are delivered to S3 late, when old files are copied into the bucket, or when an outage kept notifications waiting. The text after the warning is the Dynatrace response and lists the rejected entries.

**Fix:** Not fixable on the forwarder side for old entries. Make sure new log files reach the bucket and are processed promptly (sections 2, 5). Other causes of rejected entries are shown in the same response text.

---

## 3. Dynatrace Token Issues (SSM Parameter Store)

The forwarder authenticates to Dynatrace with an **access token** that has the **`logs.ingest`** scope (Ingest logs, API v2). The token is stored in an AWS Systems Manager Parameter Store `SecureString` parameter, and the stack parameter `DynatraceEnvironment1ApiKeyParameter` holds the **name (path) of that parameter**, not the token. The Lambda reads the token with a cache of up to 2 minutes, so after changing it wait about 2 minutes before re-testing. See [deployment_guide.md](deployment_guide.md#step-2-create-an-aws-ssm-securestring-parameter-to-store-your-dynatrace-access-token-to-ingest-logs) for the original setup steps.

---

### 3a. Wrong parameter name, wrong format, or no access

**Symptom:** The [Lambda logs](#lambda-logs) show `AccessDeniedException ... ssm:GetParameter` or `ParameterNotFound`.

**Cause:** Common mistakes:

- **The parameter is outside the allowed path.** The Lambda role can read only parameters under `/dynatrace/s3-log-forwarder/<STACK_NAME>/`. Use `/dynatrace/s3-log-forwarder/<STACK_NAME>/<DYNATRACE_TENANT_UUID>/api-key`
- The stack parameter `DynatraceEnvironment1ApiKeyParameter` holds the raw token instead of the parameter name, or the name has no leading `/`
- The parameter is `String` instead of `SecureString`
- The stack still uses the template default for `DynatraceEnvironment1ApiKeyParameter` (`/dynatrace/s3-log-forwarder/dynatrace-aws-s3-log-forwarder/tenant/api-key`), which is valid only for a stack named `dynatrace-aws-s3-log-forwarder`

**Fix:**

```bash
aws ssm put-parameter \
  --name "/dynatrace/s3-log-forwarder/<STACK_NAME>/<DYNATRACE_TENANT_UUID>/api-key" \
  --type SecureString \
  --value "<your-dynatrace-access-token>" \
  --overwrite
```

If the parameter name in the stack was wrong, update the stack with the correct value, keeping all other parameters unchanged (the guides rely on this behavior of `aws cloudformation deploy`):

```bash
aws cloudformation deploy --stack-name <STACK_NAME> \
  --parameter-overrides DynatraceEnvironment1ApiKeyParameter=/dynatrace/s3-log-forwarder/<STACK_NAME>/<DYNATRACE_TENANT_UUID>/api-key \
  --template-file template.yaml --capabilities CAPABILITY_IAM
```

Use the `template.yaml` of the version you are running (see [update_guide.md](update_guide.md)).

---

### 3b. Token invalid, expired, revoked, or missing the required scope

**Symptom:** The [Lambda logs](#lambda-logs) show `There was a HTTP 401 error posting batch ...` (or 403), followed by the Dynatrace response — for example `Token is missing required scope. Use one of: logs.ingest`. Logs stop arriving in Dynatrace.

**Fix:**

1. In Dynatrace, **Access tokens** — check that the token is still valid (not expired or revoked) and has the **`logs.ingest`** scope
2. If not, create a new token with that scope
3. Store it in the parameter used by your stack (command in 3a, no redeploy needed)
4. Wait about 2 minutes for the token cache to expire, then check the Lambda logs again

---

### 3c. Parameter encrypted with a customer-managed KMS key

**Symptom:** Lambda cannot read the parameter; a KMS-related access error (`kms:Decrypt`, `AccessDeniedException`) appears in the [Lambda logs](#lambda-logs).

**Fix:** The parameter is encrypted with the AWS-managed key `aws/ssm` by default. If you used a customer-managed key, grant the Lambda execution role (stack output `QueueProcessingFunctionIamRole`, command in 2d) `kms:Decrypt` on it, and make sure the key policy allows the role to use the key.

---

### 3d. Lambda cannot reach Dynatrace (network, Managed, VPC)

**Symptom:** The [Lambda logs](#lambda-logs) show `Error pushing logs to Dynatrace` with a connection/read timeout (the forwarder waits 3 s to connect and 12 s for a response) or an SSL/TLS error.

**Fix:**

1. Verify `DynatraceEnvironment1URL` (format in 1e). For **Dynatrace Managed** use `https://<activegate-domain>:9999/e/<environment-id>`
2. If your ActiveGate is not publicly reachable (Managed), the Lambda must run in a VPC that can reach it: set `LambdaSubnetIds` (at least 2 subnets in different Availability Zones) and `LambdaSecurityGroupId`. The security group must allow outbound access to the ActiveGate, and the subnets need outbound connectivity to the Internet (for example a NAT gateway) so the Lambda can also reach AWS APIs (S3, SQS, SSM, AppConfig). See [deployment_guide.md](deployment_guide.md#step-6-deploy-the-cloudformation-stack)
3. If your ActiveGate uses a self-signed certificate, set `VerifyLogEndpointSSLCerts=false` (only for this case)
4. For Managed, also set `DynatraceLogIngestContentMaxLength=8192` (the default content length in Managed), otherwise longer entries are sent and rejected

---

## 4. Log Processing Rules Misconfiguration

### 4a. Custom processing rule is invalid or not applied

**Symptom:** Logs arrive without the expected parsing/enrichment. The [Lambda logs](#lambda-logs) show `Log processing rule N is invalid` (N is the position of the rule in the configuration, counting from 0), or `No matching log processing rule for custom.<name>. Defaulting to 'generic' log ingestion.`

**Cause:**

- An invalid rule (for example a missing required field or an invalid `source`) is skipped and logged; the other rules still load. Malformed YAML syntax aborts loading of the whole custom rule set.
- Custom processing rules are used only by log forwarding rules with `source: custom` whose `source_name` equals the processing rule `name`.
- Rule fields that exist only in the newer platform-monitoring forwarder (for example `header_line_prefix`) are not supported by this forwarder.

**Fix:**

1. Edit the rules in `LogProcessingRulesHostedConfiguration` in `dynatrace-aws-s3-log-forwarder-configuration.yaml`, then redeploy the configuration stack (not in the AppConfig console — direct edits are overwritten). The change applies within about a minute. `LogForwarderConfigurationLocation` must stay `aws-appconfig` (the default); with `local` the rules bundled in the image are used and cannot be changed
2. Start with a minimal valid rule and add fields incrementally. Required fields are `name`, `source`, `known_key_path_pattern` and `log_format`:

    ```yaml
    ---
    name: my-rule
    source: custom
    known_key_path_pattern: "^.*$"
    log_format: text
    ```

3. Reference it from a forwarding rule with `source: custom` and `source_name: my-rule`

See [log_processing.md](log_processing.md) for the full rule reference and [log_forwarding.md](log_forwarding.md) for forwarding rules.

---

### 4b. AWS service logs arrive without AWS attributes (ingested as generic)

**Symptom:** Logs arrive in Dynatrace but without parsed fields or attributes such as `aws.account.id` or `aws.service`. The [Lambda logs](#lambda-logs) show `Couldn't find a matching aws processing rule for <key>. Defaulting to generic ingestion.`

**Cause:** The forwarder recognizes the AWS service from the S3 key layout AWS uses when delivering logs (`AWSLogs/...`). Custom bucket prefixes, a changed key layout, an unsupported output format or an unsupported service are ingested as plain generic logs. Notes for this forwarder:

- **Organization-level CloudTrail** (`AWSLogs/o-<org-id>/<account-id>/CloudTrail/...`) is recognized from version **v0.4.6**. Older versions ingest it as generic logs — update ([update_guide.md](update_guide.md))
- CloudFront is supported for **standard logging (legacy)** only; CloudFront standard logging (v2) is not recognized
- VPC Flow Logs are supported in the default format only; AppFabric in OCSF-JSON only (Raw-JSON needs a custom processing rule)

**Fix:**

1. Deliver the logs with the default AWS key layout (no custom bucket prefix) and a supported output format
2. Check the list of supported AWS services in the [README](../README.md#supported-aws-services)
3. For layouts the built-in rules do not cover, ingest as `generic` and parse in Dynatrace, or add a custom processing rule with `attribute_extraction_from_key_name` (see 4a and [log_processing.md](log_processing.md))

---

## 5. Throttling, Timeouts and the Dead Letter Queue

Each S3 notification is received up to `MaximumSQSMessageRetries` times (template default **2**) before the message moves to the dead letter queue `<STACK_NAME>-S3NotificationsDLQ`. See [resiliency.md](resiliency.md).

### 5a. Dynatrace rejects or throttles requests

**Symptom:** One of these entries in the [Lambda logs](#lambda-logs), with the matching metric (section 7):

| Log message | Metric | What to do |
|-------------|--------|------------|
| `Throttled by Dynatrace. Exhausted retry attempts...` (`DynatraceThrottlingException`) | `DynatraceHTTP429Throttled` | Lower `MaximumLambdaConcurrency` (default 30) and reduce the volume forwarded (forwarding rules / per-bucket prefixes, sections 2e and 2b). Transient throttling clears on its own — the messages are retried or redriven (5c) |
| `Usable space limit reached. Exhausted retry attempts...` | `DynatraceHTTP503SpaceLimitReached` | The ActiveGate that receives the logs reports that its queue/space limit is reached. Lower `MaximumLambdaConcurrency` and wait; if you use your own Environment ActiveGate (Managed), check its health and disk. Then redrive the messages (5c). If it persists, raise a support ticket |
| `There was a HTTP 401/403 error posting batch...` | `DynatraceHTTPErrors` | Token problem — section 3 |
| `There was a HTTP <other> error posting batch...` | `DynatraceHTTPErrors` | The text after the message is the Dynatrace response. A 404 usually means a wrong `DynatraceEnvironment1URL` (1e, 3d) |
| `Error pushing logs to Dynatrace` | — | Connection problem — see 3d |

If it persists after these steps, raise a support ticket with the log excerpt.

### 5b. Lambda runs out of time on large files

**Symptom:** The [Lambda logs](#lambda-logs) show `Unable to process log file s3://... with remaining Lambda execution time`; the metric `NotEnoughExecutionTimeRemainingErrors` is above 0.

**Fix:** Update the stack parameters (descriptions in [template.yaml](../template.yaml), [log_forwarding.md](log_forwarding.md#forwarding-large-log-files-to-dynatrace)):

- Increase `LambdaMaximumExecutionTime` (default 300 s, maximum 900 s) and `LambdaFunctionMemorySize` (more memory also means more CPU and network bandwidth)
- Decrease `LambdaSQSMessageBatchSize` (default 4) for very large files
- Keep `SQSVisibilityTimeout` (default 420 s) greater than `LambdaMaximumExecutionTime`

### 5c. Messages in the dead letter queue

**Symptom:** You receive an e-mail from the CloudWatch alarm `<STACK_NAME>-MessagesInDLQ` (sent only if `NotificationsEmail` is set; the alarm publishes to the SNS topic `<STACK_NAME>-Alarms`, where you can add other subscribers), or the DLQ shows messages.

**Fix:**

1. Find the cause in the [Lambda logs](#lambda-logs) — search for `Error processing message` and for tracebacks — and fix it (sections 2–5)
2. **AWS Console → SQS → `<STACK_NAME>-S3NotificationsDLQ` → Start DLQ redrive** to the source queue, so the forwarder re-processes the messages — see [Configuring a dead-letter queue redrive](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html)

The DLQ keeps messages for **1 day**, and the main queue keeps unprocessed notifications for **12 hours**. Expired messages cannot be redriven, so fix problems promptly. Remember that entries older than 24 hours are rejected by Dynatrace (2i).

---

## 6. Security Vulnerabilities (CVEs)

The Lambda runs the container image you copied into your ECR repository, so findings (for example from ECR image scanning) relate to the base image and libraries of that image version. Before raising a support ticket:

1. Check [cve-status.dynatrace.com](https://cve-status.dynatrace.com) — the CVE may already be documented
2. Check [GitHub releases](https://github.com/dynatrace-oss/dynatrace-aws-s3-log-forwarder/releases) for a version that patches the vulnerability
3. Update to the latest release by following [update_guide.md](update_guide.md): pull the new image, push it to your ECR repository and update the stack with the new `ContainerImageUri`

---

## 7. General Debugging Tips

### Lambda logs

The forwarder's Lambda function (`QueueProcessingFunction` in the stack) writes its logs to **Amazon CloudWatch Logs**, in the log group `/aws/lambda/<function-name>` in the same AWS account and region as the stack. The function name is generated by CloudFormation (it looks like `<STACK_NAME>-QueueProcessingFunction-<random suffix>`).

1. **AWS Console → CloudFormation → your stack → Resources → `QueueProcessingFunction`** — the *Physical ID* is the function name
2. **AWS Console → CloudWatch → Logs → Log groups** → open `/aws/lambda/<function-name>` (or use the **Monitoring** tab of the Lambda function → **View CloudWatch logs**)
3. Open the most recent log stream, or use **Search all log streams** / **Logs Insights** to filter for `ERROR`, `Exception` or a specific S3 object key

From the CLI:

```bash
# Get the function name
FUNCTION_NAME=$(aws cloudformation describe-stack-resource \
  --stack-name <STACK_NAME> \
  --logical-resource-id QueueProcessingFunction \
  --query 'StackResourceDetail.PhysicalResourceId' --output text)

# Show the last hour of logs and keep following new entries
aws logs tail "/aws/lambda/${FUNCTION_NAME}" --since 1h --follow

# Show only errors from the last 24 hours
aws logs tail "/aws/lambda/${FUNCTION_NAME}" --since 24h --filter-pattern "?ERROR ?Exception"
```

If the log group does not exist, the function has not run yet (no messages reached the SQS queue — see section 2) or the Lambda execution role cannot write to CloudWatch Logs.

**Enable debug logging:**

1. **AWS Console → Lambda → your function → Configuration → Environment variables**
2. Set `LOGGING_LEVEL` to `DEBUG` (or set the `LambdaLoggingLevel` CloudFormation parameter, so a redeploy doesn't reset it)
3. Reproduce the problem and read the new entries in the [Lambda log group](#lambda-logs); reset to `INFO` afterwards to avoid extra CloudWatch Logs costs

**Use the CloudWatch monitoring dashboard:**

The main stack can deploy a CloudWatch dashboard named `<STACK_NAME>-monitoring-dashboard`. It shows log files processed, Dynatrace API responses (including throttling), processing and ingestion times, SQS queue and DLQ message counts, Lambda executions, and Lambda logs, which makes it the quickest way to see where logs stop flowing.

1. Find the dashboard link in the **Outputs** tab of the main stack (`CloudWatchDashboardURL`), or open **AWS Console → CloudWatch → Dashboards**
2. Or get the link from the CLI:

```bash
aws cloudformation describe-stacks \
  --stack-name <STACK_NAME> \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchDashboardURL`].OutputValue' \
  --output text
```

**The dashboard may be disabled.** It is deployed only when the `DeployCloudWatchMonitoringDashboard` parameter is `true` (the default). If it is `false`, the `CloudWatchDashboardURL` output is missing and no dashboard exists.

- To enable it, update the stack with `DeployCloudWatchMonitoringDashboard=true` and keep all other parameter values unchanged (see [update_guide.md](update_guide.md))
- Without the dashboard you can still see the same data: the forwarder publishes its metrics to the CloudWatch namespace `dynatrace-aws-s3-log-forwarder` (dimension `deployment` = your stack name) regardless of this setting. Browse them in **CloudWatch → Metrics**, and check the SQS queue and DLQ metrics directly. See [function_metrics.md](function_metrics.md) for the metric list

**Metrics worth checking** (namespace `dynatrace-aws-s3-log-forwarder`, dimension `deployment` = `<STACK_NAME>`):

| Metric | Meaning | See |
|--------|---------|-----|
| `LogFilesProcessed` | Files ingested successfully | — |
| `LogProcessingFailures` | Processing failures (retried, then DLQ) | 5c |
| `LogFilesSkipped` | Files skipped (no usable processing rule or sink) | 4a |
| `DroppedObjectsNotMatchingFwdRules` | Objects with no matching forwarding rule | 2e |
| `DroppedObjectsDecodingErrors` | Objects that are not valid UTF-8 text | 2h |
| `NotEnoughExecutionTimeRemainingErrors` | Lambda timed out on a file | 5b |
| `DynatraceHTTP200PartialSuccess`, `DynatraceHTTP400InvalidLogEntries` | Dynatrace rejected some entries | 2i |
| `DynatraceHTTP429Throttled`, `DynatraceHTTP503SpaceLimitReached`, `DynatraceHTTPErrors` | Dynatrace rejected requests | 5a, 3b |

For the SQS queue `<STACK_NAME>-S3NotificationsQueue` and the DLQ, look at `NumberOfMessagesSent` and `ApproximateNumberOfMessagesVisible`.

**Verify end-to-end flow:**

1. Upload a test file to a source S3 bucket that is configured for forwarding (per-bucket stack deployed, EventBridge notifications enabled)
2. Check SQS queue metrics — message count should rise then drop (processed)
3. Check the [Lambda log group](#lambda-logs) in CloudWatch Logs (`/aws/lambda/<function-name>`) for the invocation
4. Search Dynatrace for logs from that file, for example in a Notebook (Grail) — on tenants without Grail use the Logs viewer and filter on the same attributes:

```text
fetch logs
| filter log.source.aws.s3.bucket.name == "<BUCKET_NAME>"
| filter log.source.aws.s3.key.name == "<OBJECT_KEY>"
```
