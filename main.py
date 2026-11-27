"""SeatDesk FastAPI application covering Part B booking API and Part C search/timetable."""
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from advisories import ADVISORIES
from algo import cosine_similarity, merge_sorted
from db import get_db
from llm_client import LLMParseError, extract_trip_query
from mock_llm import mock_embed
from models import Booking, LedgerEntry, Route, Trip, User
from schemas import (
    AISearchRequest,
    AISearchResponse,
    AdvisorySearchHit,
    BookingCreate,
    BookingOut,
    BookingPage,
    BookingStatusUpdate,
    CancelResponse,
    LoginRequest,
    OperatorSummary,
    RegisterRequest,
    ReleaseHoldsResponse,
    TimetableEntry,
    TokenResponse,
    TripOut,
    TripPage,
    UserOut,
)
from security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from seed_data import DESK_NOW, FMT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("seatdesk")

ACTIVE_SEAT_STATUSES = ("held", "confirmed", "boarded", "completed")
ALLOWED_STATUS_MOVES = {
    ("confirmed", "boarded"),
    ("boarded", "completed"),
}
STALE_HOLD_CUTOFF = (datetime.strptime(DESK_NOW, FMT) - timedelta(minutes=15)).strftime(FMT)
NOTIFICATION_LOG = Path("notifications.log")

app = FastAPI(title="SeatDesk API", version="1.0.0")


@app.middleware("http")
async def process_time_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"
    logger.info("%s %s -> %s (%.6fs)", request.method, request.url.path, response.status_code, elapsed)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def hours_until(departure_at: str, now: str) -> float:
    """Return hours remaining from `now` until `departure_at`."""
    return (datetime.strptime(departure_at, FMT) - datetime.strptime(now, FMT)).total_seconds() / 3600


def append_booking_notification(
    booking_id: int,
    trip_id: int,
    passenger_id: int,
    seats: int,
    amount_inr: int,
) -> None:
    """Append a single booking notification line after the response has been sent."""
    line = (
        f"booking {booking_id}: trip={trip_id} passenger={passenger_id} "
        f"seats={seats} amount_inr={amount_inr}\n"
    )
    with NOTIFICATION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _booked_seats_by_trip(db: Session, trip_ids: list[int] | None = None) -> dict[int, int]:
    stmt = (
        select(Booking.trip_id, func.coalesce(func.sum(Booking.seats), 0))
        .where(Booking.status.in_(ACTIVE_SEAT_STATUSES))
        .group_by(Booking.trip_id)
    )
    if trip_ids is not None:
        if not trip_ids:
            return {}
        stmt = stmt.where(Booking.trip_id.in_(trip_ids))
    return {trip_id: int(booked) for trip_id, booked in db.execute(stmt).all()}


def _trip_to_out(trip: Trip, booked_seats: int) -> TripOut:
    return TripOut(
        id=trip.id,
        origin=trip.route.origin,
        destination=trip.route.destination,
        operator=trip.operator,
        departure_at=trip.departure_at,
        bus_type=trip.bus_type,
        fare_inr=trip.fare_inr,
        seats_left=trip.total_seats - booked_seats,
    )


