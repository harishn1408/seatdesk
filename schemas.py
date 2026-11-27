"""Pydantic v2 request and response schemas for SeatDesk."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str
    full_name: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str


class TripOut(BaseModel):
    id: int
    origin: str
    destination: str
    operator: str
    departure_at: str
    bus_type: str
    fare_inr: int
    seats_left: int


class TripPage(BaseModel):
    items: list[TripOut]
    total: int
    page: int
    limit: int


class BookingCreate(BaseModel):
    trip_id: int
    seats: int = Field(ge=1, le=6)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    passenger_id: int
    seats: int
    amount_inr: int
    status: str
    created_at: str


class BookingPage(BaseModel):
    items: list[BookingOut]
    total: int
    page: int
    limit: int


class BookingStatusUpdate(BaseModel):
    status: Literal["boarded", "completed"]


class CancelResponse(BaseModel):
    id: int
    status: Literal["cancelled"]
    refund_inr: int


class OperatorSummary(BaseModel):
    revenue_inr: int
    bookings_by_status: dict[str, int]
    busiest_route: str
    busiest_route_seats: int


class ReleaseHoldsResponse(BaseModel):
    released: int
    booking_ids: list[int]


class TimetableEntry(BaseModel):
    trip_id: int
    operator: str
    departure_at: str


class TripQuery(BaseModel):
    origin: str | None = None
    destination: str | None = None
    max_fare_inr: int | None = None
    bus_type: str | None = None


class AISearchRequest(BaseModel):
    query: str


class AISearchResponse(BaseModel):
    parsed: TripQuery
    total: int
    trips: list[TripOut]


class AdvisorySearchHit(BaseModel):
    id: int
    title: str
    score: float
