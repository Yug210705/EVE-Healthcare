import uuid


class TestListCentres:
    def test_returns_seeded_centres(self, client, seed_centres):
        resp = client.get("/centres/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["name"] == "TestCentre"

    def test_pagination(self, client, seed_centres):
        resp = client.get("/centres/?skip=0&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestGetCentre:
    def test_valid_centre(self, client, seed_centres):
        centre_id = str(seed_centres["centre_id"])
        resp = client.get(f"/centres/{centre_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == centre_id

    def test_nonexistent_centre(self, client):
        resp = client.get(f"/centres/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_invalid_uuid(self, client):
        resp = client.get("/centres/not-a-uuid")
        assert resp.status_code == 404


class TestCentreTests:
    def test_list_tests_for_centre(self, client, seed_centres):
        centre_id = str(seed_centres["centre_id"])
        resp = client.get(f"/centres/{centre_id}/tests")
        assert resp.status_code == 200
        tests = resp.json()
        assert len(tests) == 2
        names = {t["name"] for t in tests}
        assert "Blood Test" in names
        assert "X-Ray" in names

    def test_nonexistent_centre_returns_404(self, client):
        resp = client.get(f"/centres/{uuid.uuid4()}/tests")
        assert resp.status_code == 404


class TestGetTest:
    def test_valid_test(self, client, seed_centres):
        test_id = str(seed_centres["test_a_id"])
        resp = client.get(f"/tests/{test_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Blood Test"

    def test_nonexistent_test(self, client):
        resp = client.get(f"/tests/{uuid.uuid4()}")
        assert resp.status_code == 404
