from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text, func
from signaltrade_trading.database import Base


class MessageOutbox(Base):
    __tablename__ = "message_outbox"
    __table_args__ = (Index("ix_message_outbox_pending", "status", "next_attempt_at", "created_at"),)
    id = Column(Integer, primary_key=True)
    message_id = Column(String(36), nullable=False, unique=True)
    message_type = Column(String(128), nullable=False, index=True)
    correlation_id = Column(String(128), nullable=False, index=True)
    producer = Column(String(64), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String(255), unique=True)
    payload = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_error = Column(Text); transport_message_id = Column(String(128))
    published_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
