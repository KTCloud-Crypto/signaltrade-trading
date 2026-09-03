from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from signaltrade_trading.database import get_db
from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user

strategy_router = APIRouter(prefix="/strategies", tags=["Trading"])
trade_router = APIRouter(prefix="/trades", tags=["Trades"])


class StrategyExecutionOut(BaseModel):
    id: int
    strategy_name: str
    strategy_code: str
    action: Literal["buy", "sell"]
    market: str
    mode: Literal["simulated", "live"]
    status: str
    price: float
    order_amount: float | None
    order_volume: float | None
    executed_volume: float | None
    average_price: float | None
    paid_fee: float | None
    entry_price: float | None
    transaction_amount: float | None
    realized_profit_loss: float | None
    error_message: str | None
    notification_sent: bool
    exit_reason: str | None
    created_at: datetime


class TradeOut(BaseModel):
    id: int
    strategy_execution_id: int | None
    strategy_name: str | None = None
    ticker: str
    action: str
    price: float | None
    volume: float | None
    status: str
    created_at: datetime


@strategy_router.get("/executions", response_model=list[StrategyExecutionOut])
def executions(mode: Literal["simulated", "live"] = Query("simulated"),
               db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT e.*, s.name AS strategy_name, s.code AS strategy_code, ss.source
        FROM strategy_execution e
        JOIN user_strategy us ON us.id=e.user_strategy_id
        JOIN strategy s ON s.id=us.strategy_id
        LEFT JOIN strategy_signal ss ON ss.id=e.signal_id
        WHERE e.user_id=:user_id AND e.mode=:mode
          AND COALESCE(ss.source, '') <> 'external_sync' AND s.code <> 'manual_hold_v1'
        ORDER BY e.created_at DESC LIMIT 100
    """), {"user_id": user.id, "mode": mode}).mappings().all()
    result = []
    for row in rows:
        price = row["average_price"] or row["price"]
        volume = row["executed_volume"] or row["order_volume"]
        amount = float(price * volume) if price is not None and volume is not None else None
        result.append(StrategyExecutionOut(
            id=row["id"], strategy_name=row["strategy_name"], strategy_code=row["strategy_code"],
            action=row["action"], market=row["market"], mode=row["mode"], status=row["status"],
            price=row["price"], order_amount=row["order_amount"], order_volume=row["order_volume"],
            executed_volume=row["executed_volume"], average_price=row["average_price"],
            paid_fee=row["paid_fee"], entry_price=None, transaction_amount=amount,
            realized_profit_loss=None, error_message=row["error_message"],
            notification_sent=row["notification_sent"],
            exit_reason={"stop_loss": "손절", "take_profit": "목표 수익률", "manual": "수동 매도"}.get(row["source"] or "manual"),
            created_at=row["created_at"]))
    return result


@trade_router.get("", response_model=list[TradeOut])
def trades(db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT t.*, s.name AS strategy_name
        FROM trade t LEFT JOIN strategy_execution e ON e.id=t.strategy_execution_id
        LEFT JOIN user_strategy us ON us.id=e.user_strategy_id
        LEFT JOIN strategy s ON s.id=us.strategy_id
        WHERE t.user_id=:user_id ORDER BY t.created_at DESC LIMIT 200
    """), {"user_id": user.id}).mappings().all()
    return [TradeOut(id=row["id"], strategy_execution_id=row["strategy_execution_id"],
        strategy_name=row["strategy_name"], ticker=row["ticker"], action=row["action"],
        price=row["price"], volume=row["volume"], status=row["status"], created_at=row["created_at"])
        for row in rows]
