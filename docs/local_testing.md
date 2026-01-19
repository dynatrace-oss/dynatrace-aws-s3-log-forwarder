# Local testing & debugging

You may want to perform local testing of the Lambda function when creating log Forwarding rules or log processing rules to validate that they behave as expected before deploying the changes.

As we're using Docker to build a Lambda container image, you can use the following steps to test locally:

1. Create a file `dev/env_vars.cfg` with the required configuration environment variables for the Lambda function to work:

   ```bash
   AWS_SAM_LOCAL=True
   AWS_DEFAULT_REGION=us-east-1
   DEPLOYMENT_NAME=test
   POWERTOOLS_METRICS_NAMESPACE=local
   DYNATRACE_1_ENV_URL=https://xxx.dynatrace.com
   DYNATRACE_1_API_KEY_PARAM=/dynatrace/s3-log-forwarder/dynatrace-aws-s3-log-forwarder/tenant/api-key
   DYNATRACE_1_API_KEY=dt0c01.XXX
   DYNATRACE_2_ENV_URL=https://yyy.dynatrace.com
   DYNATRACE_2_API_KEY_PARAM=/dynatrace/s3-log-forwarder/my-test/api-key2 
   DYNATRACE_2_API_KEY=dt0c01.YYY
   PYTHONPATH=/var/task
   LOG_FORWARDER_CONFIGURATION_LOCATION=local
   ```

2. Create a development Docker image with the development and testing dependencies running the following command:

   ```bash
   export LAMBDA_BASE_IMAGE_TAG=3.14.2025.12.22.13-arm64
   export LAMBDA_ARCH=arm64
   docker build --progress=plain . -t queueprocessingfunction:dev --build-arg ARCH=$LAMBDA_ARCH --build-arg LAMBDA_BASE_IMAGE_TAG=${LAMBDA_BASE_IMAGE_TAG} --build-arg ENABLE_LAMBDA_INSIGHTS="false" --build-arg ENV="DEV"
   ```

   **Note:** If you're running on an x86_64 machine and an OS that doesn't support arm64 emulation, change the LAMBDA_BASE_IMAGE_TAG and LAMBDA_ARCH to x86_64

3. Run the following command to execute the `tests/e2e/local_app.py` code to validate the forwarding rules.

   ```bash
   docker run \
           --entrypoint="" \
           --env-file dev/env_vars.cfg \
           --mount type=bind,source=$(pwd)/tests,target=/var/task/tests \
           --mount type=bind,source=$(pwd)/config,target=/var/task/config \
           queueprocessingfunction:dev \
           python tests/e2e/local_app.py
   ```

   **NOTE:** The above command mounts the `tests` and `config` folders on the development container, so you don't need to rebuild the image on every    change of log_processing or log_forwarding rules or adding new log files to `tests/test_data`.

To test/validate forwarding and processing rules, we execute `tests/e2e/local_app.py`. It is a lightweight wrapper around the real forwarder's entry point, adding additional processing steps:

* Setup up an AWS mock for SSM and S3
* Load SSM parameters from information from environment variables
* Load test data from your disk, prepare the data and load it to the mock S3
* Start the forwarder as it would be running within AWS

You can now test your log_forwarding_rules and log_processing_rules configured in `config/*` against the data contained in `tests/test_data/s3/*`. If you want to test new log files, you can add them to a new folder `tests/test_data/s3/<your_folder>`. For each file you want to test on the execution, within the folder create a `_test_setup.yaml` file that specifies which log files to load and the properties to mock them as S3 objects. The structure is the following:

```yaml
--- 
files: 
  your_log_file_name: 
    bucket: bucket_name       # <name_of_the_s3_bucket_to_mock>
    key: key_name             # <name_of_the_s3_key_to_mock>
    requester: 012345678910   # <AWS account ID or requester to mock (e.g. cloudtrail.amazonaws.com)>
    pipeline:                 # Optionally, define processing of your log file using jinja2 as templating engine  
      - command:
          args:
            - arg1
```

Available commands are:

* **update_timestamps**: creates an UTC timestamp in requested format (argument). The date format needs to follow the pattern described in the [datetime](https://docs.python.org/3/library/datetime.html) library docs | strftime() and strptime() Format Codes. Occurrences of {{next_log_timestamp()}} in the underlying test data will be replaced by a valid time string. Each instance of {{next_log_timestamp()}} will receive a different timestamp. The first timestamp is now - 2h 55m; every consecutive call a second is added.
* **print**: prints current data to stdout
* **gz**: zip current content and append .gz prefix to to-be S3 key name
