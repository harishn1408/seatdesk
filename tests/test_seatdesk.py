"""Standard-library tests for SeatDesk API checkpoints using an isolated temp DB."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

_TMP_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR.name) / 'test_seatdesk.db'}"
os.environ.setdefault("JWT_SECRET", "seatdesk-dev-secret-key-at-least-32-chars")

from fastapi.testclient import TestClient

from algo import cosine_similarity
import db as db_module
from load_seed import load
import main

main.NOTIFICATION_LOG = Path(_TMP_DIR.name) / "notifications.log"
load()
client = TestClient(main.app)


def tearDownModule():
    db_module.engine.dispose()
    _TMP_DIR.cleanup()


class TestSeatDesk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        r = client.post("/auth/login", json={"email": "aarav@mail.test", "password": "SeatDesk@2026"})
        cls._token = r.json()["access_token"]
        r = client.post("/auth/login", json={"email": "conductor.one@seatdesk.test", "password": "SeatDesk@2026"})
        cls._conductor_token = r.json()["access_token"]

    def test_health(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_removed_extra_health_route(self):
        response = client.get("/health/db")
        self.assertEqual(response.status_code, 404)

    def test_trips_total(self):
        response = client.get("/trips")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 40)

    def test_login_wrong_password(self):
        response = client.post(
            "/auth/login",
            json={"email": "aarav@mail.test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Wrong email or password")

    def test_advisory_search(self):
        response = client.get("/advisories/search?q=child+ticket")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], 7)

    def test_login_long_password(self):
        response = client.post(
            "/auth/login",
            json={"email": "aarav@mail.test", "password": "a" * 73},
        )
        self.assertEqual(response.status_code, 401)

    def test_cosine_similarity_length_mismatch(self):
        with self.assertRaises(ValueError):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_trips_filter(self):
        response = client.get("/trips?origin=Pune&destination=Goa")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 4)
        self.assertEqual([x["id"] for x in response.json()["items"]], [42, 43, 44, 45])

    def test_bookings_unknown_status_returns_empty(self):
        response = client.get("/bookings?status=unknown", headers={"Authorization": "Bearer " + self._token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 0)
        self.assertEqual(response.json()["items"], [])

    def test_cors_strict_origin(self):
        ok = client.options(
            "/bookings",
            headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST"},
        )
        bad = client.options(
            "/bookings",
            headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "http://localhost:5500")
        self.assertEqual(bad.status_code, 400)
        self.assertIsNone(bad.headers.get("access-control-allow-origin"))

    def test_timetable(self):
        response = client.get("/routes/1/timetable?operator_a=Coastline%20Express&operator_b=Highway%20Kings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x["trip_id"] for x in response.json()], [2, 3, 4, 5])

    def test_ai_search(self):
        response = client.post("/ai/search", json={"query": "Pune to Goa under 800"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)
        self.assertEqual([x["id"] for x in response.json()["trips"]], [42, 43])

    def test_booking_lifecycle(self):
        response = client.post("/bookings", json={"trip_id": 22, "seats": 1}, headers={"Authorization": "Bearer " + self._token})
        self.assertEqual(response.status_code, 201)
        booking_id = response.json()["id"]
        response = client.post(f"/bookings/{booking_id}/pay", headers={"Authorization": "Bearer " + self._token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "confirmed")
        response = client.patch(f"/bookings/{booking_id}/status", json={"status": "boarded"}, headers={"Authorization": "Bearer " + self._conductor_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "boarded")


if __name__ == "__main__":
    unittest.main()
