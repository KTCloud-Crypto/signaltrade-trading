from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String

from signaltrade_trading.database import Base


class Trade(Base):
    __tablename__ = "trade"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    strategy_execution_id = Column(Integer, ForeignKey("strategy_execution.id"),
                                   unique=True, nullable=True, index=True)
    ticker = Column(String(32), nullable=False)
    action = Column(String(8), nullable=False)
    price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    status = Column(String(16), nullable=False)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
