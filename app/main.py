import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import auth, bookings, centres, payments, tests
from app.core.exceptions import AppError

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)

app = FastAPI(
    title="EVE Health — Diagnostic Booking Service",
    description=(
        "Backend service for diagnostic test bookings with simulated payment "
        "processing and idempotent webhook handling."
    ),
    version="1.0.0",
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["Health"], summary="Health check")
def health_check():
    return {"status": "ok"}
