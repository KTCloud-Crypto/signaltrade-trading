from sqlalchemy import insert, select

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models import (MessageOutbox, PaperAccount, StrategyExecution,
    strategy_signal_table, strategy_table, supported_market_table, user_strategy_table, user_table)
from signaltrade_trading.trading_commands import execute_strategy_signal


def _seed_signal():
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
                                        "live_trading_enabled": False}])
        db.execute(insert(strategy_table), [{"id": 10, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 20, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 30, "user_id": 1,
            "strategy_id": 10, "market_id": 20, "mode": "simulated",
            "invest_ratio": 0.1, "allocated_amount": None,
            "timeframe_minutes": 10, "enabled": True, "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 40, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 50000.0}])
        db.add(PaperAccount(user_id=1, cash_balance=100000, net_deposit=100000))
        db.commit()


def test_strategy_signal_executes_paper_order_and_queues_allocation():
    _seed_signal()
    envelope = MessageEnvelope.create(message_type="StrategySignalCreated", producer="strategy",
        payload={"signal_id": 40, "target_user_id": None, "target_mode": None})
    first = execute_strategy_signal(envelope)
    second = execute_strategy_signal(envelope)
    with SessionLocal() as db:
        execution = db.query(StrategyExecution).one()
        account = db.query(PaperAccount).one()
        outbox = db.query(MessageOutbox).filter_by(message_type="AllocationChanged").one()
    assert first.execution_count == 1
    assert second.execution_count == 0
    assert execution.status == "simulated_success"
    assert execution.order_amount == 10000
    assert float(account.cash_balance) == 89995
    assert outbox.payload["user_strategy_id"] == 30
    assert outbox.payload["allocated_amount"] == 10000


def test_invalid_strategy_signal_is_rejected():
    envelope = MessageEnvelope.create(message_type="StrategySignalCreated", producer="strategy",
                                      payload={"signal_id": 0})
    try:
        execute_strategy_signal(envelope)
    except ValueError as error:
        assert "positive integer" in str(error)
    else:
        raise AssertionError("invalid signal must be rejected")
