from signaltrade_trading.main import app


def test_frontend_history_routes_and_response_contracts():
    spec = app.openapi()
    for method, path in [("get", "/strategies/executions"), ("get", "/trades"),
                         ("post", "/strategies/liquidate-all"),
                         ("post", "/strategies/{strategy_id}/manual-sell")]:
        assert method in spec["paths"].get(path, {})
    assert set(spec["components"]["schemas"]["TradeOut"]["properties"]) == {
        "id", "strategy_execution_id", "strategy_name", "ticker", "action", "price",
        "volume", "status", "created_at"}
    assert set(spec["components"]["schemas"]["StrategyExecutionOut"]["properties"]) == {
        "id", "strategy_name", "strategy_code", "action", "market", "mode", "status",
        "price", "order_amount", "order_volume", "executed_volume", "average_price",
        "paid_fee", "entry_price", "transaction_amount", "realized_profit_loss",
        "error_message", "notification_sent", "exit_reason", "created_at"}
