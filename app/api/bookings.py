import uuid

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.booking import BookingCreateRequest, BookingResponse
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test booking",
)
def create_booking(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = booking_service.create_booking(db, current_user.id, payload)
    return booking


@router.get(
    "/",
    response_model=list[BookingResponse],
    summary="List your bookings",
)
def list_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return booking_service.get_user_bookings(db, current_user.id, skip, limit)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get a specific booking",
)
def get_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        uid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found")

    return booking_service.get_booking(db, uid, current_user.id)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a pending booking",
)
def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        uid = uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Booking not found")

    return booking_service.cancel_booking(db, uid, current_user.id)
