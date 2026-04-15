#!/bin/bash

# Copyright 2024 Dynatrace LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#      https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Publish the Lambda Layer to one or more AWS regions with public access.
# Assumes the layer has already been built with build_layer.sh.
#
# Usage:
#   ./scripts/publish_layer.sh                                             # All commercial regions
#   ./scripts/publish_layer.sh --regions us-east-1,eu-west-1,eu-central-1  # Specific regions

set -e

LAYER_NAME="dynatrace-aws-s3-log-forwarder"
ZIP_FILE="dist/dynatrace-aws-s3-log-forwarder-layer-x86_64.zip"
REGIONS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --regions)
            IFS=',' read -ra REGIONS <<< "$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --regions <r1,r2,...>  Publish to a comma-separated list of regions."
            echo "                        If not specified, publishes to all commercial regions."
            echo "  --help                Show this help message."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
done

# Default to all enabled commercial regions if none specified
if [ ${#REGIONS[@]} -eq 0 ]; then
    echo "Querying available AWS regions..."
    REGIONS=($(aws ec2 describe-regions \
        --query "Regions[].RegionName" \
        --output text))
fi

if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: $ZIP_FILE not found. Run build_layer.sh first."
    exit 1
fi

echo "Publishing Lambda Layer: $LAYER_NAME"
echo "ZIP file: $ZIP_FILE"
echo "Regions: ${REGIONS[*]}"
echo ""

FAILED_REGIONS=()

for REGION in "${REGIONS[@]}"; do
    echo "--- Publishing to $REGION ---"

    PUBLISH_OUTPUT=$(aws lambda publish-layer-version \
        --region "$REGION" \
        --layer-name "$LAYER_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --compatible-runtimes python3.14 \
        --compatible-architectures x86_64 \
        --description "Dynatrace AWS S3 Log Forwarder (x86_64)" \
        --output json 2>&1) || {
        echo "  FAILED to publish in $REGION"
        FAILED_REGIONS+=("$REGION")
        continue
    }

    LAYER_VERSION_ARN=$(echo "$PUBLISH_OUTPUT" | grep -o '"LayerVersionArn": "[^"]*"' | cut -d'"' -f4)
    LAYER_VERSION=$(echo "$PUBLISH_OUTPUT" | grep -o '"Version": [0-9]*' | grep -o '[0-9]*')

    echo "  Published: $LAYER_VERSION_ARN"

    # Grant public access
    aws lambda add-layer-version-permission \
        --region "$REGION" \
        --layer-name "$LAYER_NAME" \
        --version-number "$LAYER_VERSION" \
        --statement-id allow-all-accounts \
        --principal "*" \
        --action lambda:GetLayerVersion \
        --output json > /dev/null 2>&1 && \
    echo "  Public access granted." || \
    echo "  WARNING: Failed to grant public access."

    echo ""
done

# Summary
echo "=== Publishing Summary ==="
echo "Regions attempted: ${#REGIONS[@]}"
echo "Failed: ${#FAILED_REGIONS[@]}"

if [ ${#FAILED_REGIONS[@]} -gt 0 ]; then
    echo "Failed regions: ${FAILED_REGIONS[*]}"
    exit 1
fi

echo "All regions published successfully."







