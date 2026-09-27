import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidStateError,
    NotFoundError,
)
from app.models import (
    Booking,
    BookingStatus,
    BOOKING_TERMINAL_STATES,
    Payment,
    PaymentStatus,
    WebhookEvent,
)
from app.schemas.payment import PaymentCreateRequest
from app.schemas.webhook import WebhookPayload

logger = logging.getLogger(__name__)


def process_payment(
    db: Session, user_id: uuid.UUID, payload: PaymentCreateRequest
) -> Payment:
    """Direct mock payment — simulates what a payment provider would do."""

    # Lock the booking row to prevent concurrent payment/cancel races
    booking = db.execute(
        select(Booking).where(Booking.id == payload.booking_id).with_for_update()
    ).scalar_one_or_none()

    if not booking:
        raise NotFoundError("Booking")

    if booking.user_id != user_id:
        raise ForbiddenError("You do not have access to this booking")

    if booking.status in BOOKING_TERMINAL_STATES:
        raise InvalidStateError(
            f"Cannot process payment for booking in {booking.status.value} state"
        )

    # Prevent double-payment: if a successful payment already exists, reject
    existing_success = db.execute(
        select(Payment).where(
            Payment.booking_id == booking.id,
            Payment.status == PaymentStatus.SUCCESS,
        )
    ).scalar_one_or_none()
    if existing_success:
        raise ConflictError("A successful payment already exists for this booking")

    # Simulate payment outcome
    simulated_status = (
        PaymentStatus.SUCCESS if payload.simulate == "SUCCESS" else PaymentStatus.FAILED
    )
    provider_ref = f"sim_{uuid.uuid4().hex[:16]}"

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=simulated_status,
        provider_reference=provider_ref,
    )
    db.add(payment)

    # Transition booking state
    if simulated_status == PaymentStatus.SUCCESS:
        booking.status = BookingStatus.CONFIRMED
    else:
        booking.status = BookingStatus.FAILED

    db.commit()
    db.refresh(payment)

    logger.info(
        "Payment processed: payment=%s booking=%s status=%s",
        payment.id,
        booking.id,
        payment.status.value,
    )
    return payment


def process_webhook(db: Session, payload: WebhookPayload) -> dict:
    """
    Process a payment provider webhook with two layers of idempotency:

    Layer 1 — Event-level: UNIQUE(provider_event_id) prevents the same webhook
    delivery from being processed twice, even under concurrent requests.
    Uses a SAVEPOINT so an IntegrityError doesn't corrupt the outer transaction.

    Layer 2 — Payment-level: UNIQUE(provider_reference) prevents different webhook
    events that reference the same provider payment from creating duplicate
    Payment rows (e.g. evt_001 and evt_002 both for pay_xyz).

    The booking row is locked with SELECT FOR UPDATE before any state transition
    to prevent conflicting concurrent updates (e.g. simultaneous SUCCESS + FAILED).
    """

    # --- Layer 1: Event deduplication via savepoint ---
    try:
        nested = db.begin_nested()  # SAVEPOINT
        event = WebhookEvent(
            provider_event_id=payload.event_id,
            event_type=payload.event_type,
            payload=payload.model_dump(mode="json"),
        )
        db.add(event)
        db.flush()
    except IntegrityError:
        nested.rollback()
        logger.info("Duplicate webhook event skipped: %s", payload.event_id)
        return {"status": "duplicate", "message": "Event already processed"}

    # --- Layer 2: Payment-reference deduplication ---
    existing_payment = db.execute(
        select(Payment).where(Payment.provider_reference == payload.payment_reference)
    ).scalar_one_or_none()

    if existing_payment:
        db.commit()  # Commit the webhook_event record (for audit trail)
        logger.info(
            "Duplicate payment reference skipped: %s (event: %s)",
            payload.payment_reference,
            payload.event_id,
        )
        return {"status": "duplicate", "message": "Payment already processed"}

    # --- Lock booking and validate state ---
    booking = db.execute(
        select(Booking).where(Booking.id == payload.booking_id).with_for_update()
    ).scalar_one_or_none()

    if not booking:
        db.commit()
        logger.warning(
            "Webhook references nonexistent booking: %s (event: %s)",
            payload.booking_id,
            payload.event_id,
        )
        return {"status": "error", "message": "Booking not found"}

    if booking.status in BOOKING_TERMINAL_STATES:
        db.commit()
        logger.info(
            "Booking %s already in terminal state %s, skipping (event: %s)",
            booking.id,
            booking.status.value,
            payload.event_id,
        )
        return {
            "status": "skipped",
            "message": f"Booking already in {booking.status.value} state",
        }

    # --- Validate amount matches ---
    if payload.amount != booking.amount:
        db.commit()
        logger.warning(
            "Amount mismatch: webhook=%s booking=%s (event: %s)",
            payload.amount,
            booking.amount,
            payload.event_id,
        )
        return {"status": "error", "message": "Amount mismatch"}

    # --- Create payment and transition booking ---
    payment_status = (
        PaymentStatus.SUCCESS if payload.status == "SUCCESS" else PaymentStatus.FAILED
    )

    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=payment_status,
        provider_reference=payload.payment_reference,
    )
    db.add(payment)

    if payment_status == PaymentStatus.SUCCESS:
        booking.status = BookingStatus.CONFIRMED
    else:
        booking.status = BookingStatus.FAILED

    db.commit()

    logger.info(
        "Webhook processed: event=%s payment=%s booking=%s -> %s",
        payload.event_id,
        payment.id,
        booking.id,
        booking.status.value,
    )
    return {"status": "processed", "message": f"Booking updated to {booking.status.value}"}
