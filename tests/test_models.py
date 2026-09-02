from sqlalchemy import inspect

from signaltrade_trading.database import engine


def test_trading_owned_tables_are_mapped():
    tables = set(inspect(engine).get_table_names())
    assert {"strategy_execution", "trading_execution_request", "trade",
            "paper_account", "paper_ledger"} <= tables
