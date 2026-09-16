from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from signaltrade_trading.models import (
    StrategyExecution,
    strategy_runtime_table,
    supported_market_table,
    user_strategy_table,
)
from signaltrade_trading.models.paper import PaperAccount, PaperLedger


@dataclass(frozen=True, slots=True)
class PaperAccountValue:
    cash_balance: Decimal
    net_deposit: Decimal
    holdings_value: Decimal = Decimal("0")

    @property
    def total_equity(self) -> Decimal:
        return self.cash_balance + self.holdings_value

    @property
    def profit_loss(self) -> Decimal:
        return self.total_equity - self.net_deposit


def get_or_create_paper_account(db: Session, user_id: int, *, lock: bool = False) -> PaperAccount:
    query = db.query(PaperAccount).filter(PaperAccount.user_id == user_id)
    account = query.with_for_update().first() if lock else query.first()
    if account is None:
        account = PaperAccount(user_id=user_id, cash_balance=0, net_deposit=0)
        db.add(account)
        db.flush()
    return account


def account_value(db: Session, user_id: int) -> PaperAccountValue:
    account = get_or_create_paper_account(db, user_id)
    subscriptions = db.execute(
        user_strategy_table.select().where(
            user_strategy_table.c.user_id == user_id,
            user_strategy_table.c.mode == "simulated",
        )
    ).mappings().all()
    if not subscriptions:
        return PaperAccountValue(Decimal(account.cash_balance), Decimal(account.net_deposit))

    subscription_ids = [subscription["id"] for subscription in subscriptions]
    executions_by_subscription: dict[int, list[StrategyExecution]] = defaultdict(list)
    executions = db.query(StrategyExecution).filter(
        StrategyExecution.user_strategy_id.in_(subscription_ids),
        StrategyExecution.status == "simulated_success",
    ).order_by(
        StrategyExecution.user_strategy_id,
        StrategyExecution.created_at,
        StrategyExecution.id,
    ).all()
    for execution in executions:
        executions_by_subscription[execution.user_strategy_id].append(execution)

    market_ids = {subscription["market_id"] for subscription in subscriptions}
    markets = db.execute(
        supported_market_table.select().with_only_columns(
            supported_market_table.c.id,
            supported_market_table.c.code,
        ).where(supported_market_table.c.id.in_(market_ids))
    ).all()
    market_by_id = {market_id: code for market_id, code in markets}

    strategy_ids = {subscription["strategy_id"] for subscription in subscriptions}
    market_codes = set(market_by_id.values())
    timeframes = {subscription["timeframe_minutes"] for subscription in subscriptions}
    runtimes = db.execute(
        strategy_runtime_table.select().with_only_columns(
            strategy_runtime_table.c.strategy_id,
            strategy_runtime_table.c.market,
            strategy_runtime_table.c.timeframe_minutes,
            strategy_runtime_table.c.close_price,
        ).where(
            strategy_runtime_table.c.strategy_id.in_(strategy_ids),
            strategy_runtime_table.c.market.in_(market_codes),
            strategy_runtime_table.c.timeframe_minutes.in_(timeframes),
        )
    ).all()
    runtime_price = {
        (strategy_id, market, timeframe): close_price
        for strategy_id, market, timeframe, close_price in runtimes
    }

    holdings = Decimal("0")
    for subscription in subscriptions:
        volume = Decimal("0")
        average_buy_price = Decimal("0")
        for execution in executions_by_subscription[subscription["id"]]:
            filled = Decimal(str(execution.executed_volume or 0))
            if execution.action == "buy":
                volume += filled
                average_buy_price = Decimal(str(execution.average_price or execution.price or 0))
            else:
                volume -= filled
                if volume <= 0:
                    volume = Decimal("0")
                    average_buy_price = Decimal("0")
        if volume <= 0:
            continue
        market = market_by_id[subscription["market_id"]]
        mark_price = runtime_price.get((
            subscription["strategy_id"], market, subscription["timeframe_minutes"],
        ))
        holdings += volume * Decimal(str(mark_price or average_buy_price))
    return PaperAccountValue(
        Decimal(account.cash_balance),
        Decimal(account.net_deposit),
        holdings,
    )


def adjust_net_deposit(db: Session, user_id: int, target: Decimal,
                       protected_cash: Decimal = Decimal("0")) -> PaperAccount:
    if target < 0:
        raise ValueError("모의 투자금은 0원 이상이어야 합니다.")
    account = get_or_create_paper_account(db, user_id, lock=True)
    current = Decimal(account.net_deposit)
    difference = (target - current).quantize(Decimal("0.01"))
    cash = Decimal(account.cash_balance)
    if difference < 0 and cash + difference < protected_cash:
        raise ValueError("전략에 예약된 주문 금액과 수수료를 제외한 현금만 출금할 수 있습니다.")
    if difference != 0:
        account.net_deposit = target
        account.cash_balance = cash + difference
        db.add(PaperLedger(account_id=account.id,
                           kind="deposit" if difference > 0 else "withdraw",
                           amount=difference, balance_after=account.cash_balance))
        db.commit(); db.refresh(account)
    return account


def apply_cash_adjustment(db: Session, user_id: int, amount: Decimal, action: str,
                          protected_cash: Decimal = Decimal("0")) -> PaperAccount:
    if amount <= 0:
        raise ValueError("입출금 금액은 0원보다 커야 합니다.")
    if action not in {"deposit", "withdraw"}:
        raise ValueError("지원하지 않는 입출금 구분입니다.")
    account = get_or_create_paper_account(db, user_id, lock=True)
    cash, net = Decimal(account.cash_balance), Decimal(account.net_deposit)
    if action == "withdraw" and cash - amount < protected_cash:
        raise ValueError("전략에 예약된 주문 금액과 수수료를 제외한 현금만 출금할 수 있습니다.")
    if action == "withdraw" and amount > net:
        raise ValueError("출금하려는 금액이 현재 순입금액보다 큽니다.")
    signed = amount if action == "deposit" else -amount
    account.cash_balance = cash + signed
    account.net_deposit = net + signed
    db.add(PaperLedger(account_id=account.id, kind=action, amount=signed,
                       balance_after=account.cash_balance))
    db.commit(); db.refresh(account)
    return account
