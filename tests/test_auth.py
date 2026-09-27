from tests.conftest import auth_header


class TestSignup:
    def test_successful_signup(self, client):
        resp = client.post(
            "/auth/signup",
            json={
                "email": "new@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["full_name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data  # Must never leak

    def test_duplicate_email(self, client):
        payload = {
            "email": "dup@example.com",
            "password": "password123",
            "full_name": "User",
        }
        client.post("/auth/signup", json=payload)
        resp = client.post("/auth/signup", json=payload)
        assert resp.status_code == 409

    def test_short_password_rejected(self, client):
        resp = client.post(
            "/auth/signup",
            json={"email": "x@y.com", "password": "short", "full_name": "X"},
        )
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, client):
        resp = client.post(
            "/auth/signup",
            json={"email": "not-an-email", "password": "password123", "full_name": "X"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_successful_login(self, client, registered_user):
        resp = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_wrong_password(self, client, registered_user):
        resp = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_nonexistent_email(self, client):
        resp = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 401


class TestTokenValidation:
    def test_missing_token_returns_403(self, client):
        resp = client.get("/bookings/")
        assert resp.status_code == 403  # HTTPBearer returns 403 when header is missing

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/bookings/", headers=auth_header("garbage.token.here"))
        assert resp.status_code == 401

    def test_valid_token_works(self, client, registered_user):
        resp = client.get(
            "/bookings/", headers=auth_header(registered_user["token"])
        )
        assert resp.status_code == 200
