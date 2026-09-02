from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

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
    return PaperAccountValue(Decimal(account.cash_balance), Decimal(account.net_deposit))


def adjust_net_deposit(db: Session, user_id: int, target: Decimal) -> PaperAccount:
    if target < 0:
        raise ValueError("모의 투자금은 0원 이상이어야 합니다.")
    account = get_or_create_paper_account(db, user_id, lock=True)
    current = Decimal(account.net_deposit)
    difference = (target - current).quantize(Decimal("0.01"))
    cash = Decimal(account.cash_balance)
    if difference < 0 and -difference > cash:
        raise ValueError("출금하려는 금액이 모의계좌의 가용 현금보다 큽니다.")
    if difference != 0:
        account.net_deposit = target
        account.cash_balance = cash + difference
        db.add(PaperLedger(account_id=account.id,
                           kind="deposit" if difference > 0 else "withdraw",
                           amount=difference, balance_after=account.cash_balance))
        db.commit(); db.refresh(account)
    return account


def apply_cash_adjustment(db: Session, user_id: int, amount: Decimal, action: str) -> PaperAccount:
    if amount <= 0:
        raise ValueError("입출금 금액은 0원보다 커야 합니다.")
    if action not in {"deposit", "withdraw"}:
        raise ValueError("지원하지 않는 입출금 구분입니다.")
    account = get_or_create_paper_account(db, user_id, lock=True)
    cash, net = Decimal(account.cash_balance), Decimal(account.net_deposit)
    if action == "withdraw" and amount > cash:
        raise ValueError("출금하려는 금액이 모의계좌의 가용 현금보다 큽니다.")
    if action == "withdraw" and amount > net:
        raise ValueError("출금하려는 금액이 현재 순입금액보다 큽니다.")
    signed = amount if action == "deposit" else -amount
    account.cash_balance = cash + signed
    account.net_deposit = net + signed
    db.add(PaperLedger(account_id=account.id, kind=action, amount=signed,
                       balance_after=account.cash_balance))
    db.commit(); db.refresh(account)
    return account
