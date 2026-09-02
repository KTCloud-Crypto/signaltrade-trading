from datetime import datetime, timedelta

from signaltrade_trading.database import SessionLocal
from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.recovery import live_recovery_status, recover_stale_paper_executions


def test_live_recovery_detects_possible_external_fill():
    assert live_recovery_status("buy", 0.01) == "uncertain"
    assert live_recovery_status("sell", -0.01) == "uncertain"
    assert live_recovery_status("buy", 0) == "failed"


def test_stale_paper_execution_fails_safely():
    with SessionLocal() as db:
        row = StrategyExecution(signal_id=1, user_strategy_id=1, user_id=1,
            mode="simulated", action="buy", market="KRW-BTC", price=100,
            status="simulated_pending", created_at=datetime.utcnow() - timedelta(minutes=5))
        db.add(row); db.commit(); row_id = row.id
    assert recover_stale_paper_executions() == 1
    with SessionLocal() as db:
        assert db.get(StrategyExecution, row_id).status == "simulated_failed"