def _search_future_trips(
    db: Session,
    origin: str | None = None,
    destination: str | None = None,
    bus_type: str | None = None,
    max_fare: int | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[int, list[TripOut]]:
    stmt = (
        select(Trip)
        .join(Route)
        .options(joinedload(Trip.route))
        .where(Trip.departure_at >= DESK_NOW)
    )
    if origin:
        stmt = stmt.where(func.lower(Route.origin) == origin.strip().lower())
    if destination:
        stmt = stmt.where(func.lower(Route.destination) == destination.strip().lower())
    if bus_type:
        stmt = stmt.where(func.lower(Trip.bus_type) == bus_type.strip().lower())
    if max_fare is not None:
        stmt = stmt.where(Trip.fare_inr <= max_fare)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    trips = db.scalars(
        stmt.order_by(Trip.id.asc()).offset((page - 1) * limit).limit(limit)
    ).all()
    booked_map = _booked_seats_by_trip(db, [trip.id for trip in trips])
    items = [_trip_to_out(trip, booked_map.get(trip.id, 0)) for trip in trips]
    return total, items


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenResponse, status_code=http_status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="passenger",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
        )
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@app.get("/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/trips", response_model=TripPage)
def list_trips(
    origin: str | None = None,
    destination: str | None = None,
    bus_type: str | None = None,
    max_fare: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> TripPage:
    total, items = _search_future_trips(db, origin, destination, bus_type, max_fare, page, limit)
    return TripPage(items=items, total=total, page=page, limit=limit)


@app.get("/trips/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db)) -> TripOut:
    trip = db.scalar(select(Trip).options(joinedload(Trip.route)).where(Trip.id == trip_id))
    if trip is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Trip not found")
    booked = _booked_seats_by_trip(db, [trip.id]).get(trip.id, 0)
    return _trip_to_out(trip, booked)


@app.post("/bookings", response_model=BookingOut, status_code=http_status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles("passenger")),
    db: Session = Depends(get_db),
) -> Booking:
    trip = db.get(Trip, payload.trip_id)
    if trip is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Trip not found")
    if trip.departure_at < DESK_NOW:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Trip has already departed")

    booked = _booked_seats_by_trip(db, [trip.id]).get(trip.id, 0)
    seats_left = trip.total_seats - booked
    if payload.seats > seats_left:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Only {seats_left} seats are left on this trip",
        )

    booking = Booking(
        trip_id=trip.id,
        passenger_id=current_user.id,
        seats=payload.seats,
        amount_inr=payload.seats * trip.fare_inr,
        status="held",
        created_at=DESK_NOW,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    background_tasks.add_task(
        append_booking_notification,
        booking.id,
        booking.trip_id,
        booking.passenger_id,
        booking.seats,
        booking.amount_inr,
    )
    return booking


@app.get("/bookings", response_model=BookingPage)
def list_bookings(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_roles("passenger", "operator")),
    db: Session = Depends(get_db),
) -> BookingPage:
    stmt = select(Booking)
    if current_user.role == "passenger":
        stmt = stmt.where(Booking.passenger_id == current_user.id)
    if status:
        stmt = stmt.where(Booking.status == status)

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    items = db.scalars(
        stmt.order_by(Booking.id.asc()).offset((page - 1) * limit).limit(limit)
    ).all()
    return BookingPage(items=items, total=total, page=page, limit=limit)


@app.post("/bookings/{booking_id}/pay", response_model=BookingOut)
def pay_booking(
    booking_id: int,
    current_user: User = Depends(require_roles("passenger")),
    db: Session = Depends(get_db),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.passenger_id != current_user.id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Not your booking")
    if booking.status != "held":
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Only held bookings can be paid")

    booking.status = "confirmed"
    db.add(LedgerEntry(booking_id=booking.id, entry_type="charge", amount_inr=booking.amount_inr))
    db.commit()
    db.refresh(booking)
    return booking


@app.patch("/bookings/{booking_id}/status", response_model=BookingOut)
def update_booking_status(
    booking_id: int,
    payload: BookingStatusUpdate,
    _current_user: User = Depends(require_roles("operator", "conductor")),
    db: Session = Depends(get_db),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if (booking.status, payload.status) not in ALLOWED_STATUS_MOVES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move booking from {booking.status} to {payload.status}",
        )

    booking.status = payload.status
    db.commit()
    db.refresh(booking)
    return booking


@app.post("/bookings/{booking_id}/cancel", response_model=CancelResponse)
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(require_roles("passenger")),
    db: Session = Depends(get_db),
) -> CancelResponse:
    booking = db.scalar(
        select(Booking).options(joinedload(Booking.trip)).where(Booking.id == booking_id)
    )
    if booking is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.passenger_id != current_user.id:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Not your booking")
    if booking.status not in ("held", "confirmed"):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail="Booking cannot be cancelled")

    refund_inr = 0
    if booking.status == "confirmed":
        hours = hours_until(booking.trip.departure_at, DESK_NOW)
        pct = 90 if hours >= 24 else (50 if hours >= 12 else 0)
        refund_inr = booking.amount_inr * pct // 100
        if refund_inr > 0:
            db.add(LedgerEntry(booking_id=booking.id, entry_type="refund", amount_inr=refund_inr))

    booking.status = "cancelled"
    db.commit()
    return CancelResponse(id=booking.id, status="cancelled", refund_inr=refund_inr)


