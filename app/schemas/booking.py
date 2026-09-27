import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.models.booking import BookingStatus


class BookingCreateRequest(BaseModel):
    test_id: uuid.UUID
    centre_id: uuid.UUID
    appointment_at: AwareDatetime


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    test_id: uuid.UUID
    centre_id: uuid.UUID
    appointment_at: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
