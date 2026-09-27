import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import auth_header


class TestCreateBooking:
    def test_successful_booking(self, client, registered_user, seed_centres):
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
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["amount"] == "500.00"  # Derived from test price
        assert data["user_id"] == registered_user["user"]["id"]

    def test_unauthenticated_rejected(self, client, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
        )
        assert resp.status_code == 403

    def test_nonexistent_centre(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(uuid.uuid4()),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 404

    def test_nonexistent_test(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(uuid.uuid4()),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 404

    def test_test_not_offered_by_centre(self, client, registered_user, seed_centres, db):
        """Create a second centre and try to book its test under the first centre."""
        from decimal import Decimal
        from app.models.diagnostic_centre import DiagnosticCentre
        from app.models.diagnostic_test import DiagnosticTest

        other_centre = DiagnosticCentre(name="Other", address="456 Other St", city="Other")
        db.add(other_centre)
        db.flush()
        other_test = DiagnosticTest(
            centre_id=other_centre.id, name="MRI", price=Decimal("3000.00")
        )
        db.add(other_test)
        db.commit()

        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(other_test.id),
                "centre_id": str(seed_centres["centre_id"]),  # Wrong centre
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 409
        assert "not offered" in resp.json()["detail"].lower()

    def test_past_appointment_rejected(self, client, registered_user, seed_centres):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": past,
            },
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 409

    def test_naive_datetime_rejected(self, client, registered_user, seed_centres):
        # Format without timezone offset (e.g. 2026-09-27T10:00:00)
        naive_future = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
        resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": naive_future,
            },
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 422


class TestGetBooking:
    def test_owner_can_access(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking_id = create_resp.json()["id"]

        resp = client.get(
            f"/bookings/{booking_id}",
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == booking_id

    def test_other_user_cannot_access(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking_id = create_resp.json()["id"]

        # Register second user
        client.post(
            "/auth/signup",
            json={
                "email": "other@example.com",
                "password": "password123",
                "full_name": "Other User",
            },
        )
        other_token = client.post(
            "/auth/login",
            json={"email": "other@example.com", "password": "password123"},
        ).json()["access_token"]

        resp = client.get(
            f"/bookings/{booking_id}",
            headers=auth_header(other_token),
        )
        assert resp.status_code == 403

    def test_nonexistent_booking(self, client, registered_user):
        resp = client.get(
            f"/bookings/{uuid.uuid4()}",
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 404


class TestCancelBooking:
    def test_cancel_pending_booking(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking_id = create_resp.json()["id"]

        resp = client.post(
            f"/bookings/{booking_id}/cancel",
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"

    def test_cancel_confirmed_booking_rejected(self, client, registered_user, seed_centres):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking_id = create_resp.json()["id"]

        # Pay to move to CONFIRMED
        client.post(
            "/payments/",
            json={"booking_id": booking_id, "simulate": "SUCCESS"},
            headers=auth_header(registered_user["token"]),
        )

        resp = client.post(
            f"/bookings/{booking_id}/cancel",
            headers=auth_header(registered_user["token"]),
        )
        assert resp.status_code == 409

    def test_other_user_cannot_cancel(self, client, registered_user, seed_centres, db):
        from app.models import Booking
        from sqlalchemy import select

        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = client.post(
            "/bookings/",
            json={
                "test_id": str(seed_centres["test_a_id"]),
                "centre_id": str(seed_centres["centre_id"]),
                "appointment_at": future,
            },
            headers=auth_header(registered_user["token"]),
        )
        booking_id = create_resp.json()["id"]

        # Register second user
        client.post(
            "/auth/signup",
            json={
                "email": "hacker@example.com",
                "password": "password123",
                "full_name": "Hacker User",
            },
        )
        hacker_token = client.post(
            "/auth/login",
            json={"email": "hacker@example.com", "password": "password123"},
        ).json()["access_token"]

        resp = client.post(
            f"/bookings/{booking_id}/cancel",
            headers=auth_header(hacker_token),
        )
        assert resp.status_code == 403

        # Verify booking remains unchanged in DB
        db_booking = db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        ).scalar_one()
        assert db_booking.status.value == "PENDING"
