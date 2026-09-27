import uuid
from datetime import datetime

from pydantic import BaseModel


class CentreResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    city: str
    created_at: datetime

    model_config = {"from_attributes": True}
