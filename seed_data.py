"""SeatDesk deterministic seed data. Usage: python seed_data.py -> writes seed.json"""
import json
import random
from datetime import datetime, timedelta

FMT = "%Y-%m-%d %H:%M:%S"
DESK_NOW = "2026-12-01 09:00:00"  # the desk's fixed "current time"
DEMO_PASSWORD = "SeatDesk@2026"  # every seeded user logs in with this
ROUTES = [  # (origin, destination, distance_km)
    ("Bengaluru", "Chennai", 346),
    ("Chennai", "Bengaluru", 346),
    ("Bengaluru", "Hyderabad", 570),
    ("Hyderabad", "Bengaluru", 570),
    ("Pune", "Mumbai", 150),
    ("Mumbai", "Pune", 150),
    ("Mumbai", "Goa", 590),
    ("Goa", "Mumbai", 590),
    ("Pune", "Goa", 450),
    ("Hyderabad", "Pune", 560),
]
OPERATORS = ["Coastline Express", "Highway Kings"]
BUS_TYPES = {  # bus_type: (fare in paise per km, total seats)
    "AC Sleeper": (260, 30),
    "AC Seater": (190, 40),
    "Non-AC Seater": (130, 44),
}
# (day offset from DESK_NOW's date, departure time): 1 past trip + 4 future trips per route
SLOTS = [(-1, "20:30"), (0, "18:00"), (1, "06:15"), (1, "21:45"), (2, "10:00")]
NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vivaan", "Anaya", "Arjun", "Saanvi", "Dev", "Tara", "Ishaan", "Riya", "Nikhil", "Pooja"]


def build():
    rng = random.Random(2606)
    now = datetime.strptime(DESK_NOW, FMT)
    users = [
        {"id": 1, "email": "ops.manager@seatdesk.test", "full_name": "Ops Manager", "role": "operator"},
        {"id": 2, "email": "ops.lead@seatdesk.test", "full_name": "Ops Lead", "role": "operator"},
        {"id": 3, "email": "conductor.one@seatdesk.test", "full_name": "Conductor One", "role": "conductor"},
        {"id": 4, "email": "conductor.two@seatdesk.test", "full_name": "Conductor Two", "role": "conductor"},
    ]
    for i, name in enumerate(NAMES):
        users.append({"id": 5 + i, "email": f"{name.lower()}@mail.test", "full_name": f"{name} Rao", "role": "passenger"})
    passenger_ids = [u["id"] for u in users if u["role"] == "passenger"]
    routes = [{"id": i + 1, "origin": o, "destination": d, "distance_km": km} for i, (o, d, km) in enumerate(ROUTES)]
    trips = []
    for r in routes:
        for k, (day, hhmm) in enumerate(SLOTS):
            bus_type = rng.choice(list(BUS_TYPES))
            paise_per_km, seats = BUS_TYPES[bus_type]
            fare = r["distance_km"] * paise_per_km // 100 // 10 * 10 + 10 * rng.randint(0, 5)
            date = (now + timedelta(days=day)).strftime("%Y-%m-%d")
            trips.append({"id": len(trips) + 1, "route_id": r["id"], "operator": OPERATORS[k % 2], "departure_at": f"{date} {hhmm}:00", "bus_type": bus_type, "fare_inr": fare, "total_seats": seats})
    bookings, ledger = [], []
    left = {t["id"]: t["total_seats"] for t in trips}
    for _ in range(110):
        trip = trips[rng.randint(0, len(trips) - 2)]  # the last trip never gets a booking
        seats = rng.randint(1, 4)
        if seats > left[trip["id"]]:
            continue
        left[trip["id"]] -= seats
        roll, paid = rng.random(), rng.random() < 0.5
        if trip["departure_at"] < DESK_NOW:  # already departed
            status = "completed" if roll < 0.85 else "cancelled"
        else:
            status = "held" if roll < 0.20 else ("confirmed" if roll < 0.80 else "cancelled")
        age = rng.randint(1, 60) if status == "held" else rng.randint(1, 2880)  # minutes
        bid = len(bookings) + 1
        amount = seats * trip["fare_inr"]
        bookings.append({"id": bid, "trip_id": trip["id"], "passenger_id": rng.choice(passenger_ids), "seats": seats, "amount_inr": amount, "status": status, "created_at": (now - timedelta(minutes=age)).strftime(FMT)})
        if status in ("confirmed", "completed") or (status == "cancelled" and paid):
            ledger.append({"booking_id": bid, "entry_type": "charge", "amount_inr": amount})
        if status == "cancelled" and paid:
            ledger.append({"booking_id": bid, "entry_type": "refund", "amount_inr": amount // 2})
    return {"desk_now": DESK_NOW, "demo_password": DEMO_PASSWORD, "users": users, "routes": routes, "trips": trips, "bookings": bookings, "ledger": ledger}


if __name__ == "__main__":
    data = build()
    with open("seed.json", "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    print({k: len(v) for k, v in data.items() if isinstance(v, list)})
