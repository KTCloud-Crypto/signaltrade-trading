from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from signaltrade_trading.database import get_db
from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user
from signaltrade_trading.models.paper import PaperAccount, PaperLedger
from signaltrade_trading.paper_accounts import account_value, adjust_net_deposit, apply_cash_adjustment
from signaltrade_trading.schemas import PaperAccountAdjustmentIn, PaperAccountCashIn, PaperAccountOut, PaperLedgerOut

router = APIRouter(prefix="/paper-account", tags=["Paper Trading"])


def _account_out(db: Session, user_id: int) -> PaperAccountOut:
    value = account_value(db, user_id)
    return_rate = float(value.profit_loss / value.net_deposit * 100) if value.net_deposit > 0 else None
    return PaperAccountOut(cash_balance=float(value.cash_balance), reserved_amount=0,
                           available_for_order=float(value.cash_balance), net_deposit=float(value.net_deposit),
                           holdings_value=float(value.holdings_value), total_equity=float(value.total_equity),
                           profit_loss=float(value.profit_loss), return_rate=return_rate)


@router.get("", response_model=PaperAccountOut)
def read_paper_account(db: Session = Depends(get_db),
                       user: AuthenticatedUser = Depends(get_current_user)) -> PaperAccountOut:
    account_value(db, user.id); db.commit()
    return _account_out(db, user.id)


@router.put("", response_model=PaperAccountOut)
def update_paper_account(payload: PaperAccountAdjustmentIn, db: Session = Depends(get_db),
                         user: AuthenticatedUser = Depends(get_current_user)) -> PaperAccountOut:
    try:
        adjust_net_deposit(db, user.id, Decimal(str(payload.target_net_deposit)))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _account_out(db, user.id)


def _cash(payload: PaperAccountCashIn, action: str, db: Session, user: AuthenticatedUser):
    try:
        apply_cash_adjustment(db, user.id, Decimal(str(payload.amount)), action)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _account_out(db, user.id)


@router.post("/deposit", response_model=PaperAccountOut)
def deposit(payload: PaperAccountCashIn, db: Session = Depends(get_db),
            user: AuthenticatedUser = Depends(get_current_user)) -> PaperAccountOut:
    return _cash(payload, "deposit", db, user)


@router.post("/withdraw", response_model=PaperAccountOut)
def withdraw(payload: PaperAccountCashIn, db: Session = Depends(get_db),
             user: AuthenticatedUser = Depends(get_current_user)) -> PaperAccountOut:
    return _cash(payload, "withdraw", db, user)


@router.get("/ledger", response_model=list[PaperLedgerOut])
def ledger(db: Session = Depends(get_db),
           user: AuthenticatedUser = Depends(get_current_user)) -> list[PaperLedgerOut]:
    account = db.query(PaperAccount).filter_by(user_id=user.id).first()
    if account is None:
        return []
    rows = db.query(PaperLedger).filter_by(account_id=account.id).order_by(PaperLedger.created_at.desc()).limit(100).all()
    return [PaperLedgerOut(id=row.id, kind=row.kind, amount=float(row.amount),
                           balance_after=float(row.balance_after), created_at=row.created_at)
            for row in rows]
