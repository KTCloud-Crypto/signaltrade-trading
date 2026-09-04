from datetime import datetime, timedelta

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.models.execution import StrategyExecution
from sqlalchemy import insert

from signaltrade_trading.models import (
    MessageOutbox,
    strategy_signal_table,
    strategy_table,
    supported_market_table,
    user_strategy_table,
    user_table,
)
from signaltrade_trading.recovery import (
    live_recovery_status,
    recover_stale_live_executions,
    recover_stale_paper_executions,
)


def test_live_recovery_detects_possible_external_fill():
    assert live_recovery_status("buy", 0.01) == "uncertain"
    assert live_recovery_status("sell", -0.01) == "uncertain"
    assert live_recovery_status("buy", 0) == "failed"


def test_stale_paper_execution_fails_safely():
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
            "live_trading_enabled": False, "telegram_chat_id": None}])
        db.execute(insert(strategy_table), [{"id": 1, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 1, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 1, "user_id": 1,
            "strategy_id": 1, "market_id": 1, "mode": "simulated",
            "invest_ratio": 0.1, "timeframe_minutes": 10,
            "enabled": True, "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 1, "strategy_id": 1,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 100}])
        row = StrategyExecution(signal_id=1, user_strategy_id=1, user_id=1,
            mode="simulated", action="buy", market="KRW-BTC", price=100,
            status="simulated_pending", created_at=datetime.utcnow() - timedelta(minutes=5))
        db.add(row); db.commit(); row_id = row.id
    assert recover_stale_paper_executions() == 1
    with SessionLocal() as db:
        assert db.get(StrategyExecution, row_id).status == "simulated_failed"


def test_stale_live_execution_with_balance_change_becomes_uncertain(monkeypatch):
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
            "live_trading_enabled": True, "telegram_chat_id": "chat-1"}])
        db.execute(insert(strategy_table), [{"id": 10, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 20, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 30, "user_id": 1,
            "strategy_id": 10, "market_id": 20, "mode": "live", "invest_ratio": 0.1,
            "allocated_amount": 10000, "timeframe_minutes": 10, "enabled": True,
            "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 1, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 100}])
        row = StrategyExecution(signal_id=1, user_strategy_id=30, user_id=1,
            mode="live", action="buy", market="KRW-BTC", price=100,
            status="ready", created_at=datetime.utcnow() - timedelta(minutes=5))
        db.add(row)
        db.commit()
        row_id = row.id
    monkeypatch.setattr(
        "signaltrade_trading.recovery.get_reconciliation_differences",
        lambda _user_id: {"BTC": 0.01},
    )

    assert recover_stale_live_executions() == (1, 1)
    with SessionLocal() as db:
        row = db.get(StrategyExecution, row_id)
        assert row.status == "uncertain"
        notification = db.query(MessageOutbox).one()
        assert notification.payload["notification_type"] == "execution_recovery_uncertain"
