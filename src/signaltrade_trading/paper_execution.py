from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.paper import PaperLedger
from signaltrade_trading.paper_accounts import get_or_create_paper_account

PAPER_FEE_RATE = Decimal("0.0005")
MIN_KRW_ORDER = Decimal("5000")


def _position_volume(db: Session, subscription_id: int) -> Decimal:
    rows = db.query(StrategyExecution).filter_by(
        user_strategy_id=subscription_id, status="simulated_success"
    ).order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    volume = Decimal("0")
    for row in rows:
        filled = Decimal(str(row.executed_volume or 0))
        volume += filled if row.action == "buy" else -filled
    return max(Decimal("0"), volume)


def execute_paper_order(db: Session, execution: StrategyExecution,
                        invest_ratio: float, allocated_amount: float | None) -> float | None:
    account = get_or_create_paper_account(db, execution.user_id, lock=True)
    price = Decimal(str(execution.price))
    position = _position_volume(db, execution.user_strategy_id)
    if execution.action == "buy":
        if position > 0:
            execution.status = "simulated_skipped"
            execution.error_message = "기존 모의 포지션을 보유 중입니다."
            return None
        cash = Decimal(account.cash_balance)
        budget = (Decimal(str(allocated_amount)) if allocated_amount is not None
                  else cash * Decimal(str(invest_ratio)))
        amount = min(max(Decimal("0"), budget), cash).quantize(Decimal("1"), rounding=ROUND_DOWN)
        if amount * (Decimal("1") + PAPER_FEE_RATE) > cash:
            amount = (cash / (Decimal("1") + PAPER_FEE_RATE)).quantize(Decimal("1"), rounding=ROUND_DOWN)
        if amount < MIN_KRW_ORDER:
            execution.status = "simulated_failed"
            execution.error_message = "모의 주문금액이 최소 주문금액 5,000원보다 작습니다."
            return None
        fee = (amount * PAPER_FEE_RATE).quantize(Decimal("0.01"))
        volume = amount / price
        total = (amount + fee).quantize(Decimal("0.01"))
        account.cash_balance = Decimal(account.cash_balance) - total
        execution.status = "simulated_success"; execution.order_amount = float(amount)
        execution.executed_volume = float(volume); execution.average_price = float(price)
        execution.paid_fee = float(fee)
        db.add(PaperLedger(account_id=account.id, strategy_execution_id=execution.id,
                           kind="buy", amount=-total, balance_after=account.cash_balance))
        return float(amount) if allocated_amount is None else None
    if execution.action == "sell":
        if position <= 0:
            execution.status = "simulated_skipped"; execution.error_message = "보유 수량이 없습니다."
            return None
        gross = position * price; fee = (gross * PAPER_FEE_RATE).quantize(Decimal("0.01"))
        proceeds = (gross - fee).quantize(Decimal("0.01"))
        account.cash_balance = Decimal(account.cash_balance) + proceeds
        execution.status = "simulated_success"; execution.order_amount = float(gross)
        execution.order_volume = float(position); execution.executed_volume = float(position)
        execution.average_price = float(price); execution.paid_fee = float(fee)
        db.add(PaperLedger(account_id=account.id, strategy_execution_id=execution.id,
                           kind="sell", amount=proceeds, balance_after=account.cash_balance))
        return float(proceeds.quantize(Decimal("1"), rounding=ROUND_DOWN))
    execution.status = "simulated_failed"; execution.error_message = "지원하지 않는 주문 방향입니다."
    return None
