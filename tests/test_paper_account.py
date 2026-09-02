from fastapi.testclient import TestClient

from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user
from signaltrade_trading.main import app


USER = AuthenticatedUser(id=1, username="paper", nickname="paper",
                         bot_enabled=True, execution_mode="simulated",
                         live_trading_enabled=False)


def test_paper_account_deposit_withdraw_and_ledger():
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    try:
        initial = client.get("/paper-account")
        deposited = client.post("/paper-account/deposit", json={"amount": 10000})
        withdrawn = client.post("/paper-account/withdraw", json={"amount": 2500})
        ledger = client.get("/paper-account/ledger")
    finally:
        app.dependency_overrides.clear()
    assert initial.status_code == 200
    assert initial.json()["cash_balance"] == 0
    assert deposited.json()["cash_balance"] == 10000
    assert withdrawn.json()["cash_balance"] == 7500
    assert [row["kind"] for row in ledger.json()] == ["withdraw", "deposit"]


def test_paper_account_rejects_withdrawal_above_cash():
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = TestClient(app).post("/paper-account/withdraw", json={"amount": 1})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
