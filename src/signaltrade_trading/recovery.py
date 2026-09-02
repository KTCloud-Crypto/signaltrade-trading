from datetime import datetime, timedelta

from signaltrade_trading.config import settings
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.models.execution import StrategyExecution


def live_recovery_status(action: str, difference: float) -> str:
    tolerance = max(1e-8, abs(difference) * 1e-6)
    if action == "buy" and difference > tolerance:
        return "uncertain"
    if action == "sell" and difference < -tolerance:
        return "uncertain"
    return "failed"


def recover_stale_paper_executions() -> int:
    """A paper order has no external side effect, so stale pending rows fail safely."""
    cutoff = datetime.utcnow() - timedelta(seconds=max(30, settings.stale_execution_seconds))
    with SessionLocal() as db:
        rows = db.query(StrategyExecution).filter(
            StrategyExecution.status == "simulated_pending",
            StrategyExecution.created_at < cutoff,
        ).all()
        for execution in rows:
            execution.status = "simulated_failed"
            execution.error_message = "worker가 중단되어 완료되지 않은 모의 주문을 정리했습니다."
        db.commit()
        return len(rows)