@app.get("/operator/summary", response_model=OperatorSummary)
def operator_summary(
    _current_user: User = Depends(require_roles("operator")),
    db: Session = Depends(get_db),
) -> OperatorSummary:
    charges = int(
        db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_inr), 0)).where(LedgerEntry.entry_type == "charge")
        ) or 0
    )
    refunds = int(
        db.scalar(
            select(func.coalesce(func.sum(LedgerEntry.amount_inr), 0)).where(LedgerEntry.entry_type == "refund")
        ) or 0
    )
    status_rows = db.execute(select(Booking.status, func.count(Booking.id)).group_by(Booking.status)).all()
    bookings_by_status = {row_status: int(cnt) for row_status, cnt in status_rows if cnt > 0}

    busiest = db.execute(
        select(
            Route.id,
            Route.origin,
            Route.destination,
            func.coalesce(func.sum(Booking.seats), 0).label("total_seats"),
        )
        .join(Trip, Trip.route_id == Route.id)
        .join(Booking, Booking.trip_id == Trip.id)
        .where(Booking.status != "cancelled")
        .group_by(Route.id, Route.origin, Route.destination)
        .order_by(func.sum(Booking.seats).desc(), Route.id.asc())
        .limit(1)
    ).first()

    if busiest is None:
        busiest_route = ""
        busiest_route_seats = 0
    else:
        busiest_route = f"{busiest.origin} to {busiest.destination}"
        busiest_route_seats = int(busiest.total_seats)

    return OperatorSummary(
        revenue_inr=charges - refunds,
        bookings_by_status=bookings_by_status,
        busiest_route=busiest_route,
        busiest_route_seats=busiest_route_seats,
    )


@app.post("/operator/release-stale-holds", response_model=ReleaseHoldsResponse)
def release_stale_holds(
    _current_user: User = Depends(require_roles("operator")),
    db: Session = Depends(get_db),
) -> ReleaseHoldsResponse:
    stale_bookings = db.scalars(
        select(Booking)
        .where(Booking.status == "held", Booking.created_at < STALE_HOLD_CUTOFF)
        .order_by(Booking.id.asc())
    ).all()
    released_ids = [booking.id for booking in stale_bookings]
    for booking in stale_bookings:
        booking.status = "cancelled"
    db.commit()
    return ReleaseHoldsResponse(released=len(released_ids), booking_ids=released_ids)


@app.get("/routes/{route_id}/timetable", response_model=list[TimetableEntry])
def get_route_timetable(
    route_id: int,
    operator_a: str = Query(...),
    operator_b: str = Query(...),
    db: Session = Depends(get_db),
) -> list[TimetableEntry]:
    if db.get(Route, route_id) is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Route not found")

    trips = db.scalars(
        select(Trip)
        .where(Trip.route_id == route_id, Trip.departure_at >= DESK_NOW)
        .order_by(Trip.departure_at.asc(), Trip.id.asc())
    ).all()
    op_a_lower = operator_a.strip().lower()
    op_b_lower = operator_b.strip().lower()
    list_a = [
        {"trip_id": t.id, "operator": t.operator, "departure_at": t.departure_at}
        for t in trips
        if t.operator.lower() == op_a_lower
    ]
    list_b = [
        {"trip_id": t.id, "operator": t.operator, "departure_at": t.departure_at}
        for t in trips
        if t.operator.lower() == op_b_lower
    ]
    merged = merge_sorted(list_a, list_b, key=lambda item: item["departure_at"])
    return [TimetableEntry(**item) for item in merged]


@app.post("/ai/search", response_model=AISearchResponse)
def ai_search(payload: AISearchRequest, db: Session = Depends(get_db)) -> AISearchResponse:
    try:
        parsed = extract_trip_query(payload.query)
    except LLMParseError as exc:
        raise HTTPException(status_code=http_status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    total, items = _search_future_trips(
        db,
        origin=parsed.origin,
        destination=parsed.destination,
        bus_type=parsed.bus_type,
        max_fare=parsed.max_fare_inr,
        page=1,
        limit=5,
    )
    return AISearchResponse(parsed=parsed, total=total, trips=items)


@app.get("/advisories/search", response_model=list[AdvisorySearchHit])
def search_advisories(
    q: str = Query(..., min_length=3),
    top_k: int = Query(default=3, ge=1, le=8),
) -> list[AdvisorySearchHit]:
    query_vec = mock_embed(q)
    scored = []
    for adv in ADVISORIES:
        doc_vec = mock_embed(f"{adv['title']} {adv['text']}")
        score = round(cosine_similarity(query_vec, doc_vec), 4)
        scored.append({"id": adv["id"], "title": adv["title"], "score": score})

    scored.sort(key=lambda item: (-item["score"], item["id"]))
    return [AdvisorySearchHit(**item) for item in scored[:top_k]]
