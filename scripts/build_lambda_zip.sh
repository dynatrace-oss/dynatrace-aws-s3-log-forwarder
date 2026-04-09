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

# Build the Lambda deployment ZIP package inside an Amazon Linux 2023 Docker container.
# This ensures binary compatibility with the Lambda runtime, and bundles the yajl
# native library required by ijson's yajl2_c backend.
#
# Usage: ./scripts/build_lambda_zip.sh <output_zip_path>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Amazon Linux 2023 base image - pinned for reproducibility
LAMBDA_RUNTIME_IMAGE="public.ecr.aws/lambda/python:3.14.2026.03.31.12-x86_64"

OUTPUT_ZIP="${1:?Usage: $0 <output_zip_path>}"
# Resolve to absolute path
OUTPUT_DIR="$(cd "$(dirname "${OUTPUT_ZIP}")" 2>/dev/null && pwd)" || { mkdir -p "$(dirname "${OUTPUT_ZIP}")"; OUTPUT_DIR="$(cd "$(dirname "${OUTPUT_ZIP}")" && pwd)"; }
OUTPUT_FILENAME="$(basename "${OUTPUT_ZIP}")"

echo "Building Lambda ZIP package using ${LAMBDA_RUNTIME_IMAGE}..."

docker run --rm \
    -v "${REPO_ROOT}:/src:ro" \
    -v "${OUTPUT_DIR}:/output" \
    --entrypoint bash \
    "${LAMBDA_RUNTIME_IMAGE}" \
    -c "
        set -e

        BUILD_DIR=/tmp/lambda-build
        mkdir -p \${BUILD_DIR}/lib

        # Install build tools and yajl
        dnf install -y zip yajl > /dev/null 2>&1

        # Install Python dependencies
        pip install --upgrade pip
        python3.14 -m pip install --no-cache-dir -r /src/src/requirements.txt \
            -t \${BUILD_DIR} --use-pep517 --quiet

        # Copy application source code
        cp /src/src/app.py /src/src/version.py /src/src/__init__.py \${BUILD_DIR}/
        cp -r /src/src/log \${BUILD_DIR}/
        cp -r /src/src/utils \${BUILD_DIR}/

        # Copy local configuration
        cp -r /src/config \${BUILD_DIR}/

        # Copy license files
        cp /src/LICENSE /src/NOTICE /src/THIRD_PARTY_LICENSES \${BUILD_DIR}/ 2>/dev/null || true

        # Copy yajl shared library and create symlink for compatibility
        cp /usr/lib64/libyajl.so.2 \${BUILD_DIR}/lib/
        cd \${BUILD_DIR}/lib && ln -sf libyajl.so.2 libyajl.so

        # Create ZIP
        cd \${BUILD_DIR}
        zip -r9q /output/${OUTPUT_FILENAME} . -x '*.pyc' '__pycache__/*' '*.dist-info/*'

        echo 'Lambda ZIP created successfully'
    "

echo "Output: ${OUTPUT_DIR}/${OUTPUT_FILENAME}"
ls -lh "${OUTPUT_DIR}/${OUTPUT_FILENAME}"
