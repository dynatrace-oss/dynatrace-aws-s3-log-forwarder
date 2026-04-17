# Publishing the Lambda Layer

This guide covers how to build and publish the `dynatrace-aws-s3-log-forwarder` Lambda Layer, making it available for customers to use directly via a Layer ARN.

## Prerequisites

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* Docker Engine

## Step 1. Build the Lambda Layer

From the project root directory, run:

```bash
./scripts/build_docker.sh layer dist/layer-x86_64.zip --arch x86_64
```

## Step 2. Publish the Layer

Lambda Layers are regional — a layer must be published in each region where customers will deploy. The publish script handles this automatically and grants public access to each published layer version.

### Publish to all commercial regions

```bash
./scripts/publish_layer.sh --x86_64 dist/layer-x86_64.zip --arm64 dist/layer-arm64.zip
```

### Publish to specific regions

```bash
./scripts/publish_layer.sh --x86_64 dist/layer-x86_64.zip --arm64 dist/layer-arm64.zip --regions us-east-1,eu-west-1,eu-central-1
```

The script will output the `LayerVersionArn` for each region — share the appropriate ARN with customers based on their deployment region.

### Manual publishing

Alternatively, you can publish manually:

```bash
# x86_64
aws lambda publish-layer-version \
    --layer-name dynatrace-aws-s3-log-forwarder \
    --zip-file fileb://dist/layer-x86_64.zip \
    --compatible-runtimes python3.14 \
    --compatible-architectures x86_64 \
    --description "Dynatrace AWS S3 Log Forwarder (x86_64)"

# arm64
aws lambda publish-layer-version \
    --layer-name dynatrace-aws-s3-log-forwarder \
    --zip-file fileb://dist/layer-arm64.zip \
    --compatible-runtimes python3.14 \
    --compatible-architectures arm64 \
    --description "Dynatrace AWS S3 Log Forwarder (arm64)"
```

Note the `LayerVersionArn` from the output — this is the ARN you'll share with customers.

## Step 3. Share the Layer ARN with customers

Provide customers with the full Layer Version ARN, for example:

```text
arn:aws:lambda:us-east-1:123456789012:layer:dynatrace-aws-s3-log-forwarder:1
```

Customers can then deploy the log forwarder using the [Lambda Layer](deployment_guide.md) option in the deployment guide — no build tools or SAM CLI required.

## Publishing a new version

When releasing an update:

1. Rebuild: `./scripts/build_docker.sh layer dist/layer-x86_64.zip` and `./scripts/build_docker.sh layer dist/layer-arm64.zip --arch arm64`
2. Publish: `./scripts/publish_layer.sh --x86_64 dist/layer-x86_64.zip --arm64 dist/layer-arm64.zip`
3. Communicate the new Layer Version ARNs to customers

> **Note:** Each `publish-layer-version` call creates a new immutable version. Previous versions remain available until explicitly deleted. Customers must update the `DynatraceS3LogForwarderLayerArn` parameter and redeploy to pick up the new version.
