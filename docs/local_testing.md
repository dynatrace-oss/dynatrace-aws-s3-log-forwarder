# Local testing & debugging

You may want to perform local testing of the Lambda function when creating log Forwarding rules or log processing rules to validate that they behave as expected before deploying the changes.

You can use the following steps to test locally:

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
   PYTHONPATH=src
   LOG_FORWARDER_CONFIGURATION_LOCATION=local
   ```

2. Install the required dependencies:

   ```bash
   pip install -r src/requirements.txt -r src/requirements-dev.txt
   ```

3. Run the following command to execute the `tests/e2e/local_app.py` code to validate the forwarding rules:

   ```bash
   cd src && env $(cat ../dev/env_vars.cfg | grep -v '^#' | xargs) \
       python ../tests/e2e/local_app.py
   ```

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
