from signaltrade_trading.message_contract import MessageEnvelope
from signaltrade_trading.models.message_outbox import MessageOutbox


def enqueue_execution_notification(db, *, execution, chat_id: str | None,
                                   strategy_name: str) -> bool:
    if not chat_id or execution.status in {"simulated_skipped", "skipped"}:
        return False
    action = "매수" if execution.action == "buy" else "매도"
    mode = "모의" if execution.mode == "simulated" else "실전"
    amount = execution.order_amount
    if amount is None and execution.executed_volume:
        amount = (execution.average_price or execution.price) * execution.executed_volume
    ok = execution.status in {"success", "simulated_success", "submitted", "partially_filled"}
    message = (
        f"{'✅' if ok else '❌'} [{mode} {action}]\n\n"
        f"전략: {strategy_name}\n종목: {execution.market}\n"
        f"주문금액: {float(amount or 0):,.0f}원\n"
        f"체결수량: {float(execution.executed_volume or 0):.8f}\n"
        f"상태: {execution.status}"
    )
    key = f"execution-notification:{execution.id}"
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested", producer="trading-worker",
        correlation_id=key, idempotency_key=key,
        payload={"chat_id": str(chat_id), "message": message,
                 "notification_type": "order_execution", "user_id": execution.user_id},
    )
    db.add(MessageOutbox(
        message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at,
    ))
    execution.notification_sent = True
    return True
