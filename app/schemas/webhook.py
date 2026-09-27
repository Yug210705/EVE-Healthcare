import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    """Simulates an incoming payment provider webhook notification."""

    event_id: str = Field(description="Unique provider event ID for idempotency")
    event_type: str = Field(description="Event type, e.g. payment.completed")
    payment_reference: str = Field(description="Provider's payment transaction ID")
    booking_id: uuid.UUID
    amount: Decimal
    status: Literal["SUCCESS", "FAILED"]


class WebhookResponse(BaseModel):
    status: str
    message: str | None = None
