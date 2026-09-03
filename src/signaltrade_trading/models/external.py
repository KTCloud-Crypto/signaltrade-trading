"""Read/FK-only mappings for tables owned by Identity and Strategy."""

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Table

from signaltrade_trading.database import Base

user_table = Table("user", Base.metadata, Column("id", Integer, primary_key=True),
                   Column("bot_enabled", Boolean, nullable=False),
                   Column("live_trading_enabled", Boolean, nullable=False),
                   Column("telegram_chat_id", String(64), nullable=True))
strategy_table = Table("strategy", Base.metadata, Column("id", Integer, primary_key=True),
                       Column("name", String(100), nullable=False),
                       Column("enabled", Boolean, nullable=False))
supported_market_table = Table("supported_market", Base.metadata,
                               Column("id", Integer, primary_key=True),
                               Column("code", String(20), nullable=False))
user_strategy_table = Table(
    "user_strategy", Base.metadata, Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False), Column("strategy_id", Integer, nullable=False),
    Column("market_id", Integer, nullable=False), Column("mode", String(16), nullable=False),
    Column("invest_ratio", Float, nullable=False), Column("allocated_amount", Float),
    Column("timeframe_minutes", Integer, nullable=False),
    Column("enabled", Boolean, nullable=False), Column("paused", Boolean, nullable=False)
)
strategy_signal_table = Table(
    "strategy_signal", Base.metadata, Column("id", Integer, primary_key=True),
    Column("strategy_id", Integer, nullable=False), Column("market", String(20), nullable=False),
    Column("timeframe_minutes", Integer, nullable=False), Column("action", String(8), nullable=False),
    Column("source", String(16), nullable=False), Column("close_price", Float, nullable=False)
)
strategy_runtime_table = Table(
    "strategy_runtime", Base.metadata, Column("id", Integer, primary_key=True),
    Column("strategy_id", Integer, nullable=False), Column("market", String(20), nullable=False),
    Column("timeframe_minutes", Integer, nullable=False), Column("close_price", Float, nullable=False),
    Column("metrics", JSON, nullable=False), Column("evaluated_at", DateTime, nullable=False),
)
