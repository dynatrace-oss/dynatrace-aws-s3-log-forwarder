#!/bin/bash

# Copyright 2022 Dynatrace LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#      https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Build the Lambda Layer ZIP containing the application code and dependencies.
# Usage: ./build_layer.sh

set -e

ARCH="x86_64"
PIP_PLATFORM="manylinux2014_x86_64"

echo "Building Lambda Layer for architecture: $ARCH (pip platform: $PIP_PLATFORM)"

LAYER_DIR="build/layer/python"
DIST_DIR="dist"

# Clean previous build
rm -rf build/layer
mkdir -p "$LAYER_DIR"
mkdir -p "$DIST_DIR"

# Install pip dependencies with pre-built binary wheels for the target platform
echo "Installing pip dependencies..."
pip install \
    -r src/requirements.txt \
    --target "$LAYER_DIR" \
    --platform "$PIP_PLATFORM" \
    --python-version 3.14 \
    --only-binary=:all: \
    --implementation cp \
    --quiet

# Copy application source code
echo "Copying application source code..."
cp -r src/* "$LAYER_DIR/"

# Remove files not needed in the layer
rm -f "$LAYER_DIR/requirements.txt" "$LAYER_DIR/requirements-dev.txt"
find "$LAYER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Copy license files
echo "Copying license files..."
for f in LICENSE NOTICE THIRD_PARTY_LICENSES; do
    if [[ -f "$f" ]]; then
        cp "$f" "$LAYER_DIR/"
    fi
done

# Create the ZIP
ZIP_FILE="$DIST_DIR/dynatrace-aws-s3-log-forwarder-layer-${ARCH}.zip"
echo "Creating layer ZIP: $ZIP_FILE"
cd build/layer
zip -r "../../$ZIP_FILE" python/ -q
cd ../..

echo ""
echo "Layer ZIP built successfully: $ZIP_FILE"
echo "Uncompressed size: $(du -sh build/layer/python | cut -f1)"
echo "ZIP size: $(du -sh "$ZIP_FILE" | cut -f1)"




