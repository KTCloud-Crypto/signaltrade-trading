from fastapi.testclient import TestClient

from signaltrade_trading.main import app


def test_health_and_readiness():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok", "service": "trading"}
    assert client.get("/ready").json() == {"status": "ready", "database": "ok"}
