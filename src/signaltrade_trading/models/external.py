"""Read/FK-only mappings for tables owned by Identity and Strategy."""

from sqlalchemy import Column, Integer, Table

from signaltrade_trading.database import Base

user_table = Table("user", Base.metadata, Column("id", Integer, primary_key=True))
user_strategy_table = Table(
    "user_strategy", Base.metadata, Column("id", Integer, primary_key=True)
)
strategy_signal_table = Table(
    "strategy_signal", Base.metadata, Column("id", Integer, primary_key=True)
)
