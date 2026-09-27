import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.payment import PaymentCreateRequest, PaymentResponse
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger(__name__)


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process a simulated payment for a booking",
)
def create_payment(
    payload: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return payment_service.process_payment(db, current_user.id, payload)


@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    summary="Payment provider webhook endpoint",
)
def payment_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    result = payment_service.process_webhook(db, payload)
    return WebhookResponse(**result)
