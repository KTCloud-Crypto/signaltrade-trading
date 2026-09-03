from dataclasses import dataclass

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from signaltrade_trading.allocation_events import enqueue_allocation_changed
from signaltrade_trading.database import SessionLocal
from signaltrade_trading.identity_client import (
    ExchangeCredentials,
    ExchangeCredentialsUnavailable,
    get_exchange_credentials,
)
from signaltrade_trading.live_order import (
    LiveOrderResult,
    execute_market_buy,
    execute_market_sell,
)
from signaltrade_trading.models.execution import StrategyExecution, TradingExecutionRequest
from signaltrade_trading.models.trade import Trade
from signaltrade_trading.models.external import (strategy_signal_table, strategy_table,
    supported_market_table, user_strategy_table, user_table)
from signaltrade_trading.paper_execution import execute_paper_order
from signaltrade_trading.preflight import PreflightResult, validate_buy, validate_sell
from signaltrade_trading.notification_events import enqueue_execution_notification


@dataclass(frozen=True, slots=True)
class ExecutionTarget:
    signal_id: int | None
    user_strategy_id: int
    user_id: int
    action: str
    market: str
    price: float
    invest_ratio: float
    allocated_amount: float | None
    paused: bool
    mode: str
    live_trading_enabled: bool
    telegram_chat_id: str | None
    strategy_name: str
    execution_request_id: int | None = None


def load_targets(signal_id: int, target_user_id: int | None = None,
                 target_mode: str | None = None) -> list[ExecutionTarget]:
    s, st, us, m, u = (strategy_signal_table, strategy_table, user_strategy_table,
                       supported_market_table, user_table)
    statement = (select(s.c.id, us.c.id.label("subscription_id"), us.c.user_id,
                        s.c.action, s.c.market, s.c.close_price, us.c.invest_ratio,
                        us.c.allocated_amount, us.c.paused, us.c.mode,
                        u.c.live_trading_enabled, u.c.telegram_chat_id,
                        st.c.name.label("strategy_name"))
        .select_from(s.join(st, st.c.id == s.c.strategy_id)
                     .join(us, us.c.strategy_id == st.c.id)
                     .join(m, m.c.id == us.c.market_id)
                     .join(u, u.c.id == us.c.user_id))
        .where(s.c.id == signal_id, st.c.enabled.is_(True), us.c.enabled.is_(True),
               u.c.bot_enabled.is_(True),
               us.c.timeframe_minutes == s.c.timeframe_minutes, m.c.code == s.c.market))
    if target_user_id is not None:
        statement = statement.where(us.c.user_id == target_user_id)
    if target_mode is not None:
        statement = statement.where(us.c.mode == target_mode)
    with SessionLocal() as db:
        return [ExecutionTarget(row.id, row.subscription_id, row.user_id, row.action,
                                row.market, row.close_price, row.invest_ratio,
                                row.allocated_amount, row.paused, row.mode,
                                row.live_trading_enabled, row.telegram_chat_id,
                                row.strategy_name)
                for row in db.execute(statement).all()]


def _live_position_volume(db, user_strategy_id: int) -> float:
    rows = db.query(StrategyExecution).filter_by(
        user_strategy_id=user_strategy_id, mode="live", status="success"
    ).order_by(StrategyExecution.created_at, StrategyExecution.id).all()
    volume = Decimal("0")
    for row in rows:
        filled = Decimal(str(row.executed_volume or 0))
        volume += filled if row.action == "buy" else -filled
    return float(max(Decimal("0"), volume))


def _prepare_live(
    target: ExecutionTarget, db
) -> tuple[PreflightResult, ExchangeCredentials | None]:
    if not target.live_trading_enabled:
        return PreflightResult(False, None, "사용자의 실전투자 설정이 비활성화되어 있습니다."), None
    pending = db.query(StrategyExecution.id).filter(
        StrategyExecution.user_strategy_id == target.user_strategy_id,
        StrategyExecution.action == target.action,
        StrategyExecution.mode == "live",
        StrategyExecution.status.in_({"ready", "submitted", "partially_filled"}),
    ).first()
    if pending is not None:
        return PreflightResult(False, None, "이미 같은 방향의 주문이 진행 중입니다."), None
    try:
        credentials = get_exchange_credentials(target.user_id)
    except ExchangeCredentialsUnavailable as error:
        return PreflightResult(False, None, str(error)), None
    if target.action == "buy":
        if _live_position_volume(db, target.user_strategy_id) > 0:
            return PreflightResult(False, None, "이 전략으로 보유 중인 수량이 있습니다."), credentials
        return validate_buy(access_key=credentials.access_key, secret_key=credentials.secret_key,
                            market=target.market, invest_ratio=target.invest_ratio,
                            allocated_amount=target.allocated_amount), credentials
    if target.action == "sell":
        return validate_sell(access_key=credentials.access_key, secret_key=credentials.secret_key,
                             market=target.market, reference_price=target.price,
                             strategy_volume=_live_position_volume(
                                 db, target.user_strategy_id)), credentials
    return PreflightResult(False, None, "지원하지 않는 주문 방향입니다."), credentials


