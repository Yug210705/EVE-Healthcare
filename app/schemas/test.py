import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TestResponse(BaseModel):
    id: uuid.UUID
    centre_id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
