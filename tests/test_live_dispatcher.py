from sqlalchemy import insert

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.dispatcher import dispatch_signal
from signaltrade_trading.identity_client import ExchangeCredentials
from signaltrade_trading.live_order import LiveOrderResult
from signaltrade_trading.models import (
    StrategyExecution,
    Trade,
    strategy_signal_table,
    strategy_table,
    supported_market_table,
    user_strategy_table,
    user_table,
)
from signaltrade_trading.preflight import PreflightResult


def _seed_live(*, enabled: bool):
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
                                        "live_trading_enabled": enabled}])
        db.execute(insert(strategy_table), [{"id": 10, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 20, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 30, "user_id": 1,
            "strategy_id": 10, "market_id": 20, "mode": "live",
            "invest_ratio": 0.1, "allocated_amount": None,
            "timeframe_minutes": 10, "enabled": True, "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 40, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 50000.0}])
        db.commit()


def test_live_dispatcher_fails_closed_when_live_trading_is_disabled(monkeypatch):
    _seed_live(enabled=False)
    monkeypatch.setattr("signaltrade_trading.dispatcher.get_exchange_credentials",
                        lambda user_id: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert dispatch_signal(40) == 1
    with SessionLocal() as db:
        execution = db.query(StrategyExecution).one()
    assert execution.status == "validation_failed"
    assert "비활성화" in execution.error_message


def test_live_dispatcher_places_mocked_order_and_persists_trade(monkeypatch):
    _seed_live(enabled=True)
    monkeypatch.setattr("signaltrade_trading.dispatcher.get_exchange_credentials",
                        lambda user_id: ExchangeCredentials(access_key="a", secret_key="s"))
    monkeypatch.setattr("signaltrade_trading.dispatcher.validate_buy",
                        lambda **kwargs: PreflightResult(True, 10000.0))
    monkeypatch.setattr("signaltrade_trading.dispatcher.execute_market_buy",
                        lambda **kwargs: LiveOrderResult(True, "success", "order-1",
                            0.2, 50000.0, 5.0, raw_response={"uuid": "order-1"}))

    assert dispatch_signal(40) == 1
    assert dispatch_signal(40) == 0
    with SessionLocal() as db:
        execution = db.query(StrategyExecution).one()
        trade = db.query(Trade).one()
    assert execution.status == "success"
    assert execution.order_uuid == "order-1"
    assert trade.strategy_execution_id == execution.id


def test_live_dispatcher_blocks_when_same_action_is_pending(monkeypatch):
    _seed_live(enabled=True)
    with SessionLocal() as db:
        db.execute(insert(strategy_signal_table), [{"id": 41, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 49000.0}])
        db.add(StrategyExecution(signal_id=41,
            user_strategy_id=30, user_id=1, mode="live", action="buy",
            market="KRW-BTC", status="submitted", price=49000.0))
        db.commit()
    monkeypatch.setattr("signaltrade_trading.dispatcher.get_exchange_credentials",
                        lambda user_id: (_ for _ in ()).throw(AssertionError("must not fetch")))

    assert dispatch_signal(40) == 1
    with SessionLocal() as db:
        blocked = db.query(StrategyExecution).filter_by(signal_id=40).one()
    assert blocked.status == "validation_failed"
    assert "진행 중" in blocked.error_message
