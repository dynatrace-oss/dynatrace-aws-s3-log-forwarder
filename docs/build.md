# Build

If you're contributing to the project or if you want to build and deploy from source, the following sections cover how to build and deploy the `dynatrace-aws-s3-log-forwarder`.

There are two build options:

* **Lambda Layer** — built locally using pip (no Docker required). See `scripts/build_layer.sh`.
* **Lambda ZIP** — built inside a Docker container for binary compatibility. See `scripts/build_lambda_zip.sh`.

## Prerequisites

The deployment instructions are written for Linux/MacOS. If you are running on Windows, use the Linux Subsystem for Windows or use an [AWS Cloud9](https://aws.amazon.com/cloud9/) instance.

You'll need the following software installed:

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* Git

Additionally:

* **For Lambda Layer builds:** Python 3.14 + pip, [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* **For Lambda ZIP builds:** Docker Engine

You'll also need:

* A [Dynatrace access token](https://www.dynatrace.com/support/help/dynatrace-api/basics/dynatrace-api-authentication) for your tenant with the `logs.ingest` APIv2 scope.

## Building and deploying a Lambda Layer from source

If you want to build the Lambda Layer from source instead of using a pre-published Layer ARN, follow the steps below. This requires Python 3.14 + pip and the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

### Lambda Layer build details

From the project root directory:

```bash
bash scripts/build_layer.sh
```

This will:

* Install pip dependencies for the target platform into `build/layer/python/`
* Copy the application source code and license files
* Produce a ZIP at `dist/dynatrace-aws-s3-log-forwarder-layer-x86_64.zip`

### Lambda Layer deployment instructions

1. Package the layer template (uploads local artifacts to S3) and deploy it as its own CloudFormation stack:

    ```bash
    aws cloudformation package \
        --template-file dynatrace-aws-s3-log-forwarder-layer.yaml \
        --s3-bucket "${YOUR_S3_BUCKET}" \
        --s3-prefix "dynatrace-s3-log-forwarder-layer" \
        --output-template-file packaged-layer.yaml

    aws cloudformation deploy \
        --template-file packaged-layer.yaml \
        --stack-name "${STACK_NAME}-layer" \
        --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
    ```

1. Retrieve the deployed Layer ARN:

    ```bash
    export LAYER_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}-layer" \
        --query "Stacks[0].Outputs[?OutputKey=='DynatraceS3LogForwarderLayerVersionArn'].OutputValue" \
        --output text)

    echo "Layer ARN: $LAYER_ARN"
    ```

1. Deploy the main forwarder stack.

    Continue with the standard deployment from [Step 4a in the deployment guide](deployment_guide.md#step-4a-set-the-layer-arn), using the Layer ARN retrieved above.

### Updating the layer after code changes

After making source code changes, repeat steps 1-3 above to rebuild and redeploy the layer, then update the main stack with the new Layer ARN.

## Building and deploying a Lambda ZIP from source

### Lambda ZIP build details

The build script `scripts/build_lambda_zip.sh` runs entirely inside an Amazon Linux 2023 Docker container. It:

* Installs Python dependencies from `requirements.txt`
* Copies application source code, configuration files, and license files
* Installs and bundles the `libyajl.so.2` native library (required by the `ijson` `yajl2_c` backend for high-performance JSON streaming)
* Produces a ready-to-deploy Lambda ZIP package

At runtime, the `LD_LIBRARY_PATH` environment variable is set to `/var/task/lib` so the yajl library is found.

### Lambda ZIP deployment instructions

1. Clone the `dynatrace-aws-s3-log-forwarder` repository and checkout the latest version tag:

    ```bash
    export VERSION_TAG=$(curl -s https://api.github.com/repos/dynatrace-oss/dynatrace-aws-s3-log-forwarder/releases/latest | grep tag_name | cut -d'"' -f4)
    git clone https://github.com/dynatrace-oss/dynatrace-aws-s3-log-forwarder.git
    cd dynatrace-aws-s3-log-forwarder
    git checkout $VERSION_TAG
    ```

1. Define a name for your `dynatrace-aws-s3-log-forwarder` deployment name (e.g. mycompany-dynatrace-s3-log-forwarder) and your dynatrace tenant UUID (e.g. `abc12345` if your Dynatrace environment url is `https://abc12345.live.dynatrace.com`) in environment variables that will be used along the deployment process.

    ```bash
    export STACK_NAME=replace_with_your_log_forwarder_stack_name
    export DYNATRACE_TENANT_UUID=replace_with_your_dynatrace_tenant_uuid
    ```

    **IMPORTANT:** Your stack name should have a maximum of 53 characters, otherwise deployment will fail.

1. Create an AWS SSM SecureString Parameter to store your Dynatrace access token to ingest logs.

    ```bash
    export PARAMETER_NAME="/dynatrace/s3-log-forwarder/$STACK_NAME/$DYNATRACE_TENANT_UUID/api-key"
    # Configure HISTCONTROL to avoid storing on the bash history the commands containing API keys
    export HISTCONTROL=ignorespace
     export PARAMETER_VALUE=your_dynatrace_api_key_here
     aws ssm put-parameter --name $PARAMETER_NAME --type SecureString --value $PARAMETER_VALUE
    ```

    **NOTES:**
    * It's important that your parameter name follows the structure above, as the solution grants permissions to AWS Lambda to the hierarchy `/dynatrace/s3-log-forwarder/your_stack_name/*`
    * Your API Key is stored encyrpted with the default AWS-managed key alias: `aws/ssm`. If you want to use a Customer-managed Key, you'll need to grant Decrypt permissions to the AWS Lambda IAM Role that's deployed within the SAM template.

1. From the project root directory, execute the following command to build the Lambda deployment package:

    ```bash
    mkdir -p build
    ./scripts/build_lambda_zip.sh build/lambda.zip
    ```

    > [!NOTE]
    >
    > The build runs inside a Docker container. Make sure Docker is running before executing the build script.

1. Deploy the CloudFormation stack (this creates all infrastructure with a placeholder Lambda function):

    ```bash
    aws cloudformation deploy --stack-name $STACK_NAME \
               --template-file template.yaml \
               --parameter-overrides \
                    DynatraceEnvironment1URL="https://$DYNATRACE_TENANT_UUID.live.dynatrace.com" \
                    DynatraceEnvironment1ApiKeyParameter=$PARAMETER_NAME \
               --capabilities CAPABILITY_IAM
    ```

    If you want to customize deployment values, you can find the parameter descriptions on the [template.yaml](../template.yaml) file.

1. Update the Lambda function code with the built deployment package:

    ```bash
    FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
        --output text | rev | cut -d':' -f1 | rev)

    aws lambda update-function-code --function-name ${FUNCTION_NAME} \
        --zip-file fileb://build/lambda.zip
    ```

    If successfull, you'll see a JSON response with `"LastUpdateStatus": "InProgress"`.

    **NOTES:**
    * The e-mail address is set to receive alerts when log files can't be processed and messages are arriving to the Dead Letter Queue. If you don't want to receive those, just leave the parameter empty.
    * An Amazon SNS topic is created to receive monitoring alerts where you can subscribe HTTP endpoints to send the notification to your tools (e.g. PagerDuty, Service Now...).

1. The log forwarding Lambda function pulls configuration data from AWS AppConfig that contains the rules that defines how to forward and process log files. The `dynatrace-aws-s3-log-forwarder-configuration.yaml` CloudFormation template is designed to help get you started deploying the log forwarding configuration. It deploys a default "catch all" log forwarding rule that makes the log forwarding Lambda function process any S3 Object it receives an S3 Object Created notification for, and attempts to identify the source of the log, matching the object against supported AWS log sources. The log forwarder logic falls back to generic text log ingestion if it's unable to identify the log source:

    ```yaml
    ---
    bucket_name: default
    log_forwarding_rules:
      - name: default_forward_all
        # Match any file in your buckets
        prefix: ".*"
        # Process as AWS-vended log (automatic fallback to generic text log    ingestion if log is not
        source: aws
    ```

    You'll find this rule defined in-line on the CloudFormation template [here](dynatrace-aws-s3-log-forwarder-configuration.yaml#L60-L67), which you can modify and tailor it to your needs. To configure explicit log forwarding rules, visit  the [docs/log_forwarding.md](docs/log_forwarding.md) documentation.

    To deploy the configuration, execute the following command:

    ```bash
    aws cloudformation deploy \
        --template-file dynatrace-aws-s3-log-forwarder-configuration.yaml \
        --stack-name dynatrace-aws-s3-log-forwarder-configuration-$STACK_NAME \
        --parameter-overrides DynatraceAwsS3LogForwarderStackName=$STACK_NAME
    ```

    **NOTES:**
    * You can deploy updated configurations at any point in time, the log forwarding function will load them in ~1 minute after they've been deployed.
    * The log forwarder adds context attributes to all forwarded logs, including: `log.source.aws.s3.bucket.name`, `log.source.aws.s3.key.name` and `cloud.forwarder`. Additional attributes are extracted from log contents for supported AWS-vended logs.

1. At this point, you have successfully deployed the `dynatrace-aws-s3-log-forwarder` with your desired configuration. Now, you need to configure specific Amazon S3 buckets to send "S3 Object created" notifications to the log forwarder; as well as grant permissions to the log forwarder to read files from your bucket. For each bucket that you want to send logs from to Dynatrace, perform the below steps:

    * Go to your S3 bucket(s) configuration and enable S3 notifications via EventBridge following instructions [here](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-event-notifications-eventbridge.html).
    * Create Amazon EventBridge rules to send Object created notifications to the log forwarder. To do so, deploy the `dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml` CloudFormation template:

        ```bash
        export BUCKET_NAME=your-bucket-name-here

        aws cloudformation deploy \
            --template-file dynatrace-aws-s3-log-forwarder-s3-bucket-configuration.yaml \
            --stack-name dynatrace-aws-s3-log-forwarder-s3-bucket-configuration-$BUCKET_NAME \
            --parameter-overrides DynatraceAwsS3LogForwarderStackName=$STACK_NAME \
                                  LogsBucketName=$BUCKET_NAME \
            --capabilities CAPABILITY_IAM
        ```

        **NOTES:**
        * The S3 bucket must be on the same AWS account and region than where your log forwarder is deployed. For cross-region and cross-account deployments, check the [docs/log_forwarding.md](docs/log_forwarding.md) docs.
        * If you want to forward logs only for specific S3 prefixes, you can add up to 10 LogsBucketPrefix# parameter overrides (e.g. LogsBucketPrefix1=dev/ LogsBucketPrefix2=prod/ ...).
