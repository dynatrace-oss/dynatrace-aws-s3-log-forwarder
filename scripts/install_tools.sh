#!/bin/bash
set -e

# yq
YQ_VERSION="v4.30.8"
declare -A yq_sha256=(["amd64"]="2e07c9b81699a6823dafc36a9c01aef5025179c069fedd42b1c6983545386771" ["arm64"]="063d2ed03a370341225a0624c0b7050131e95f7e9e903490aa02fb83e7111c72")
YQ_BINARY="yq_linux_${TRAVIS_CPU_ARCH}"

wget -q https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/${YQ_BINARY}.tar.gz 

YQ_SHA256_SUM=$"YQ_${TRAVIS_CPU_ARCH}_SHA256"

if [ "$(sha256sum ${YQ_BINARY}.tar.gz | cut -d' ' -f1)" = ${yq_sha256["$TRAVIS_CPU_ARCH"]} ]
then
    tar xzf ${YQ_BINARY}.tar.gz
    sudo mv ${YQ_BINARY} /usr/bin/yq
else
    echo "ERROR! yq tarball doesn't match checksum"
    exit 1
fi
