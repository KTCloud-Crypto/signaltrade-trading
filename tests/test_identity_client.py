import httpx
import pytest
from fastapi import HTTPException

from signaltrade_trading import identity_client


def test_identity_client_forwards_bearer_token(monkeypatch):
    def fake_get(url, *, headers, timeout):
        assert url.endswith("/internal/auth/me")
        assert headers == {"Authorization": "Bearer valid"}
        return httpx.Response(200, json={"id": 3, "username": "u", "nickname": "n",
                                         "bot_enabled": True, "execution_mode": "simulated",
                                         "live_trading_enabled": False})

    monkeypatch.setattr(identity_client.httpx, "get", fake_get)
    assert identity_client.get_current_user("Bearer valid").id == 3


def test_identity_client_requires_bearer_token():
    with pytest.raises(HTTPException) as error:
        identity_client.get_current_user(None)
    assert error.value.status_code == 401
