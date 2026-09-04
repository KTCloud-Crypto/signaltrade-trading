from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.external import user_strategy_table

FEE_BUFFER_RATE = Decimal("0.0005")


def _position_volume(db: Session, subscription_id: int) -> Decimal:
    rows = db.query(StrategyExecution).filter_by(
        user_strategy_id=subscription_id,
        mode="simulated",
        status="simulated_success",
    ).order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    volume = Decimal("0")
    for row in rows:
        filled = Decimal(str(row.executed_volume or 0))
        volume += filled if row.action == "buy" else -filled
    return max(Decimal("0"), volume)


def reserved_amount(db: Session, user_id: int) -> Decimal:
    subscriptions = db.execute(user_strategy_table.select().where(
        user_strategy_table.c.user_id == user_id,
        user_strategy_table.c.mode == "simulated",
        user_strategy_table.c.enabled.is_(True),
        user_strategy_table.c.allocated_amount.is_not(None),
    )).mappings().all()
    return sum((
        Decimal(str(row["allocated_amount"]))
        for row in subscriptions
        if _position_volume(db, row["id"]) <= 0
    ), Decimal("0"))


def available_for_order(cash_balance: Decimal, reserved: Decimal) -> Decimal:
    free = max(Decimal("0"), cash_balance-reserved)
    return (free/(Decimal("1")+FEE_BUFFER_RATE)).quantize(Decimal("1"), rounding=ROUND_DOWN)


def cash_required_for_reservations(reserved: Decimal) -> Decimal:
    """예약된 주문 원금과 예상 매수 수수료를 합친 보호 대상 현금입니다."""
    return (max(Decimal("0"), reserved) * (Decimal("1") + FEE_BUFFER_RATE)).quantize(
        Decimal("0.01")
    )


def realized_profit_by_execution(db: Session, user_id: int) -> dict[int, float]:
    rows = db.query(StrategyExecution).filter_by(
        user_id=user_id, mode="simulated", status="simulated_success"
    ).order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.user_strategy_id].append(row)
    result: dict[int, float] = {}
    for executions in grouped.values():
        volume = cost = Decimal("0")
        for row in executions:
            quantity = Decimal(str(row.executed_volume or 0))
            price = Decimal(str(row.average_price or row.price or 0))
            fee = Decimal(str(row.paid_fee or 0))
            if quantity <= 0 or price <= 0:
                continue
            if row.action == "buy":
                volume += quantity
                cost += quantity*price+fee
            elif row.action == "sell" and volume > 0:
                removed = min(quantity, volume)
                removed_cost = removed*(cost/volume)
                matched_fee = fee*(removed/quantity)
                result[row.id] = float(removed*price-matched_fee-removed_cost)
                volume -= removed
                cost = max(Decimal("0"), cost-removed_cost)
    return result
