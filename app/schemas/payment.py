import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.payment import PaymentStatus


class PaymentCreateRequest(BaseModel):
    booking_id: uuid.UUID
    simulate: Literal["SUCCESS", "FAILED"] = "SUCCESS"


class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    provider_reference: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
