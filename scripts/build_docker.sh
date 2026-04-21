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
# Usage: ./scripts/build_docker.sh <layer|zip> <output_path> [--arch x86_64|arm64]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUILD_TYPE="${1:?Usage: $0 <layer|zip> <output_path> [--arch x86_64|arm64]}"
OUTPUT_PATH="${2:?Usage: $0 <layer|zip> <output_path> [--arch x86_64|arm64]}"
ARCH="x86_64"

if [[ "${3:-}" == "--arch" ]]; then
    ARCH="${4:?--arch requires a value (x86_64 or arm64)}"
elif [[ -n "${3:-}" ]]; then
    echo "Unknown option: $3" >&2
    echo "Usage: $0 <layer|zip> <output_path> [--arch x86_64|arm64]" >&2
    exit 1
fi

case "${ARCH}" in
    x86_64|arm64) ;;
    *) echo "ERROR: invalid arch '${ARCH}'. Use x86_64 or arm64." >&2; exit 1 ;;
esac

LAMBDA_IMAGE_X86_64="public.ecr.aws/lambda/python:3.14.2026.03.31.12-x86_64"
LAMBDA_IMAGE_ARM64="public.ecr.aws/lambda/python:3.14.2026.03.31.12-arm64"

if [[ "${ARCH}" == "arm64" ]]; then
    LAMBDA_RUNTIME_IMAGE="${LAMBDA_IMAGE_ARM64}"
    PLATFORM_ARGS=(--platform linux/arm64)
else
    LAMBDA_RUNTIME_IMAGE="${LAMBDA_IMAGE_X86_64}"
    PLATFORM_ARGS=()
fi

OUTPUT_DIR="$(dirname "${OUTPUT_PATH}")"
OUTPUT_FILENAME="$(basename "${OUTPUT_PATH}")"
mkdir -p "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd)"

BUILD_DIR=/tmp/lambda-build

case "${BUILD_TYPE}" in
    layer)
        APP_DIR="${BUILD_DIR}/python"
        ZIP_CMD="cd ${BUILD_DIR} && zip -r9q /output/${OUTPUT_FILENAME} python/ -x '*.pyc' '__pycache__/*' '*.dist-info/*'"
        ;;
    zip)
        APP_DIR="${BUILD_DIR}"
        ZIP_CMD="cd ${BUILD_DIR} && zip -r9q /output/${OUTPUT_FILENAME} . -x '*.pyc' '__pycache__/*' '*.dist-info/*'"
        ;;
    *)
        echo "ERROR: unknown build type '${BUILD_TYPE}'. Use 'layer' or 'zip'." >&2
        exit 1
        ;;
esac

echo "Building ${BUILD_TYPE} (${ARCH}) using ${LAMBDA_RUNTIME_IMAGE}..."

docker run --rm "${PLATFORM_ARGS[@]}" \
    -v "${REPO_ROOT}:/src:ro" \
    -v "${OUTPUT_DIR}:/output" \
    --entrypoint bash \
    "${LAMBDA_RUNTIME_IMAGE}" \
    -c "
        set -euo pipefail

        mkdir -p ${APP_DIR}/lib

        # Install build tools and yajl
        dnf install -y zip yajl > /dev/null 2>&1

        # Install Python dependencies
        python3.14 -m pip install --upgrade pip > /dev/null
        python3.14 -m pip install --no-cache-dir -r /src/src/requirements.txt \
            --target ${APP_DIR} \
            --use-pep517 \
            --quiet

        # Copy application source code
        cp -r /src/src/* ${APP_DIR}/
        rm -f ${APP_DIR}/requirements.txt ${APP_DIR}/requirements-dev.txt

        # Copy local configuration
        cp -r /src/config ${APP_DIR}/

        # Copy license files
        cp /src/LICENSE /src/NOTICE /src/THIRD_PARTY_LICENSES ${APP_DIR}/ 2>/dev/null || trueCan

        # Copy yajl shared library and create symlink for compatibility
        cp /usr/lib64/libyajl.so.2 ${APP_DIR}/lib/
        cd ${APP_DIR}/lib && ln -sf libyajl.so.2 libyajl.so

        ${ZIP_CMD}
    "

echo ""
echo "Done. Output:"
ls -lh "${OUTPUT_DIR}/${OUTPUT_FILENAME}"
