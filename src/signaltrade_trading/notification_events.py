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


def enqueue_settlement_notification(
    db,
    *,
    execution,
    chat_id: str | None,
    strategy_name: str,
    signal_source: str,
) -> bool:
    if not chat_id or execution.settlement_notification_sent:
        return False
    action = "매수" if execution.action == "buy" else "매도"
    reason = {
        "stop_loss": "손절 조건 도달",
        "take_profit": "목표 수익률 도달",
        "manual": "사용자 수동 매도",
    }.get(signal_source)
    reason_line = f"매도 사유: {reason}\n" if execution.action == "sell" and reason else ""
    if execution.status == "success":
        message = (
            f"✅ [실전 체결 완료] {action}\n\n"
            f"전략: {strategy_name}\n종목: {execution.market}\n"
            f"평균 체결가: {execution.average_price or execution.price:,.0f}원\n"
            f"체결수량: {execution.executed_volume or 0:.8f}\n"
            f"{reason_line}주문 UUID: {execution.order_uuid}"
        )
    else:
        message = (
            f"⚠️ [실전 주문 종료] {action}\n\n"
            f"전략: {strategy_name}\n종목: {execution.market}\n"
            f"상태: {execution.status}\n"
            f"사유: {execution.error_message or '체결 없이 주문이 종료되었습니다.'}\n"
            f"주문 UUID: {execution.order_uuid}"
        )
    key = f"execution-settlement:{execution.id}"
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested",
        producer="trading-worker",
        correlation_id=key,
        idempotency_key=key,
        payload={
            "chat_id": str(chat_id),
            "message": message,
            "notification_type": "order_settlement",
            "user_id": execution.user_id,
        },
    )
    db.add(MessageOutbox(
        message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at,
    ))
    execution.settlement_notification_sent = True
    return True


def enqueue_recovery_notification(
    db, *, execution, chat_id: str | None, strategy_name: str
) -> bool:
    if not chat_id:
        return False
    key = f"execution-recovery:{execution.id}"
    envelope = MessageEnvelope.create(
        message_type="NotificationRequested",
        producer="trading-worker",
        correlation_id=key,
        idempotency_key=key,
        payload={
            "chat_id": str(chat_id),
            "message": "\n".join([
                "⚠️ [실전 주문 상태 확인 필요]",
                f"전략: {strategy_name}",
                f"종목: {execution.market}",
                f"구분: {'매수' if execution.action == 'buy' else '매도'}",
                "worker 중단 중 실제 체결됐을 가능성이 있습니다.",
                "웹의 실전계좌 화면에서 잔고 차이를 확인해 주세요.",
                "확인 전에는 같은 방향의 주문을 추가 실행하지 않습니다.",
            ]),
            "notification_type": "execution_recovery_uncertain",
            "user_id": execution.user_id,
        },
    )
    db.add(MessageOutbox(
        message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at,
    ))
    return True
