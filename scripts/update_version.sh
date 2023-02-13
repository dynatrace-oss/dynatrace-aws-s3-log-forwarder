#!/bin/bash

echo  "Travis tag:     ${TRAVIS_TAG}"
echo  "Travis commit:  ${TRAVIS_COMMIT}"

if [ -n $TRAVIS_TAG ]
then
    # remove "v from vx.y.z in the tag"
    VERSION="${TRAVIS_TAG:1}"
elif [ -n $TRAVIS_COMMIT ]
then
    VERSION="${TRAVIS_COMMIT:0:7}"
else
    echo "This is not a travis build. Defaulting to VERSION=dev"
    VERSION="dev"
fi

# Update version.py
sed -i "s/__version__ = \"dev\"/__version__ = \"${VERSION}\"/g" version.py

# Update CloudFormation templates
for file in $(ls *.yaml);
do
    yq -i -e '.Metadata.Version.Description = strenv(VERSION)' $file
done

    