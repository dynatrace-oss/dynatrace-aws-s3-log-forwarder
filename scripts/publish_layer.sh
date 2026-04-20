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

# Publish the Lambda Layer (both x86_64 and arm64) to one or more AWS regions with public access.
# Assumes both layers have already been built with build_docker.sh layer.
#
# Usage:
#   ./scripts/publish_layer.sh --x86_64 <zip> --arm64 <zip>                                             # All commercial regions
#   ./scripts/publish_layer.sh --x86_64 <zip> --arm64 <zip> --regions us-east-1,eu-west-1,eu-central-1  # Specific regions

set -e

LAYER_NAME="dynatrace-aws-s3-log-forwarder"
ZIP_X86_64=""
ZIP_ARM64=""
REGIONS=()

IDX=1
while [[ $IDX -le $# ]]; do
    case "${!IDX}" in
        --x86_64)
            IDX=$((IDX + 1))
            ZIP_X86_64="${!IDX:?--x86_64 requires a value}"
            ;;
        --arm64)
            IDX=$((IDX + 1))
            ZIP_ARM64="${!IDX:?--arm64 requires a value}"
            ;;
        --regions)
            IDX=$((IDX + 1))
            IFS=',' read -ra REGIONS <<< "${!IDX:?--regions requires a value}"
            ;;
        *)
            echo "Unknown option: ${!IDX}"
            echo "Usage: $0 --x86_64 <zip> --arm64 <zip> [--regions r1,r2,...]"
            exit 1
            ;;
    esac
    IDX=$((IDX + 1))
done

[[ -n "$ZIP_X86_64" ]] || { echo "Error: --x86_64 is required." >&2; exit 1; }
[[ -n "$ZIP_ARM64"  ]] || { echo "Error: --arm64 is required."  >&2; exit 1; }

# Default to all enabled commercial regions if none specified
if [[ ${#REGIONS[@]} -eq 0 ]]; then
    echo "Querying available AWS regions..."
    REGIONS=($(aws ec2 describe-regions \
        --query "Regions[].RegionName" \
        --output text))
fi

for ZIP_FILE in "$ZIP_X86_64" "$ZIP_ARM64"; do
    if [[ ! -f "$ZIP_FILE" ]]; then
        echo "Error: $ZIP_FILE not found. Run build_docker.sh layer first." >&2
        exit 1
    fi
done

echo "Publishing Lambda Layer: $LAYER_NAME"
echo "x86_64 ZIP: $ZIP_X86_64"
echo "arm64  ZIP: $ZIP_ARM64"
echo "Regions: ${REGIONS[*]}"
echo ""

FAILED_REGIONS=()

publish_arch() {
    local region="$1"
    local zip_file="$2"
    local arch="$3"

    LAYER_VERSION_ARN=$(aws lambda publish-layer-version \
        --region "$region" \
        --layer-name "$LAYER_NAME" \
        --zip-file "fileb://$zip_file" \
        --compatible-runtimes python3.14 \
        --compatible-architectures "$arch" \
        --description "Dynatrace AWS S3 Log Forwarder ($arch)" \
        --query 'LayerVersionArn' \
        --output text 2>&1) || {
        echo "  FAILED to publish $arch in $region"
        return 1
    }

    LAYER_VERSION=$(echo "$LAYER_VERSION_ARN" | grep -o '[0-9]*$')
    echo "  Published ($arch): $LAYER_VERSION_ARN"

    if aws lambda add-layer-version-permission \
        --region "$region" \
        --layer-name "$LAYER_NAME" \
        --version-number "$LAYER_VERSION" \
        --statement-id allow-all-accounts \
        --principal "*" \
        --action lambda:GetLayerVersion \
        --output json > /dev/null 2>&1; then
        echo "  Public access granted ($arch)."
    else
        echo "  FAILED to grant public access for $arch in $region"
        return 1
    fi
}

for REGION in "${REGIONS[@]}"; do
    echo "--- Publishing to $REGION ---"

    REGION_FAILED=false
    publish_arch "$REGION" "$ZIP_X86_64" "x86_64" || REGION_FAILED=true
    publish_arch "$REGION" "$ZIP_ARM64"  "arm64"  || REGION_FAILED=true

    if [[ "$REGION_FAILED" == "true" ]]; then
        FAILED_REGIONS+=("$REGION")
    fi

    echo ""
done

# Summary
echo "=== Publishing Summary ==="
echo "Regions attempted: ${#REGIONS[@]}"
echo "Failed: ${#FAILED_REGIONS[@]}"

if [[ ${#FAILED_REGIONS[@]} -gt 0 ]]; then
    echo "Failed regions: ${FAILED_REGIONS[*]}"
    exit 1
fi

echo "All regions published successfully."