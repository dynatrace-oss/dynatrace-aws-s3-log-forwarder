#!/bin/bash

# Copyright 2026 Dynatrace LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#      https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Build a Lambda Layer or Lambda deployment ZIP inside a Docker container.
# This ensures binary compatibility with the Lambda runtime, and bundles the yajl
# native library required by ijson's yajl2_c backend.
# Usage: ./scripts/build_docker.sh <layer|zip> <output_path>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUILD_TYPE="${1:?Usage: $0 <layer|zip> <output_path>}"
OUTPUT_PATH="${2:?Usage: $0 <layer|zip> <output_path>}"

LAMBDA_RUNTIME_IMAGE="public.ecr.aws/lambda/python:3.14.2026.03.31.12-x86_64"

OUTPUT_DIR="$(dirname "${OUTPUT_PATH}")"
OUTPUT_FILENAME="$(basename "${OUTPUT_PATH}")"
mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"

echo "Building ${BUILD_TYPE} using ${LAMBDA_RUNTIME_IMAGE}..."

case "${BUILD_TYPE}" in
    layer)
        docker run --rm \
            -v "${REPO_ROOT}:/src:ro" \
            -v "${OUTPUT_DIR}:/output" \
            --entrypoint bash \
            "${LAMBDA_RUNTIME_IMAGE}" \
            -c "
                set -euo pipefail

                BUILD_DIR=/tmp/lambda-layer-build
                mkdir -p \${BUILD_DIR}/python/lib

                # Install build tools and yajl
                dnf install -y zip yajl > /dev/null 2>&1

                # Install Python dependencies
                python3.14 -m pip install --upgrade pip > /dev/null
                python3.14 -m pip install --no-cache-dir -r /src/src/requirements.txt \
                    --target \${BUILD_DIR}/python \
                    --use-pep517 \
                    --quiet

                # Copy application source code
                cp -r /src/src/* \${BUILD_DIR}/python/
                rm -f \${BUILD_DIR}/python/requirements.txt \${BUILD_DIR}/python/requirements-dev.txt

                # Copy license files
                cp /src/LICENSE /src/NOTICE /src/THIRD_PARTY_LICENSES \${BUILD_DIR}/python/ 2>/dev/null || true

                # Copy yajl shared library and create symlink for compatibility
                cp /usr/lib64/libyajl.so.2 \${BUILD_DIR}/python/lib/
                cd \${BUILD_DIR}/python/lib && ln -sf libyajl.so.2 libyajl.so

                # Create ZIP (python/ prefix is required by the Lambda layer spec)
                cd \${BUILD_DIR}
                zip -r /output/${OUTPUT_FILENAME} python/ -q
            "
        ;;
    zip)
        docker run --rm \
            -v "${REPO_ROOT}:/src:ro" \
            -v "${OUTPUT_DIR}:/output" \
            --entrypoint bash \
            "${LAMBDA_RUNTIME_IMAGE}" \
            -c "
                set -euo pipefail

                BUILD_DIR=/tmp/lambda-build
                mkdir -p \${BUILD_DIR}/lib

                # Install build tools and yajl
                dnf install -y zip yajl > /dev/null 2>&1

                # Install python dependencies
                python3.14 -m pip install --upgrade pip > /dev/null
                python3.14 -m pip install --no-cache-dir -r /src/src/requirements.txt \
                    --target \${BUILD_DIR} \
                    --use-pep517 \
                    --quiet

                # Copy application source code
                cp /src/src/app.py /src/src/index.py /src/src/version.py /src/src/__init__.py \${BUILD_DIR}/
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
            "
        ;;
    *)
        echo "ERROR: unknown build type '${BUILD_TYPE}'. Use 'layer' or 'zip'." >&2
        exit 1
        ;;
esac

echo ""
echo "Done. Output:"
ls -lh "${OUTPUT_DIR}/${OUTPUT_FILENAME}"
