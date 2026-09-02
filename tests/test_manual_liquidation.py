from fastapi.testclient import TestClient
from sqlalchemy import insert

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user
from signaltrade_trading.main import app
from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models import (
    MessageOutbox, StrategyExecution, TradingExecutionRequest,
    strategy_signal_table, strategy_table, supported_market_table,
    user_strategy_table, user_table,
)
from signaltrade_trading.trading_commands import execute_manual_liquidation

USER = AuthenticatedUser(id=1, username="manual", nickname="manual",
                         bot_enabled=True, execution_mode="simulated",
                         live_trading_enabled=False)


def _seed_position():
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1, "bot_enabled": True,
                                        "live_trading_enabled": False}])
        db.execute(insert(strategy_table), [{"id": 10, "name": "SMA", "enabled": True}])
        db.execute(insert(supported_market_table), [{"id": 20, "code": "KRW-BTC"}])
        db.execute(insert(user_strategy_table), [{"id": 30, "user_id": 1,
            "strategy_id": 10, "market_id": 20, "mode": "simulated",
            "invest_ratio": 0.1, "allocated_amount": 10000,
            "timeframe_minutes": 10, "enabled": True, "paused": False}])
        db.execute(insert(strategy_signal_table), [{"id": 40, "strategy_id": 10,
            "market": "KRW-BTC", "timeframe_minutes": 10, "action": "buy",
            "source": "engine", "close_price": 50000.0}])
        db.add(StrategyExecution(signal_id=40, user_strategy_id=30, user_id=1,
            mode="simulated", action="buy", market="KRW-BTC",
            status="simulated_success", price=50000, order_amount=10000,
            executed_volume=0.2, average_price=50000, paid_fee=5))
        db.commit()


def test_manual_sell_is_idempotently_stored_with_outbox(monkeypatch):
    _seed_position()

    async def fake_price(market):
        return 51000.0

    monkeypatch.setattr("signaltrade_trading.api_manual.get_current_price", fake_price)
    app.dependency_overrides[get_current_user] = lambda: USER
    client = TestClient(app)
    try:
        first = client.post("/strategies/10/manual-sell?mode=simulated&market=KRW-BTC",
                            headers={"Idempotency-Key": "manual-1"})
        second = client.post("/strategies/10/manual-sell?mode=simulated&market=KRW-BTC",
                             headers={"Idempotency-Key": "manual-1"})
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == 200
    assert second.json() == first.json()
    with SessionLocal() as db:
        assert db.query(TradingExecutionRequest).count() == 1
        outbox = db.query(MessageOutbox).filter_by(
            message_type="ManualLiquidationRequested").one()
    assert outbox.payload["execution_request_id"] == first.json()["execution_request_id"]


def test_manual_liquidation_command_executes_paper_sell_once(monkeypatch):
    test_manual_sell_is_idempotently_stored_with_outbox(monkeypatch)
    with SessionLocal() as db:
        request_id = db.query(TradingExecutionRequest.id).scalar()
    envelope = MessageEnvelope.create(
        message_type="ManualLiquidationRequested", producer="trading-api",
        payload={"execution_request_id": request_id},
    )
    first = execute_manual_liquidation(envelope)
    second = execute_manual_liquidation(envelope)
    assert first.execution_count == 1
    assert second.execution_count == 0
    with SessionLocal() as db:
        execution = db.query(StrategyExecution).filter_by(
            execution_request_id=request_id).one()
    assert execution.status == "simulated_success"
    assert execution.action == "sell"
