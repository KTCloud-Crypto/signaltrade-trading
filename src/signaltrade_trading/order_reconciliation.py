"""Refresh non-final Upbit orders and persist their latest settlement state."""

import logging

from sqlalchemy import select

from signaltrade_trading.allocation_events import enqueue_allocation_changed
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.identity_client import (
    ExchangeCredentialsUnavailable,
    get_exchange_credentials,
)
from signaltrade_trading.live_order import fetch_order_result
from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.external import (
    strategy_signal_table,
    strategy_table,
    user_strategy_table,
    user_table,
)
from signaltrade_trading.models.trade import Trade
from signaltrade_trading.notification_events import enqueue_settlement_notification

logger = logging.getLogger(__name__)
PENDING_STATUSES = ("submitted", "partially_filled")
FINAL_STATUSES = {"success", "cancelled", "failed"}


def _pending_rows(db):
    execution = StrategyExecution.__table__
    statement = (
        select(
            StrategyExecution,
            strategy_signal_table.c.source,
            strategy_table.c.name.label("strategy_name"),
            user_table.c.telegram_chat_id,
            user_strategy_table.c.allocated_amount,
        )
        .select_from(
            execution.join(
                user_strategy_table,
                user_strategy_table.c.id == execution.c.user_strategy_id,
            )
            .join(strategy_table, strategy_table.c.id == user_strategy_table.c.strategy_id)
            .join(user_table, user_table.c.id == execution.c.user_id)
            .outerjoin(strategy_signal_table, strategy_signal_table.c.id == execution.c.signal_id)
        )
        .where(
            execution.c.status.in_(PENDING_STATUSES),
            execution.c.order_uuid.is_not(None),
        )
    )
    return db.execute(statement).all()


def _allocation_after_settlement(execution, previous_allocated_amount: float | None) -> float | None:
    if execution.status != "success":
        return None
    if execution.action == "buy" and previous_allocated_amount is None:
        return execution.order_amount
    if execution.action == "sell":
        return max(
            0.0,
            (execution.average_price or execution.price) * (execution.executed_volume or 0)
            - (execution.paid_fee or 0),
        )
    return None


def reconcile_pending_orders() -> int:
    settled = 0
    with SessionLocal() as db:
        for row in _pending_rows(db):
            execution = row.StrategyExecution
            try:
                credentials = get_exchange_credentials(execution.user_id)
            except ExchangeCredentialsUnavailable as error:
                logger.warning(
                    "Pending order credentials unavailable: execution=%s error=%s",
                    execution.id,
                    error,
                )
                continue
            result = fetch_order_result(
                access_key=credentials.access_key,
                secret_key=credentials.secret_key,
                order_uuid=execution.order_uuid,
            )
            if result is None:
                continue

            previous_status = execution.status
            execution.status = result.status
            execution.executed_volume = result.executed_volume
            execution.average_price = result.average_price
            execution.paid_fee = result.paid_fee
            execution.error_message = result.error_message
            trade = db.query(Trade).filter_by(strategy_execution_id=execution.id).one_or_none()
            if trade is not None:
                trade.status = result.status
                trade.volume = result.executed_volume
                trade.price = result.average_price or execution.price
                trade.raw_response = result.raw_response

            if result.status in FINAL_STATUSES and previous_status not in FINAL_STATUSES:
                settled += 1
                allocation = _allocation_after_settlement(execution, row.allocated_amount)
                if allocation is not None:
                    enqueue_allocation_changed(db, execution, allocation)
                enqueue_settlement_notification(
                    db,
                    execution=execution,
                    chat_id=row.telegram_chat_id,
                    strategy_name=row.strategy_name,
                    signal_source=row.source or "manual",
                )
            db.commit()
    return settled
