from sqlalchemy import insert

from signaltrade_trading.identity_client import ExchangeCredentials
from signaltrade_trading.live_order import LiveOrderResult
from signaltrade_trading.models import (
    MessageOutbox,
    StrategyExecution,
    Trade,
    strategy_signal_table,
    strategy_table,
    supported_market_table,
    user_strategy_table,
    user_table,
)
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.order_reconciliation import reconcile_pending_orders


def test_pending_order_is_settled_and_events_are_queued(monkeypatch) -> None:
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
            "live_trading_enabled": True, "telegram_chat_id": "chat-1"}])
        db.execute(insert(strategy_table), [{"id": 10, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 20, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 30, "user_id": 1,
            "strategy_id": 10, "market_id": 20, "mode": "live", "invest_ratio": 0.1,
            "allocated_amount": None, "timeframe_minutes": 10, "enabled": True,
            "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 40, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 50000.0}])
        execution = StrategyExecution(signal_id=40, user_strategy_id=30, user_id=1,
            mode="live", action="buy", market="KRW-BTC", status="submitted",
            price=50000.0, order_amount=10000.0, order_uuid="order-1")
        db.add(execution)
        db.flush()
        db.add(Trade(user_id=1, strategy_execution_id=execution.id, ticker="KRW-BTC",
            action="buy", price=50000.0, volume=0, status="submitted", raw_response={}))
        db.commit()
        execution_id = execution.id

    monkeypatch.setattr(
        "signaltrade_trading.order_reconciliation.get_exchange_credentials",
        lambda _user_id: ExchangeCredentials(access_key="access", secret_key="secret"),
    )
    monkeypatch.setattr(
        "signaltrade_trading.order_reconciliation.fetch_order_result",
        lambda **_kwargs: LiveOrderResult(True, "success", "order-1", 0.2, 50000.0,
                                          5.0, None, {"state": "done"}),
    )

    assert reconcile_pending_orders() == 1
    assert reconcile_pending_orders() == 0

    with SessionLocal() as db:
        execution = db.get(StrategyExecution, execution_id)
        trade = db.query(Trade).filter_by(strategy_execution_id=execution_id).one()
        outboxes = db.query(MessageOutbox).order_by(MessageOutbox.id).all()
        assert execution.status == "success"
        assert execution.executed_volume == 0.2
        assert execution.settlement_notification_sent is True
        assert (trade.status, trade.volume) == ("success", 0.2)
        assert [row.message_type for row in outboxes] == [
            "AllocationChanged", "NotificationRequested"
        ]
        assert outboxes[1].payload["notification_type"] == "order_settlement"
