from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.message_outbox import MessageOutbox
from signaltrade_trading.notification_events import enqueue_execution_notification
from signaltrade_trading.database import SessionLocal


def test_execution_notification_is_written_to_outbox():
    with SessionLocal() as db:
        db.execute(insert(user_table), {"id": 4, "bot_enabled": True,
            "live_trading_enabled": False, "telegram_chat_id": "1234"})
        db.execute(insert(strategy_table), {"id": 2, "name": "SMA", "enabled": True})
        db.execute(insert(supported_market_table), {"id": 1, "code": "KRW-BTC"})
        db.execute(insert(user_strategy_table), {"id": 3, "user_id": 4,
            "strategy_id": 2, "market_id": 1, "mode": "simulated",
            "invest_ratio": 0.1, "timeframe_minutes": 10,
            "enabled": True, "paused": False})
        db.execute(insert(strategy_signal_table), {"id": 9, "strategy_id": 2,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 100_000_000})
        execution = StrategyExecution(
            id=81, signal_id=9, user_strategy_id=3, user_id=4, mode="simulated",
            action="buy", market="KRW-BTC", status="simulated_success", price=100_000_000,
            order_amount=1_000_000, executed_volume=.01,
        )
        db.add(execution)
        assert enqueue_execution_notification(
            db, execution=execution, chat_id="1234", strategy_name="SMA",
        )
        db.flush()
        message = db.query(MessageOutbox).filter_by(
            idempotency_key="execution-notification:81").one()
        assert message.message_type == "NotificationRequested"
        assert message.payload["chat_id"] == "1234"
        assert message.payload["user_id"] == 4
        assert execution.notification_sent is True
from sqlalchemy import insert

from signaltrade_trading.models import (
    strategy_signal_table,
    strategy_table,
    supported_market_table,
    user_strategy_table,
    user_table,
)
