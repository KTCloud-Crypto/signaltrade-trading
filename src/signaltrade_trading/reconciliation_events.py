from signaltrade_trading.database import SessionLocal
from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models.execution import StrategyExecution


def apply_position_reconciled(envelope: MessageEnvelope) -> int:
    if envelope.message_type != "PositionReconciled":
        raise ValueError(f"unsupported reconciliation event: {envelope.message_type}")
    subscription_id = envelope.payload.get("user_strategy_id")
    if not isinstance(subscription_id, int) or subscription_id <= 0:
        raise ValueError("PositionReconciled.user_strategy_id must be a positive integer")
    with SessionLocal() as db:
        rows = db.query(StrategyExecution).filter_by(
            user_strategy_id=subscription_id, action="sell", status="uncertain").all()
        for row in rows:
            row.status = "reconciled"
            row.error_message = "실제 잔고 차이를 사용자가 전략 포지션에 반영했습니다."
        db.commit()
        return len(rows)
