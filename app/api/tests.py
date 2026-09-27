import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.diagnostic_test import DiagnosticTest
from app.schemas.test import TestResponse

router = APIRouter(prefix="/tests", tags=["Diagnostic Tests"])


@router.get(
    "/{test_id}",
    response_model=TestResponse,
    summary="Get a diagnostic test by ID",
)
def get_test(test_id: str, db: Session = Depends(get_db)):
    try:
        uid = _uuid.UUID(test_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic test not found",
        )

    test = db.execute(
        select(DiagnosticTest).where(DiagnosticTest.id == uid)
    ).scalar_one_or_none()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostic test not found",
        )
    return test
