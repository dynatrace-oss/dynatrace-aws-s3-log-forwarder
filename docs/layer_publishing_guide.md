# Publishing the Lambda Layer

This guide covers how to build and publish the `dynatrace-aws-s3-log-forwarder` Lambda Layer, making it available for customers to use directly via a Layer ARN.

## Prerequisites

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* Python 3.14 + pip

## Step 1. Build the Lambda Layer

From the project root directory, run:

```bash
bash scripts/build_layer.sh
```

This will produce a ZIP at `dist/dynatrace-aws-s3-log-forwarder-layer-x86_64.zip`.

## Step 2. Publish the Layer

Lambda Layers are regional — a layer must be published in each region where customers will deploy. The publish script handles this automatically and grants public access to each published layer version.

### Publish to all commercial regions

```bash
bash scripts/publish_layer.sh
```

### Publish to specific regions

```bash
bash scripts/publish_layer.sh --regions us-east-1,eu-west-1,eu-central-1
```

The script will output the `LayerVersionArn` for each region — share the appropriate ARN with customers based on their deployment region.

### Manual publishing

Alternatively, you can publish manually:

```bash
aws lambda publish-layer-version \
    --layer-name dynatrace-aws-s3-log-forwarder \
    --zip-file fileb://dist/dynatrace-aws-s3-log-forwarder-layer-x86_64.zip \
    --compatible-runtimes python3.14 \
    --compatible-architectures x86_64 \
    --description "Dynatrace AWS S3 Log Forwarder"
```

Note the `LayerVersionArn` from the output — this is the ARN you'll share with customers.

## Step 3. Share the Layer ARN with customers

Provide customers with the full Layer Version ARN, for example:

```
arn:aws:lambda:us-east-1:123456789012:layer:dynatrace-aws-s3-log-forwarder:1
```

Customers can then deploy the log forwarder using the [Pre-published Lambda Layer](deployment_guide.md) option in the deployment guide — no build tools or SAM CLI required.

## Publishing a new version

When releasing an update:

1. Rebuild the layer: `bash scripts/build_layer.sh`
2. Publish new layer versions: `bash scripts/publish_layer.sh`
3. Communicate the new Layer Version ARNs to customers

> **Note:** Each `publish-layer-version` call creates a new immutable version. Previous versions remain available until explicitly deleted. Customers must update the `DynatraceS3LogForwarderLayerArn` parameter and redeploy to pick up the new version.









