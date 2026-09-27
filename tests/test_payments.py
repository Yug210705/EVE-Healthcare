import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import auth_header


class TestProcessPayment:
    def _create_booking(self, client, registered_user, seed_centres):
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
        return resp.json()

    def test_successful_payment(self, client, registered_user, seed_centres, db):
        booking = self._create_booking(client, registered_user, seed_centres)

        resp = client.post(
            "/payments/",
            json={"booking_id": booking["id"], "simulate": "SUCCESS"},
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 201
        payment = resp.json()
        assert payment["status"] == "SUCCESS"
        assert payment["amount"] == "500.00"

        # Verify booking state in DB
        from app.models import Booking
        from sqlalchemy import select

        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking["id"]))
        ).scalar_one()
        assert db_booking.status.value == "CONFIRMED"

    def test_failed_payment(self, client, registered_user, seed_centres, db):
        booking = self._create_booking(client, registered_user, seed_centres)

        resp = client.post(
            "/payments/",
            json={"booking_id": booking["id"], "simulate": "FAILED"},
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "FAILED"

        from app.models import Booking
        from sqlalchemy import select

        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking["id"]))
        ).scalar_one()
        assert db_booking.status.value == "FAILED"

    def test_payment_for_nonexistent_booking(self, client, registered_user):
        resp = client.post(
            "/payments/",
            json={"booking_id": str(uuid.uuid4())},
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 404

    def test_payment_for_other_users_booking(self, client, registered_user, seed_centres):
        booking = self._create_booking(client, registered_user, seed_centres)

        # Register second user
        client.post(
            "/auth/signup",
            json={"email": "other@example.com", "password": "password123", "full_name": "Other"},
        )
        other_token = client.post(
            "/auth/login",
            json={"email": "other@example.com", "password": "password123"},
        ).json()["access_token"]

        resp = client.post(
            "/payments/",
            json={"booking_id": booking["id"]},
            headers=auth_header(other_token),
        )
        assert resp.status_code == 403

    def test_double_payment_rejected(self, client, registered_user, seed_centres):
        booking = self._create_booking(client, registered_user, seed_centres)
        headers = auth_header(registered_user["token"])

        client.post(
            "/payments/",
            json={"booking_id": booking["id"], "simulate": "SUCCESS"},
            headers=headers,
        )
        # Second attempt
        resp = client.post(
            "/payments/",
            json={"booking_id": booking["id"], "simulate": "SUCCESS"},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_payment_on_cancelled_booking_rejected(self, client, registered_user, seed_centres):
        booking = self._create_booking(client, registered_user, seed_centres)
        headers = auth_header(registered_user["token"])

        client.post(f"/bookings/{booking['id']}/cancel", headers=headers)

        resp = client.post(
            "/payments/",
            json={"booking_id": booking["id"]},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_unauthenticated_payment_rejected(self, client, seed_centres):
        resp = client.post(
            "/payments/",
            json={"booking_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403
