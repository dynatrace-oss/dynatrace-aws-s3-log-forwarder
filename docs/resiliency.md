# Resiliency

The `dynatrace-aws-s3-log-forwarder` will attempt up to 3 times to forward a log object to Dynatrace. In the scenario where a log file has failed to be processed more than 3 times, the SQS message with the object details will be redriven to the Dead Letter Queue, where it will be retained for up to 1 day.

The SAM template configures a CloudWatch alarm to trigger whenever messages make it to the Dead Letter Queue. When this happens, you'll receive a notification e-mail (you can change this for any valid Amazon SNS target).

You can take a look at the messages on the Dead Letter Queue, as well as the dynatrace-s3-log-forwarder logs to determine the cause of the error. If it's a retriable error due to a temporary situation, you can redrive the messages in the DLQ so they're re-processed by the log forwarder. More information [here](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-dead-letter-queue-redrive.html).

You can customize the solution behavior changing the `S3NotificationsQueue`.`RedrivePolicy` attributes and the `SQSDeadLetterQueue`.`MessageRetentionPeriod` attribute on the SAM template:

```yaml
S3NotificationsQueue:
  Type: AWS::SQS::Queue
  Properties:
    # Use crafted queue name to avoid circular dependency with RedriveAllowPolic
    QueueName: !Sub ${AWS::StackName}-S3NotificationsQueue
    ReceiveMessageWaitTimeSeconds: 10
    VisibilityTimeout: 420
    MessageRetentionPeriod: 43200
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt SQSDeadLetterQueue.Arn
      maxReceiveCount: 3

SQSDeadLetterQueue:
Type: AWS::SQS::Queue
Properties:
  QueueName: !Sub ${AWS::StackName}-S3NotificationsDQL
  # Keep messages during 1 day for troubleshooting purpos
  MessageRetentionPeriod: 86400
  RedriveAllowPolicy:
    redrivePermission: byQueue
    # Hand-crafted ARN to avoid circular dependency
    sourceQueueArns:
      - !Join
        - ":"
        - - arn
          - !Ref AWS::Partition
          - sqs
          - !Ref AWS::Region
          - !Ref AWS::AccountId
          - !Sub ${AWS::StackName}-S3NotificationsQueue
```

**Note:** The VisibilityTimeout value should be higher than the Lambda function timeout (default is 300s), to avoid processing the same message multiple times.
