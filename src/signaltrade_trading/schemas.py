from datetime import datetime

from pydantic import BaseModel, Field


class PaperAccountAdjustmentIn(BaseModel):
    target_net_deposit: float = Field(ge=0)


class PaperAccountCashIn(BaseModel):
    amount: float = Field(gt=0)


class PaperAccountOut(BaseModel):
    cash_balance: float
    reserved_amount: float
    available_for_order: float
    net_deposit: float
    holdings_value: float
    total_equity: float
    profit_loss: float
    return_rate: float | None


class PaperLedgerOut(BaseModel):
    id: int
    kind: str
    amount: float
    balance_after: float
    created_at: datetime
    realized_profit_loss: float | None = None
