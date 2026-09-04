from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import insert

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user
from signaltrade_trading.main import app
from signaltrade_trading.models import (
    PaperAccount,
    StrategyExecution,
    strategy_runtime_table,
    strategy_signal_table,
    strategy_table,
    supported_market_table,
    user_strategy_table,
    user_table,
)
from signaltrade_trading.paper_accounts import account_value


USER = AuthenticatedUser(id=1, username="paper", nickname="paper",
                         bot_enabled=True, execution_mode="simulated",
                         live_trading_enabled=False)


def _seed_paper_user():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 1, "bot_enabled": True,
            "live_trading_enabled": False, "telegram_chat_id": None})
        db.commit()


def test_paper_account_deposit_withdraw_and_ledger():
    _seed_paper_user()
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
    _seed_paper_user()
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = TestClient(app).post("/paper-account/withdraw", json={"amount": 1})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409


def test_paper_account_equity_includes_open_position_mark_value():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 1, "bot_enabled": False,
                                       "live_trading_enabled": False, "telegram_chat_id": None})
        db.execute(insert(strategy_table), {"id": 1, "name": "SMA", "enabled": True})
        db.execute(insert(supported_market_table), {"id": 1, "code": "KRW-BTC"})
        db.execute(insert(user_strategy_table), {
            "id": 1, "user_id": 1, "strategy_id": 1, "market_id": 1,
            "mode": "simulated", "invest_ratio": 0.5, "allocated_amount": 1_000_000,
            "timeframe_minutes": 1, "enabled": True, "paused": False,
        })
        db.execute(insert(strategy_signal_table), {
            "id": 1, "strategy_id": 1, "market": "KRW-BTC", "timeframe_minutes": 1,
            "action": "buy", "source": "engine", "close_price": 100,
        })
        db.execute(insert(strategy_runtime_table), {
            "id": 1, "strategy_id": 1, "market": "KRW-BTC", "timeframe_minutes": 1,
            "close_price": 110, "metrics": {}, "evaluated_at": datetime(2026, 9, 3),
        })
        db.add(PaperAccount(user_id=1, cash_balance=1_000_000, net_deposit=2_000_000))
        db.add(StrategyExecution(
            signal_id=1, user_strategy_id=1, user_id=1, mode="simulated", action="buy",
            market="KRW-BTC", status="simulated_success", price=100,
            executed_volume=10, average_price=100,
        ))
        db.commit()

        value = account_value(db, 1)
        assert value.holdings_value == 1100
        assert value.total_equity == 1_001_100
        assert value.profit_loss == -998_900


def test_paper_account_reserves_unspent_strategy_budget():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 1, "bot_enabled": False,
                                       "live_trading_enabled": False, "telegram_chat_id": None})
        db.execute(insert(strategy_table), {"id": 1, "name": "SMA", "enabled": True})
        db.execute(insert(supported_market_table), {"id": 1, "code": "KRW-BTC"})
        db.execute(insert(user_strategy_table), {
            "id": 1, "user_id": 1, "strategy_id": 1, "market_id": 1,
            "mode": "simulated", "invest_ratio": .5, "allocated_amount": 40000,
            "timeframe_minutes": 1, "enabled": True, "paused": False,
        })
        db.add(PaperAccount(user_id=1, cash_balance=100000, net_deposit=100000))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = TestClient(app).get("/paper-account")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["reserved_amount"] == 40000
    assert response.json()["available_for_order"] == 59970


def test_paper_account_cannot_withdraw_reserved_strategy_budget():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 1, "bot_enabled": False,
                                       "live_trading_enabled": False, "telegram_chat_id": None})
        db.execute(insert(strategy_table), {"id": 1, "name": "SMA", "enabled": True})
        db.execute(insert(supported_market_table), {"id": 1, "code": "KRW-BTC"})
        db.execute(insert(user_strategy_table), {
            "id": 1, "user_id": 1, "strategy_id": 1, "market_id": 1,
            "mode": "simulated", "invest_ratio": .4, "allocated_amount": 40000,
            "timeframe_minutes": 1, "enabled": True, "paused": False,
        })
        db.add(PaperAccount(user_id=1, cash_balance=100000, net_deposit=100000))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        rejected = TestClient(app).post("/paper-account/withdraw", json={"amount": 60000})
        accepted = TestClient(app).post("/paper-account/withdraw", json={"amount": 59980})
    finally:
        app.dependency_overrides.clear()
    assert rejected.status_code == 409
    assert "예약된 주문 금액" in rejected.json()["detail"]
    assert accepted.status_code == 200
    assert accepted.json()["cash_balance"] == 40020


def test_paper_sell_ledger_contains_realized_profit():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 1, "bot_enabled": False,
                                       "live_trading_enabled": False, "telegram_chat_id": None})
        db.execute(insert(strategy_table), {"id": 1, "name": "SMA", "enabled": True})
        db.execute(insert(supported_market_table), {"id": 1, "code": "KRW-BTC"})
        db.execute(insert(user_strategy_table), {
            "id": 1, "user_id": 1, "strategy_id": 1, "market_id": 1,
            "mode": "simulated", "invest_ratio": .5, "allocated_amount": 100,
            "timeframe_minutes": 1, "enabled": True, "paused": False,
        })
        db.execute(insert(strategy_signal_table), [{"id": 1, "strategy_id": 1,
            "market": "KRW-BTC", "timeframe_minutes": 1, "action": "buy",
            "source": "engine", "close_price": 100}, {"id": 2, "strategy_id": 1,
            "market": "KRW-BTC", "timeframe_minutes": 1, "action": "sell",
            "source": "engine", "close_price": 110}])
        account = PaperAccount(user_id=1, cash_balance=110, net_deposit=100)
        db.add(account); db.flush()
        buy = StrategyExecution(signal_id=1, user_strategy_id=1, user_id=1,
            mode="simulated", action="buy", market="KRW-BTC", status="simulated_success",
            price=100, executed_volume=1, average_price=100, paid_fee=.05)
        sell = StrategyExecution(signal_id=2, user_strategy_id=1, user_id=1,
            mode="simulated", action="sell", market="KRW-BTC", status="simulated_success",
            price=110, executed_volume=1, average_price=110, paid_fee=.055)
        db.add_all([buy,sell]); db.flush()
        from signaltrade_trading.models import PaperLedger
        db.add(PaperLedger(account_id=account.id,strategy_execution_id=sell.id,kind="sell",
            amount=109.945,balance_after=110))
        db.commit()
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = TestClient(app).get("/paper-account/ledger")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["realized_profit_loss"] == 9.895
