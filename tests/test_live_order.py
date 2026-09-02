from signaltrade_trading.live_order import normalize_order_response


def test_cancelled_market_order_with_fill_is_success():
    result = normalize_order_response("order-1", {
        "state": "cancel", "executed_volume": "0.2", "paid_fee": "10",
        "trades": [{"volume": "0.1", "funds": "10000"},
                   {"volume": "0.1", "funds": "11000"}],
    })
    assert result.success is True
    assert result.status == "success"
    assert result.average_price == 105000


def test_waiting_order_with_fill_is_partial():
    result = normalize_order_response("order-2", {
        "state": "wait", "executed_volume": "0.01", "trades": []})
    assert result.status == "partially_filled"


def test_cancelled_order_without_fill_is_not_success():
    result = normalize_order_response("order-3", {"state": "cancel", "executed_volume": "0"})
    assert result.status == "cancelled"
    assert result.success is False