def _place_live_order(target: ExecutionTarget, preflight: PreflightResult,
                      credentials) -> LiveOrderResult:
    if target.action == "buy":
        return execute_market_buy(access_key=credentials.access_key,
                                  secret_key=credentials.secret_key,
                                  market=target.market,
                                  amount=preflight.order_amount or 0)
    return execute_market_sell(access_key=credentials.access_key,
                               secret_key=credentials.secret_key,
                               market=target.market,
                               volume=preflight.order_volume or 0)


def _execute_live_target(target: ExecutionTarget) -> bool:
    with SessionLocal() as db:
        db.execute(
            select(user_strategy_table.c.id)
            .where(user_strategy_table.c.id == target.user_strategy_id)
            .with_for_update()
        ).one()
        preflight, credentials = _prepare_live(target, db)
        execution = StrategyExecution(
            signal_id=target.signal_id,
            execution_request_id=target.execution_request_id,
            user_strategy_id=target.user_strategy_id,
            user_id=target.user_id, mode="live", action=target.action,
            market=target.market,
            status="ready" if preflight.ready else "validation_failed",
            price=target.price, order_amount=preflight.order_amount,
            order_volume=preflight.order_volume, error_message=preflight.reason,
        )
        db.add(execution)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
        if not preflight.ready or credentials is None:
            return True
        db.refresh(execution)
        try:
            order = _place_live_order(target, preflight, credentials)
        except Exception as error:
            execution.status = "failed"
            execution.error_message = str(error)
        else:
            execution.status = order.status
            execution.order_uuid = order.order_uuid
            execution.executed_volume = order.executed_volume
            execution.average_price = order.average_price
            execution.paid_fee = order.paid_fee
            execution.error_message = order.error_message
            db.add(Trade(user_id=target.user_id,
                         strategy_execution_id=execution.id,
                         ticker=target.market, action=target.action,
                         price=order.average_price or target.price,
                         volume=order.executed_volume, status=order.status,
                         raw_response=order.raw_response))
            if execution.status == "success":
                allocation = (execution.order_amount if target.action == "buy" and
                              target.allocated_amount is None else
                              max(0.0, (execution.average_price or target.price) *
                                  (execution.executed_volume or 0) -
                                  (execution.paid_fee or 0)) if target.action == "sell" else None)
                if allocation:
                    enqueue_allocation_changed(db, execution, allocation)
        enqueue_execution_notification(
            db, execution=execution, chat_id=target.telegram_chat_id,
            strategy_name=target.strategy_name,
        )
        db.commit()
        return True


def execute_target(target: ExecutionTarget) -> bool:
    if target.action == "buy" and target.paused:
        return False
    if target.mode == "live":
        return _execute_live_target(target)
    with SessionLocal() as db:
        execution = StrategyExecution(signal_id=target.signal_id,
            execution_request_id=target.execution_request_id,
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
            enqueue_execution_notification(
                db, execution=execution, chat_id=target.telegram_chat_id,
                strategy_name=target.strategy_name,
            )
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            return False


def dispatch_signal(signal_id: int, target_user_id: int | None = None,
                    target_mode: str | None = None) -> int:
    return sum(execute_target(target) for target in load_targets(
        signal_id, target_user_id, target_mode))


def load_manual_target(request_id: int) -> ExecutionTarget | None:
    request = TradingExecutionRequest
    us, st, u = user_strategy_table, strategy_table, user_table
    statement = (select(request, us.c.invest_ratio, us.c.allocated_amount,
                        us.c.paused, u.c.live_trading_enabled, u.c.telegram_chat_id,
                        st.c.name.label("strategy_name"))
        .select_from(request.__table__.join(us, us.c.id == request.user_strategy_id)
                     .join(st, st.c.id == us.c.strategy_id)
                     .join(u, u.c.id == request.user_id))
        .where(request.id == request_id, us.c.user_id == request.user_id))
    with SessionLocal() as db:
        row = db.execute(statement).first()
    if row is None:
        return None
    execution_request = row.TradingExecutionRequest
    return ExecutionTarget(
        signal_id=None, user_strategy_id=execution_request.user_strategy_id,
        user_id=execution_request.user_id, action=execution_request.action,
        market=execution_request.market, price=execution_request.reference_price,
        invest_ratio=row.invest_ratio, allocated_amount=row.allocated_amount,
        paused=row.paused, mode=execution_request.mode,
        live_trading_enabled=row.live_trading_enabled,
        telegram_chat_id=row.telegram_chat_id, strategy_name=row.strategy_name,
        execution_request_id=execution_request.id,
    )


def dispatch_manual_request(request_id: int) -> int:
    target = load_manual_target(request_id)
    return int(target is not None and execute_target(target))
