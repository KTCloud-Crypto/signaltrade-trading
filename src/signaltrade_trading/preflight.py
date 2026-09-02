import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

import pyupbit

MIN_KRW_ORDER = Decimal("5000")
DEFAULT_BUY_FEE_RATE = Decimal("0.0005")
BUY_ORDER_RESERVE_KRW = Decimal("1")


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ready: bool
    order_amount: float | None
    reason: str | None = None
    order_volume: float | None = None


def available_balances(access_key: str, secret_key: str) -> dict[str, Decimal]:
    last_error = None
    for attempt in range(3):
        try:
            response = pyupbit.Upbit(access_key, secret_key).get_balances()
            if not isinstance(response, list):
                raise ValueError("invalid Upbit balance response")
            return {row["currency"]: Decimal(str(row.get("balance") or "0"))
                    for row in response if row.get("currency")}
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.5)
    raise ValueError("Upbit 계좌 조회에 실패했습니다.") from last_error


def fee_adjusted_buying_power(available_krw: Decimal, fee_rate: Decimal) -> Decimal:
    spendable = max(Decimal("0"), available_krw - BUY_ORDER_RESERVE_KRW)
    return (spendable / (Decimal("1") + max(Decimal("0"), fee_rate))).quantize(
        Decimal("1"), rounding=ROUND_DOWN)


def validate_buy(*, access_key: str, secret_key: str, market: str,
                 invest_ratio: float, allocated_amount: float | None) -> PreflightResult:
    try:
        balances = available_balances(access_key, secret_key)
    except ValueError as error:
        return PreflightResult(False, None, str(error))
    cash = balances.get("KRW", Decimal("0"))
    budget = (Decimal(str(allocated_amount)) if allocated_amount is not None
              else cash * Decimal(str(invest_ratio)))
    try:
        chance = pyupbit.Upbit(access_key, secret_key).get_chance(market)
        fee = Decimal(str(chance["bid_fee"])) if isinstance(chance, dict) else DEFAULT_BUY_FEE_RATE
    except Exception:
        fee = DEFAULT_BUY_FEE_RATE
    amount = min(max(Decimal("0"), budget), fee_adjusted_buying_power(cash, fee))
    if amount < MIN_KRW_ORDER:
        return PreflightResult(False, float(amount), "예상 주문금액이 최소 주문금액 5,000원보다 작습니다.")
    return PreflightResult(True, float(amount))


def validate_sell(*, access_key: str, secret_key: str, market: str,
                  reference_price: float, strategy_volume: float) -> PreflightResult:
    if strategy_volume <= 0:
        return PreflightResult(False, None, "이 전략으로 매수해 남아 있는 수량이 없습니다.")
    try:
        balances = available_balances(access_key, secret_key)
    except ValueError as error:
        return PreflightResult(False, None, str(error))
    requested = Decimal(str(strategy_volume))
    available = balances.get(market.split("-", 1)[-1], Decimal("0"))
    if available < requested:
        return PreflightResult(False, None, "Upbit 가용 잔고가 전략 수량보다 부족합니다.", float(requested))
    amount = (requested * Decimal(str(reference_price))).quantize(Decimal("1"), rounding=ROUND_DOWN)
    if amount < MIN_KRW_ORDER:
        return PreflightResult(False, float(amount), "예상 주문금액이 최소 주문금액 5,000원보다 작습니다.", float(requested))
    return PreflightResult(True, float(amount), order_volume=float(requested))
