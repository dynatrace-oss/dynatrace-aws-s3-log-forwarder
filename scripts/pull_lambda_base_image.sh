#!/bin/bash

set -ev

# Build dev image with dev requirements
docker pull public.ecr.aws/lambda/python:${LAMBDA_BASE_IMAGE_TAG}
export BASE_CONTAINER_IMAGE_SHA256=$(docker inspect --format='{{index .RepoDigests 0}}' public.ecr.aws/lambda/python:${LAMBDA_BASE_IMAGE_TAG})
echo "Building Lambda container image from tag ${LAMBDA_BASE_IMAGE_TAG} --> ${BASE_CONTAINER_IMAGE_SHA256}"