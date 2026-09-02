from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from signaltrade_trading.database import Base


class TradingExecutionRequest(Base):
    __tablename__ = "trading_execution_request"
    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    action = Column(String(8), nullable=False)
    market = Column(String(20), nullable=False)
    reference_price = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default="manual")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StrategyExecution(Base):
    __tablename__ = "strategy_execution"
    __table_args__ = (
        UniqueConstraint("signal_id", "user_strategy_id", name="uq_signal_user_strategy_execution"),
        CheckConstraint("(signal_id IS NOT NULL) <> (execution_request_id IS NOT NULL)",
                        name="ck_strategy_execution_single_origin"),
    )
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("strategy_signal.id"), nullable=True, index=True)
    execution_request_id = Column(Integer, ForeignKey("trading_execution_request.id"),
                                  nullable=True, unique=True, index=True)
    user_strategy_id = Column(Integer, ForeignKey("user_strategy.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    mode = Column(String(16), nullable=False, default="simulated", index=True)
    action = Column(String(8), nullable=False)
    market = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="simulated")
    price = Column(Float, nullable=False)
    order_amount = Column(Float, nullable=True)
    order_volume = Column(Float, nullable=True)
    order_uuid = Column(String(64), nullable=True, index=True)
    executed_volume = Column(Float, nullable=True)
    average_price = Column(Float, nullable=True)
    paid_fee = Column(Float, nullable=True)
    error_message = Column(String(500), nullable=True)
    notification_sent = Column(Boolean, nullable=False, default=False)
    settlement_notification_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
