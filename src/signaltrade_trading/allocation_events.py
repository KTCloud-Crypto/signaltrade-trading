from sqlalchemy.orm import Session
from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models.execution import StrategyExecution
from signaltrade_trading.models.message_outbox import MessageOutbox


def enqueue_allocation_changed(db: Session, execution: StrategyExecution,
                               allocated_amount: float) -> MessageOutbox:
    db.flush()
    key = f"execution-allocation:{execution.id}"
    envelope = MessageEnvelope.create(message_type="AllocationChanged", producer="trading",
        correlation_id=key, idempotency_key=key,
        payload={"execution_id": execution.id, "user_strategy_id": execution.user_strategy_id,
                 "allocated_amount": allocated_amount})
    row = MessageOutbox(message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at)
    db.add(row)
    return row
