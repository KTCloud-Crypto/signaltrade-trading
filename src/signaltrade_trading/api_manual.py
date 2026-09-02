from decimal import Decimal
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from signaltrade_trading.database import get_db
from signaltrade_trading.identity_client import AuthenticatedUser, get_current_user
from signaltrade_trading.manual_commands import enqueue_manual_liquidation
from signaltrade_trading.market_client import MarketPriceUnavailable, get_current_price
from signaltrade_trading.models.execution import StrategyExecution, TradingExecutionRequest
from signaltrade_trading.models.external import (
    strategy_table, supported_market_table, user_strategy_table,
)

router = APIRouter(prefix="/strategies", tags=["Manual Trading"])


class ManualLiquidationOut(BaseModel):
    execution_request_id: int
    user_strategy_id: int
    mode: str
    action: str = "sell"
    market: str
    reference_price: float


def _position_volume(db: Session, subscription_id: int, mode: str) -> Decimal:
    success_status = "simulated_success" if mode == "simulated" else "success"
    rows = db.query(StrategyExecution).filter_by(
        user_strategy_id=subscription_id, mode=mode, status=success_status,
    ).order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    volume = Decimal("0")
    for row in rows:
        filled = Decimal(str(row.executed_volume or 0))
        volume += filled if row.action == "buy" else -filled
    return max(Decimal("0"), volume)


def _subscription(db: Session, user_id: int, strategy_id: int, mode: str, market: str):
    us, st, sm = user_strategy_table, strategy_table, supported_market_table
    return db.execute(
        select(us.c.id, us.c.invest_ratio, us.c.allocated_amount, us.c.paused,
               sm.c.code.label("market"))
        .select_from(us.join(st, st.c.id == us.c.strategy_id)
                     .join(sm, sm.c.id == us.c.market_id))
        .where(us.c.user_id == user_id, us.c.strategy_id == strategy_id,
               us.c.mode == mode, sm.c.code == market.upper(), st.c.enabled.is_(True))
    ).first()


async def _create_request(db: Session, user: AuthenticatedUser, row,
                          mode: str, idempotency_key: str) -> TradingExecutionRequest:
    existing = db.query(TradingExecutionRequest).filter_by(
        idempotency_key=idempotency_key, user_id=user.id,
    ).one_or_none()
    if existing is not None:
        return existing
    if _position_volume(db, row.id, mode) <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="매도할 포지션이 없습니다.")
    try:
        price = await get_current_price(row.market)
    except MarketPriceUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(error)) from error
    request = TradingExecutionRequest(
        idempotency_key=idempotency_key, user_strategy_id=row.id, user_id=user.id,
        mode=mode, action="sell", market=row.market,
        reference_price=price, source="manual",
    )
    db.add(request)
    enqueue_manual_liquidation(db, request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(TradingExecutionRequest).filter_by(
            idempotency_key=idempotency_key, user_id=user.id,
        ).one_or_none()
        if existing is None:
            raise
        return existing
    db.refresh(request)
    return request


def _out(request: TradingExecutionRequest) -> ManualLiquidationOut:
    return ManualLiquidationOut(
        execution_request_id=request.id, user_strategy_id=request.user_strategy_id,
        mode=request.mode, market=request.market, reference_price=request.reference_price,
    )


@router.post("/liquidate-all", response_model=list[ManualLiquidationOut])
async def liquidate_all(
    mode: Literal["simulated", "live"] = Query("simulated"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[ManualLiquidationOut]:
    if user.execution_mode != mode:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="현재 선택한 투자 모드와 요청 모드가 다릅니다.")
    us, st, sm = user_strategy_table, strategy_table, supported_market_table
    rows = db.execute(
        select(us.c.id, us.c.invest_ratio, us.c.allocated_amount, us.c.paused,
               sm.c.code.label("market"))
        .select_from(us.join(st, st.c.id == us.c.strategy_id)
                     .join(sm, sm.c.id == us.c.market_id))
        .where(us.c.user_id == user.id, us.c.mode == mode, st.c.enabled.is_(True))
    ).all()
    root_key = idempotency_key or str(uuid4())
    requests = []
    for row in rows:
        if _position_volume(db, row.id, mode) <= 0:
            continue
        requests.append(await _create_request(
            db, user, row, mode, f"{root_key}:{row.id}"
        ))
    return [_out(request) for request in requests]


@router.post("/{strategy_id}/manual-sell", response_model=ManualLiquidationOut)
async def manual_sell(
    strategy_id: int,
    mode: Literal["simulated", "live"] = Query("simulated"),
    market: str = Query("KRW-BTC"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ManualLiquidationOut:
    if user.execution_mode != mode:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="현재 선택한 투자 모드와 요청 모드가 다릅니다.")
    row = _subscription(db, user.id, strategy_id, mode, market)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="전략 설정을 찾을 수 없습니다.")
    request = await _create_request(
        db, user, row, mode, idempotency_key or str(uuid4())
    )
    return _out(request)
