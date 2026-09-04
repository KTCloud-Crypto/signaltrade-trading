from datetime import datetime, timedelta

from signaltrade_trading.config import settings
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.models.execution import StrategyExecution
from sqlalchemy import select

from signaltrade_trading.models.external import strategy_table, user_strategy_table, user_table
from signaltrade_trading.notification_events import enqueue_recovery_notification
from signaltrade_trading.portfolio_client import (
    PortfolioUnavailable,
    get_reconciliation_differences,
)


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


def recover_stale_live_executions() -> tuple[int, int]:
    """Classify stale pre-submission live orders without guessing that they failed."""
    cutoff = datetime.utcnow() - timedelta(seconds=max(30, settings.stale_execution_seconds))
    with SessionLocal() as db:
        execution = StrategyExecution.__table__
        rows = db.execute(
            select(
                StrategyExecution,
                strategy_table.c.name.label("strategy_name"),
                user_table.c.telegram_chat_id,
            )
            .select_from(
                execution.join(
                    user_strategy_table,
                    user_strategy_table.c.id == execution.c.user_strategy_id,
                )
                .join(strategy_table, strategy_table.c.id == user_strategy_table.c.strategy_id)
                .join(user_table, user_table.c.id == execution.c.user_id)
            )
            .where(
                execution.c.mode == "live",
                execution.c.status == "ready",
                execution.c.created_at < cutoff,
            )
        ).all()
        differences_by_user: dict[int, dict[str, float]] = {}
        recovered = 0
        uncertain = 0
        for row in rows:
            item = row.StrategyExecution
            try:
                if item.user_id not in differences_by_user:
                    differences_by_user[item.user_id] = get_reconciliation_differences(item.user_id)
            except PortfolioUnavailable:
                continue
            currency = item.market.split("-", maxsplit=1)[-1]
            item.status = live_recovery_status(
                item.action,
                differences_by_user[item.user_id].get(currency, 0.0),
            )
            if item.status == "uncertain":
                uncertain += 1
                item.error_message = (
                    "worker 중단 중 실제 주문이 체결됐을 가능성이 있어 잔고 동기화가 필요합니다."
                )
                enqueue_recovery_notification(
                    db,
                    execution=item,
                    chat_id=row.telegram_chat_id,
                    strategy_name=row.strategy_name,
                )
            else:
                item.error_message = (
                    "worker가 중단되어 제출 여부를 확인할 수 없었으나 잔고 차이는 없습니다."
                )
            recovered += 1
        db.commit()
        return recovered, uncertain
