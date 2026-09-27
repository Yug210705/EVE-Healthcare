"""
Webhook idempotency tests — the most important test file in this project.

These tests verify:
1. First webhook processes correctly
2. Duplicate event_id is safely ignored
3. Duplicate payment_reference (different event_id) is safely ignored
4. Repeated webhooks don't create duplicate payments or corrupt booking state
5. Terminal booking states are never overwritten
6. Invalid payloads handled gracefully

Each test asserts actual database state (row counts, statuses), not just HTTP codes.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Booking, Payment, WebhookEvent
from tests.conftest import auth_header


class TestWebhookIdempotency:
    def _setup_pending_booking(self, client, registered_user, seed_centres):
        """Helper: create a PENDING booking and return its ID + amount."""
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking = resp.json()
        return booking["id"], Decimal(booking["amount"])

    def test_first_webhook_processes_correctly(self, client, registered_user, seed_centres, db):
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)

        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_001",
                "event_type": "payment.completed",
                "payment_reference": "pay_001",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "SUCCESS",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

        # Verify DB state
        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        ).scalar_one()
        assert db_booking.status.value == "CONFIRMED"

        payment_count = db.execute(
            select(func.count()).select_from(Payment).where(Payment.booking_id == uuid.UUID(booking_id))
        ).scalar()
        assert payment_count == 1

        event_count = db.execute(
            select(func.count()).select_from(WebhookEvent)
        ).scalar()
        assert event_count == 1

    def test_duplicate_event_id_ignored(self, client, registered_user, seed_centres, db):
        """Same event_id sent twice — second is a no-op."""
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)
        webhook_body = {
            "event_id": "evt_dup",
            "event_type": "payment.completed",
            "payment_reference": "pay_dup",
            "booking_id": booking_id,
            "amount": str(amount),
            "status": "SUCCESS",
        }

        resp1 = client.post("/payments/webhook/", json=webhook_body)
        resp2 = client.post("/payments/webhook/", json=webhook_body)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"

        # Exactly 1 payment, exactly 1 webhook event
        payment_count = db.execute(
            select(func.count()).select_from(Payment).where(Payment.booking_id == uuid.UUID(booking_id))
        ).scalar()
        assert payment_count == 1

        event_count = db.execute(
            select(func.count()).select_from(WebhookEvent)
        ).scalar()
        assert event_count == 1

    def test_same_event_sent_many_times(self, client, registered_user, seed_centres, db):
        """Same webhook delivered 10 times — must result in exactly 1 payment."""
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)
        webhook_body = {
            "event_id": "evt_repeat",
            "event_type": "payment.completed",
            "payment_reference": "pay_repeat",
            "booking_id": booking_id,
            "amount": str(amount),
            "status": "SUCCESS",
        }

        responses = [
            client.post("/payments/webhook/", json=webhook_body) for _ in range(10)
        ]
        assert all(r.status_code == 200 for r in responses)

        payment_count = db.execute(
            select(func.count()).select_from(Payment).where(Payment.booking_id == uuid.UUID(booking_id))
        ).scalar()
        assert payment_count == 1

        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        ).scalar_one()
        assert db_booking.status.value == "CONFIRMED"

    def test_different_event_same_payment_reference(self, client, registered_user, seed_centres, db):
        """
        Two different event_ids but same payment_reference (provider retry with new event ID).
        Must NOT create a duplicate payment.
        """
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)

        # First event processes normally
        client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_first",
                "event_type": "payment.completed",
                "payment_reference": "pay_shared",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "SUCCESS",
            },
        )

        # Second event with different ID but same payment_reference
        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_second",
                "event_type": "payment.completed",
                "payment_reference": "pay_shared",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "SUCCESS",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"

        # Still exactly 1 payment
        payment_count = db.execute(
            select(func.count()).select_from(Payment).where(Payment.booking_id == uuid.UUID(booking_id))
        ).scalar()
        assert payment_count == 1

    def test_terminal_state_not_overwritten(self, client, registered_user, seed_centres, db):
        """Once booking is CONFIRMED, a late FAILED webhook must not change it."""
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)

        # First: SUCCESS
        client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_success",
                "event_type": "payment.completed",
                "payment_reference": "pay_success",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "SUCCESS",
            },
        )

        # Late: FAILED (different payment, but booking already terminal)
        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_late_fail",
                "event_type": "payment.failed",
                "payment_reference": "pay_late",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "FAILED",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

        # Booking remains CONFIRMED
        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        ).scalar_one()
        assert db_booking.status.value == "CONFIRMED"

    def test_failed_webhook_transitions_booking(self, client, registered_user, seed_centres, db):
        booking_id, amount = self._setup_pending_booking(client, registered_user, seed_centres)

        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_fail",
                "event_type": "payment.failed",
                "payment_reference": "pay_fail",
                "booking_id": booking_id,
                "amount": str(amount),
                "status": "FAILED",
            },
        )
        assert resp.status_code == 200

        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        ).scalar_one()
        assert db_booking.status.value == "FAILED"

    def test_webhook_nonexistent_booking(self, client):
        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_orphan",
                "event_type": "payment.completed",
                "payment_reference": "pay_orphan",
                "booking_id": str(uuid.uuid4()),
                "amount": "500.00",
                "status": "SUCCESS",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_webhook_amount_mismatch(self, client, registered_user, seed_centres):
        booking_id, _ = self._setup_pending_booking(client, registered_user, seed_centres)

        resp = client.post(
            "/payments/webhook/",
            json={
                "event_id": "evt_mismatch",
                "event_type": "payment.completed",
                "payment_reference": "pay_mismatch",
                "booking_id": booking_id,
                "amount": "99999.00",  # Wrong amount
                "status": "SUCCESS",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
        assert "mismatch" in resp.json()["message"].lower()

    def test_webhook_invalid_payload(self, client):
        resp = client.post("/payments/webhook/", json={"garbage": True})
        assert resp.status_code == 422
