# Update instructions

> [!IMPORTANT]
>
> Update of `dynatrace-aws-s3-log-forwarder` deployments to the latest version is supported from version `v0.4.4` and later.

## Prerequisites

The update instructions are written for Linux/MacOS. If you are running on Windows, use the Linux Subsystem for Windows, AWS CloudShell or an [AWS Cloud9](https://aws.amazon.com/cloud9/) instance.

You'll need the following software installed (already available in AWS CloudShell and AWS Cloud9):

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

## Update the dynatrace-aws-s3-log-forwarder

### Step 1. Review the GitHub release notes

Review the GitHub release notes for any additional required steps specific to the version you are updating to.

### Step 2. Find your deployment stack name

Find a name for your `dynatrace-aws-s3-log-forwarder` deployment and store in the `STACK_NAME` environment variable. The deployment contains several CloudFormation stacks.
Find name of the stack that do not start with `dynatrace-aws-s3-log-forwarder` prefix and has text `SAM Template to deploy the dynatrace-aws-s3-log-forwarder` in the description.

```bash
export STACK_NAME=<replace-with-your-log-forwarder-stack-name>
```

### Step 3. Set the version to update to

Set the `VERSION_TAG` environment variable to the latest release version tag of `dynatrace-aws-s3-log-forwarder`.

```bash
# Get the latest version
export VERSION_TAG=$(curl -s https://api.github.com/repos/dynatrace-oss/dynatrace-aws-s3-log-forwarder/releases/latest | grep tag_name | cut -d'"' -f4)
```

> [!Note]
>
> If you want to update to specific version, set the `VERSION_TAG` variable to that version (e.g. `v0.5.8`).
>
> ```bash
> export VERSION_TAG=v0.5.8
> ```

### Step 4. Download the latest templates and Lambda package

Download the CloudFormation templates and the Lambda deployment package for the version you're updating to:

```bash
mkdir -p dynatrace-aws-s3-log-forwarder-templates && cd "$_"
wget https://dynatrace-aws-s3-log-forwarder-assets.s3.amazonaws.com/${VERSION_TAG}/templates.zip
unzip -o templates.zip
```

### Step 5. Update the stack and Lambda function code

Update the `dynatrace-aws-s3-log-forwarder` CloudFormation stack:

```bash
aws cloudformation deploy --stack-name ${STACK_NAME} \
            --template-file template.yaml --capabilities CAPABILITY_IAM
```

Then update the Lambda function code with the new deployment package:

```bash
FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} \
    --query 'Stacks[0].Outputs[?OutputKey==`QueueProcessingFunction`].OutputValue' \
    --output text | rev | cut -d':' -f1 | rev)

aws lambda update-function-code --function-name ${FUNCTION_NAME} \
    --zip-file fileb://lambda.zip
```

If successfull, you'll see a message similar to the below at the end of the execution:

```bash
Successfully created/updated stack - dynatrace-s3-log-forwarder in us-east-1
```

## Rollback procedure

If you need to rollback to the previous version, repeat entire update procedure, but use the previous version to set the `VERSION_TAG` environment variable in Step 3.
