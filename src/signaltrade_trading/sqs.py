from dataclasses import dataclass
from typing import Any
import boto3
from signaltrade_trading.config import settings
from signaltrade_trading.message_contract import MessageEnvelope


@dataclass(frozen=True)
class QueueMessage:
    receipt_handle: str
    envelope: MessageEnvelope
    receive_count: int


class SqsQueueAdapter:
    def __init__(self, client: Any, queue_name: str):
        self.client = client; self.queue_name = queue_name; self.queue_url = None

    @classmethod
    def from_settings(cls):
        options = {"region_name": settings.aws_region,
                   "aws_access_key_id": settings.aws_access_key_id,
                   "aws_secret_access_key": settings.aws_secret_access_key}
        if settings.sqs_endpoint_url:
            options["endpoint_url"] = settings.sqs_endpoint_url
        return cls(boto3.client("sqs", **options), settings.sqs_trading_command_queue_name)

    def _url(self):
        if self.queue_url is None:
            self.queue_url = self.client.get_queue_url(QueueName=self.queue_name)["QueueUrl"]
        return self.queue_url

    def receive(self):
        response = self.client.receive_message(QueueUrl=self._url(), MaxNumberOfMessages=1,
            WaitTimeSeconds=10, VisibilityTimeout=settings.sqs_trading_visibility_timeout_seconds,
            AttributeNames=["ApproximateReceiveCount"])
        return [QueueMessage(row["ReceiptHandle"], MessageEnvelope.from_json(row["Body"]),
                             int(row.get("Attributes", {}).get("ApproximateReceiveCount", "1")))
                for row in response.get("Messages", [])]

    def acknowledge(self, message: QueueMessage):
        self.client.delete_message(QueueUrl=self._url(), ReceiptHandle=message.receipt_handle)
