# Update instructions

> [!IMPORTANT]
>
> Update of `dynatrace-aws-s3-log-forwarder` deployments to the latest version is supported from version `v0.4.4` and later.

## Prerequisites

The update instructions are written for Linux/MacOS. If you are running on Windows, use the Linux Subsystem for Windows, AWS CloudShell or an [AWS Cloud9](https://aws.amazon.com/cloud9/) instance.

You'll need the following software installed (already available in AWS CloudShell and AWS Cloud9):

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
* Docker Engine

## Update the dynatrace-aws-s3-log-forwarder

### Step 1. Review the GitHub release notes

Review the GitHub release notes for any additional required steps specific to the version you are updating to.

### Step 2. Find your deployment stack name

Find a name for your `dynatrace-aws-s3-log-forwarder` deployment and store in the `STACK_NAME` environment variable. The deployment contains several CloudFormation stacks.
Find name of the stack that do not start with `dynatrace-aws-s3-log-forwarder` prefix and has text `SAM Template to deploy the dynatrace-aws-s3-log-forwarder` in the description.

```bash
export STACK_NAME=<replace-with-your-log-forwarder-stack-name>
```

### Step 3. Note down the current version

Note down the current version you're using by checking the container image URI used in your deployment in case rollback is needed.

```bash
aws cloudformation describe-stacks --stack-name ${STACK_NAME} --query 'Stacks[0].Parameters[?ParameterKey==`ContainerImageUri`].ParameterValue' --output text
```

You'll see a response similar to the below example (version v0.5.8 in this case):

```bash
012345678901.dkr.ecr.us-east-1.amazonaws.com/dynatrace-aws-s3-log-forwarder:v5.8.0-x86_64
```

### Step 4. Set the version to update to

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

### Step 5. Get the latest `dynatrace-aws-s3-log-forwarder` image.

Pull the latest `dynatrace-aws-s3-log-forwarder` image from the Amazon ECR Public repository and push it to your private ECR repository, so it can be used by Lambda to update the function.

```bash
# Get private repo URI
export REPOSITORY_URI=$(aws ecr describe-repositories --repository-names dynatrace-aws-s3-log-forwarder --query 'repositories[0].repositoryUri' --output text)

# Pull the image
docker pull public.ecr.aws/dynatrace-oss/dynatrace-aws-s3-log-forwarder:${VERSION_TAG}-x86_64
docker tag public.ecr.aws/dynatrace-oss/dynatrace-aws-s3-log-forwarder:${VERSION_TAG}-x86_64 ${REPOSITORY_URI}:${VERSION_TAG}-x86_64

# ECR login and push image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(echo "$REPOSITORY_URI" | cut -d'/' -f1)
docker push ${REPOSITORY_URI}:${VERSION_TAG}-x86_64
```

### Step 6. Update the stack

Update the `dynatrace-aws-s3-log-forwarder` CloudFormation stack.

```bash
aws cloudformation deploy --stack-name ${STACK_NAME} --parameter-overrides \
            ContainerImageUri=${REPOSITORY_URI}:${VERSION_TAG}-x86_64 \
            --template-file template.yaml --capabilities CAPABILITY_IAM
```

If successfull, you'll see a message similar to the below at the end of the execution:

```bash
Successfully created/updated stack - dynatrace-s3-log-forwarder in us-east-1
```

## Rollback procedure

If you need to rollback to the previous version, repeat entire update procedure, but use the previous version (noted in Step 3) to set the `VERSION_TAG` environment variable in Step 4.
