from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class MessageEnvelope(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    message_type: str = Field(min_length=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    schema_version: int = Field(default=1, ge=1)
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information")
        return value.astimezone(timezone.utc)

    @classmethod
    def create(cls, *, message_type: str, producer: str, payload: dict[str, Any],
               correlation_id: str | None = None, idempotency_key: str | None = None):
        message_id = uuid4()
        return cls(message_id=message_id, message_type=message_type,
                   correlation_id=correlation_id or str(message_id), producer=producer,
                   idempotency_key=idempotency_key, payload=payload)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, value: str | bytes):
        return cls.model_validate_json(value)
