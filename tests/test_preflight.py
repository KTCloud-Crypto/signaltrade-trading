from decimal import Decimal

from signaltrade_trading import preflight


class FakeUpbit:
    def get_balances(self):
        return [{"currency": "KRW", "balance": "10000"},
                {"currency": "BTC", "balance": "0.01"}]

    def get_chance(self, _market):
        return {"bid_fee": "0.0005"}


def test_buy_preflight_reserves_fee(monkeypatch):
    monkeypatch.setattr(preflight.pyupbit, "Upbit", lambda *_: FakeUpbit())
    result = preflight.validate_buy(access_key="a", secret_key="s", market="KRW-BTC",
                                    invest_ratio=1, allocated_amount=None)
    assert result.ready is True
    assert result.order_amount == 9994


def test_sell_preflight_rejects_more_than_exchange_balance(monkeypatch):
    monkeypatch.setattr(preflight.pyupbit, "Upbit", lambda *_: FakeUpbit())
    result = preflight.validate_sell(access_key="a", secret_key="s", market="KRW-BTC",
                                     reference_price=100_000_000, strategy_volume=0.02)
    assert result.ready is False
    assert result.order_volume == 0.02


def test_fee_adjusted_buying_power_never_exceeds_cash():
    amount = preflight.fee_adjusted_buying_power(Decimal("10000"), Decimal("0.0005"))
    assert amount * Decimal("1.0005") + Decimal("1") <= Decimal("10000")
