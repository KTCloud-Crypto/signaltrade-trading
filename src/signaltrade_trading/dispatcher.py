from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from signaltrade_trading.allocation_events import enqueue_allocation_changed
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.external import (strategy_signal_table, strategy_table,
    supported_market_table, user_strategy_table, user_table)
from signaltrade_trading.paper_execution import execute_paper_order


@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    signal_id: int
    user_strategy_id: int
    user_id: int
    action: str
    market: str
    price: float
    invest_ratio: float
    allocated_amount: float | None
    paused: bool


def load_targets(signal_id: int, target_user_id: int | None = None,
                 target_mode: str | None = None) -> list[ExecutionTarget]:
    s, st, us, m, u = (strategy_signal_table, strategy_table, user_strategy_table,
                       supported_market_table, user_table)
    statement = (select(s.c.id, us.c.id.label("subscription_id"), us.c.user_id,
                        s.c.action, s.c.market, s.c.close_price, us.c.invest_ratio,
                        us.c.allocated_amount, us.c.paused)
        .select_from(s.join(st, st.c.id == s.c.strategy_id)
                     .join(us, us.c.strategy_id == st.c.id)
                     .join(m, m.c.id == us.c.market_id)
                     .join(u, u.c.id == us.c.user_id))
        .where(s.c.id == signal_id, st.c.enabled.is_(True), us.c.enabled.is_(True),
               u.c.bot_enabled.is_(True), us.c.mode == "simulated",
               us.c.timeframe_minutes == s.c.timeframe_minutes, m.c.code == s.c.market))
    if target_user_id is not None:
        statement = statement.where(us.c.user_id == target_user_id)
    if target_mode is not None:
        statement = statement.where(us.c.mode == target_mode)
    with SessionLocal() as db:
        return [ExecutionTarget(row.id, row.subscription_id, row.user_id, row.action,
                                row.market, row.close_price, row.invest_ratio,
                                row.allocated_amount, row.paused)
                for row in db.execute(statement).all()]


def execute_target(target: ExecutionTarget) -> bool:
    if target.action == "buy" and target.paused:
        return False
    with SessionLocal() as db:
        execution = StrategyExecution(signal_id=target.signal_id,
            user_strategy_id=target.user_strategy_id, user_id=target.user_id,
            mode="simulated", action=target.action, market=target.market,
            status="simulated_pending", price=target.price)
        db.add(execution)
        try:
            db.flush()
            allocation = execute_paper_order(db, execution, target.invest_ratio,
                                             target.allocated_amount)
            if allocation is not None:
                enqueue_allocation_changed(db, execution, allocation)
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False


def dispatch_signal(signal_id: int, target_user_id: int | None = None,
                    target_mode: str | None = None) -> int:
    return sum(execute_target(target) for target in load_targets(
        signal_id, target_user_id, target_mode))
