from signaltrade_trading.config import settings
from signaltrade_trading.sqs import SqsQueueAdapter


def test_aws_client_uses_pod_identity_without_static_keys(monkeypatch):
    captured = {}
    monkeypatch.setattr(settings, "sqs_endpoint_url", None)
    monkeypatch.setattr(settings, "aws_access_key_id", None)
    monkeypatch.setattr(settings, "aws_secret_access_key", None)
    monkeypatch.setattr("signaltrade_trading.sqs.boto3.client",
                        lambda service, **options: captured.update(options) or object())

    SqsQueueAdapter.from_settings()

    assert "aws_access_key_id" not in captured
    assert "aws_secret_access_key" not in captured
