from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.diagnostic_centre import DiagnosticCentre
from app.models.diagnostic_test import DiagnosticTest
from app.schemas.centre import CentreResponse
from app.schemas.test import TestResponse

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get(
    "/",
    response_model=list[CentreResponse],
    summary="List all diagnostic centres",
)
def list_centres(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    result = db.execute(
        select(DiagnosticCentre)
        .order_by(DiagnosticCentre.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get(
    "/{centre_id}",
    response_model=CentreResponse,
    summary="Get a diagnostic centre by ID",
)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = _get_centre_or_404(centre_id, db)
    return centre


@router.get(
    "/{centre_id}/tests",
    response_model=list[TestResponse],
    summary="List tests offered by a diagnostic centre",
)
def list_centre_tests(
    centre_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    _get_centre_or_404(centre_id, db)
    result = db.execute(
        select(DiagnosticTest)
        .where(DiagnosticTest.centre_id == centre_id)
        .order_by(DiagnosticTest.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


def _get_centre_or_404(centre_id: str, db: Session) -> DiagnosticCentre:
    import uuid as _uuid

    try:
        uid = _uuid.UUID(centre_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic centre not found")

    centre = db.execute(
        select(DiagnosticCentre).where(DiagnosticCentre.id == uid)
    ).scalar_one_or_none()

    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic centre not found",
        )
    return centre
