# Advanced Deployments

This page contains guidance and considerations for large deployments.

## Building and deploying a Lambda Layer from source

If you want to build the Lambda Layer from source instead of using a pre-published Layer ARN, follow the steps below. This requires Python 3.14 + pip and [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html).

### 1. Build the Lambda Layer

From the project root directory:

```bash
bash scripts/build_layer.sh
```

This will:

1. Install pip dependencies for the target platform into `build/layer/python/`
2. Copy the application source code and license files
3. Produce a ZIP at `dist/dynatrace-aws-s3-log-forwarder-layer-x86_64.zip`

### 2. Deploy the Lambda Layer stack

Deploy the layer as its own CloudFormation stack:

```bash
sam deploy \
    --template-file dynatrace-aws-s3-log-forwarder-layer.yaml \
    --stack-name "${STACK_NAME}-layer" \
    --resolve-s3 \
    --capabilities CAPABILITY_IAM
```

### 3. Retrieve the deployed Layer ARN

```bash
export LAYER_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-layer" \
    --query "Stacks[0].Outputs[?OutputKey=='DynatraceS3LogForwarderLayerVersionArn'].OutputValue" \
    --output text)

echo "Layer ARN: $LAYER_ARN"
```

### 4. Deploy the main forwarder stack

Continue with the standard deployment from [Step 4a in the deployment guide](deployment_guide.md#step-4a-set-the-layer-arn), using the Layer ARN retrieved above.

### Updating the layer after code changes

After making source code changes, repeat steps 1–3 above to rebuild and redeploy the layer, then update the main stack with the new Layer ARN.

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
