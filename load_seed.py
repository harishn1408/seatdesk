"""Repeatable seed loader for SeatDesk."""
import bcrypt
from sqlalchemy import text

import seed_data
from db import Base, SessionLocal, engine
from models import Booking, LedgerEntry, Route, Trip, User


def _hash_demo_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load() -> dict[str, int]:
    """Drop and recreate all tables, then load deterministic seed data."""
    data = seed_data.build()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        batches = [
            (
                User,
                [
                    {
                        "id": row["id"],
                        "email": row["email"],
                        "password_hash": _hash_demo_password(data["demo_password"]),
                        "full_name": row["full_name"],
                        "role": row["role"],
                    }
                    for row in data["users"]
                ],
            ),
            (Route, data["routes"]),
            (Trip, data["trips"]),
            (Booking, data["bookings"]),
            (LedgerEntry, data["ledger"]),
        ]
        for model, rows in batches:
            session.add_all([model(**row) for row in rows])
            session.flush()
        session.commit()

        if engine.dialect.name == "postgresql":
            for table in ("users", "routes", "trips", "bookings", "ledger"):
                session.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
                    )
                )
            session.commit()

    counts = {
        "users": len(data["users"]),
        "routes": len(data["routes"]),
        "trips": len(data["trips"]),
        "bookings": len(data["bookings"]),
        "ledger": len(data["ledger"]),
    }
    print(
        f"loaded: users={counts['users']} routes={counts['routes']} "
        f"trips={counts['trips']} bookings={counts['bookings']} ledger={counts['ledger']}"
    )
    return counts


if __name__ == "__main__":
    load()
