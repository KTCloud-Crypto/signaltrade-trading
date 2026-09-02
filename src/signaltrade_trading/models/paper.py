from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String

from signaltrade_trading.database import Base


class PaperAccount(Base):
    __tablename__ = "paper_account"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False, index=True)
    cash_balance = Column(Numeric(20, 2), nullable=False, default=0)
    net_deposit = Column(Numeric(20, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperLedger(Base):
    __tablename__ = "paper_ledger"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("paper_account.id"), nullable=False, index=True)
    strategy_execution_id = Column(Integer, ForeignKey("strategy_execution.id"), nullable=True, index=True)
    kind = Column(String(16), nullable=False)
    amount = Column(Numeric(20, 2), nullable=False)
    balance_after = Column(Numeric(20, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
