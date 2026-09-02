import httpx
import pytest

from signaltrade_trading.config import settings
from signaltrade_trading.identity_client import (
    ExchangeCredentialsUnavailable,
    get_exchange_credentials,
)


def test_exchange_credentials_client_sends_internal_token(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_token", "runtime-token")

    def fake_get(url, *, headers, timeout):
        assert url.endswith("/internal/exchange-credentials/7")
        assert headers == {"X-SignalTrade-Service-Token": "runtime-token"}
        assert timeout == settings.identity_service_timeout_seconds
        return httpx.Response(200, json={"access_key": "access", "secret_key": "secret"})

    monkeypatch.setattr(httpx, "get", fake_get)
    credentials = get_exchange_credentials(7)
    assert credentials.access_key == "access"
    assert credentials.secret_key == "secret"


def test_exchange_credentials_client_fails_closed_without_service_token(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_token", "")
    with pytest.raises(ExchangeCredentialsUnavailable, match="서비스 토큰"):
        get_exchange_credentials(7)
