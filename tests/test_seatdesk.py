"""Standard-library tests for SeatDesk API checkpoints."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from load_seed import load
import main

from algo import cosine_similarity

load()
client = TestClient(main.app)


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

    def test_health_db(self):
        response = client.get("/health/db")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

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
        # create
        response = client.post("/bookings", json={"trip_id": 22, "seats": 1}, headers={"Authorization": "Bearer " + self._token})
        self.assertEqual(response.status_code, 201)
        booking_id = response.json()["id"]
        # pay
        response = client.post(f"/bookings/{booking_id}/pay", headers={"Authorization": "Bearer " + self._token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "confirmed")
        # status move
        conductor_token = self._conductor_token
        response = client.patch(f"/bookings/{booking_id}/status", json={"status": "boarded"}, headers={"Authorization": "Bearer " + conductor_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "boarded")


if __name__ == "__main__":
    unittest.main()