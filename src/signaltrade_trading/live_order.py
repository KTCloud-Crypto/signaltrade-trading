from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from collections.abc import Callable

import pyupbit

ORDER_RETRY_COUNT = 1
DUPLICATE_CHECK_WINDOW_SECONDS = 10


@dataclass(frozen=True, slots=True)
class LiveOrderResult:
    success: bool
    status: str
    order_uuid: str | None = None
    executed_volume: float | None = None
    average_price: float | None = None
    paid_fee: float | None = None
    error_message: str | None = None
    raw_response: dict | None = None


def normalize_order_response(order_uuid: str, order: dict) -> LiveOrderResult:
    state = str(order.get("state") or "wait")
    executed = float(order.get("executed_volume") or 0) or None
    trades = order.get("trades") or []
    average = None
    if trades:
        volume = sum((Decimal(str(x.get("volume") or 0)) for x in trades), Decimal("0"))
        funds = sum((Decimal(str(x.get("funds") or 0)) for x in trades), Decimal("0"))
        average = float(funds / volume) if volume > 0 else None
    has_fill = bool(executed) or bool(trades)
    if state == "done":
        status = "success" if has_fill else "failed"
    elif state == "cancel":
        status = "success" if has_fill else "cancelled"
    else:
        status = "partially_filled" if has_fill else "submitted"
    fee = order.get("paid_fee")
    return LiveOrderResult(status == "success", status, order_uuid, executed, average,
                           float(fee) if fee is not None else None,
                           "체결 없이 주문이 취소되었습니다." if status == "cancelled" else None,
                           order)


def _recent(upbit, market: str, side: str):
    try:
        rows = upbit.get_order(market, state="done")
    except Exception:
        return None
    now = datetime.now(timezone.utc)
    for row in rows if isinstance(rows, list) else []:
        try:
            created = datetime.fromisoformat(row["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, TypeError):
            continue
        if row.get("side") == side and (now - created).total_seconds() <= DUPLICATE_CHECK_WINDOW_SECONDS:
            return row
    return None


def _submit(upbit, market: str, side: str, submit: Callable[[], object]) -> LiveOrderResult:
    last = None
    for attempt in range(ORDER_RETRY_COUNT + 1):
        try:
            response = submit()
        except Exception:
            response = None
        if isinstance(response, dict) and response.get("uuid"):
            return _resolve(upbit, response)
        if isinstance(response, dict):
            last = response
        existing = _recent(upbit, market, side)
        if existing and existing.get("uuid"):
            return normalize_order_response(str(existing["uuid"]), existing)
        if attempt < ORDER_RETRY_COUNT:
            time.sleep(1)
    return LiveOrderResult(False, "failed", error_message="Upbit 주문 요청에 실패했습니다.", raw_response=last)


def _resolve(upbit, response: dict) -> LiveOrderResult:
    order_uuid = str(response["uuid"]); order = response
    for _ in range(5):
        try:
            checked = upbit.get_order(order_uuid)
        except Exception:
            break
        if isinstance(checked, dict):
            order = checked
            if checked.get("state") in {"done", "cancel"}:
                break
        time.sleep(1)
    return normalize_order_response(order_uuid, order)


def execute_market_buy(*, access_key: str, secret_key: str, market: str, amount: float):
    upbit = pyupbit.Upbit(access_key, secret_key)
    return _submit(upbit, market, "bid", lambda: upbit.buy_market_order(market, amount))


def execute_market_sell(*, access_key: str, secret_key: str, market: str, volume: float):
    upbit = pyupbit.Upbit(access_key, secret_key)
    return _submit(upbit, market, "ask", lambda: upbit.sell_market_order(market, volume))


def fetch_order_result(*, access_key: str, secret_key: str, order_uuid: str):
    try:
        response = pyupbit.Upbit(access_key, secret_key).get_order(order_uuid)
    except Exception:
        return None
    return normalize_order_response(order_uuid, response) if isinstance(response, dict) else None
