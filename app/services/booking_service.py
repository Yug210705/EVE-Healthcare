import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, InvalidStateError, NotFoundError
from app.models import (
    Booking,
    BookingStatus,
    BOOKING_TERMINAL_STATES,
    DiagnosticCentre,
    DiagnosticTest,
)
from app.schemas.booking import BookingCreateRequest

logger = logging.getLogger(__name__)


def create_booking(
    db: Session, user_id: uuid.UUID, payload: BookingCreateRequest
) -> Booking:
    # Validate centre exists
    centre = db.execute(
        select(DiagnosticCentre).where(DiagnosticCentre.id == payload.centre_id)
    ).scalar_one_or_none()
    if not centre:
        raise NotFoundError("Diagnostic centre")

    # Validate test exists
    test = db.execute(
        select(DiagnosticTest).where(DiagnosticTest.id == payload.test_id)
    ).scalar_one_or_none()
    if not test:
        raise NotFoundError("Diagnostic test")

    # Validate the test belongs to the specified centre
    if test.centre_id != centre.id:
        raise ConflictError(
            f"Test '{test.name}' is not offered by centre '{centre.name}'"
        )

    # Validate appointment is in the future
    if payload.appointment_at <= datetime.now(timezone.utc):
        raise ConflictError("Appointment must be in the future")

    booking = Booking(
        user_id=user_id,
        test_id=test.id,
        centre_id=centre.id,
        appointment_at=payload.appointment_at,
        amount=test.price,  # Derived from test, never client-provided
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    logger.info("Booking created: %s for user %s", booking.id, user_id)
    return booking


def get_user_bookings(
    db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> list[Booking]:
    result = db.execute(
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


def get_booking(db: Session, booking_id: uuid.UUID, user_id: uuid.UUID) -> Booking:
    booking = db.execute(
        select(Booking).where(Booking.id == booking_id)
    ).scalar_one_or_none()

    if not booking:
        raise NotFoundError("Booking")

    if booking.user_id != user_id:
        raise ForbiddenError("You do not have access to this booking")

    return booking


def cancel_booking(db: Session, booking_id: uuid.UUID, user_id: uuid.UUID) -> Booking:
    booking = db.execute(
        select(Booking).where(Booking.id == booking_id).with_for_update()
    ).scalar_one_or_none()

    if not booking:
        raise NotFoundError("Booking")

    if booking.user_id != user_id:
        raise ForbiddenError("You do not have access to this booking")

    if booking.status in BOOKING_TERMINAL_STATES:
        raise InvalidStateError(
            f"Cannot cancel booking in {booking.status.value} state"
        )

    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)

    logger.info("Booking cancelled: %s", booking.id)
    return booking
