from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models.execution import TradingExecutionRequest
from signaltrade_trading.models.message_outbox import MessageOutbox


def enqueue_manual_liquidation(db, request: TradingExecutionRequest) -> MessageOutbox:
    db.flush()
    key = f"manual-liquidation:{request.id}"
    envelope = MessageEnvelope.create(
        message_type="ManualLiquidationRequested", producer="trading-api",
        correlation_id=key, idempotency_key=key,
        payload={"execution_request_id": request.id},
    )
    row = MessageOutbox(
        message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at,
    )
    db.add(row)
    return row
