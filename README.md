# SeatDesk

SeatDesk is a secured seat-inventory, booking, ledger, and assistant desk for intercity bus travel built with FastAPI, SQLAlchemy 2.x, SQLite, and vanilla HTML/CSS/JavaScript.

## Run

Run these commands from a clean clone of the repository:

```bash
# 1. Create and activate a virtual environment (Python 3.11+)
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

# 2. Install pinned dependencies
pip install -r requirements.txt

# 3. Create .env from the committed template
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env

# 4. Seed the database (repeatable)
python load_seed.py

# 5. Start the REST API on port 8000
uvicorn main:app --port 8000

# 6. In a second terminal, serve the browser client on port 5500
cd web
python -m http.server 5500
```

Open `http://localhost:5500` in your browser (API docs are available at `http://127.0.0.1:8000/docs`).

## Configuration

`.env` keys (defined in `.env.example`):

- `DATABASE_URL`: SQLAlchemy connection string. Defaults to `sqlite:///./seatdesk.db` when unset.
- `JWT_SECRET`: HMAC-SHA256 signing secret (at least 32 characters to avoid `InsecureKeyLengthWarning`).
- `JWT_EXPIRE_MINUTES`: Token lifetime in minutes (default `60` in `.env.example`), evaluated against real UTC wall-clock time.
- `LLM_MODE`: Assistant backend mode. Defaults to `mock` (offline deterministic parser in `mock_llm.py` and bag-of-words embeddings via `mock_embed`).
- `GEMINI_API_KEY`: Blank by default; only needed if switching to the optional `LLM_MODE=gemini` mode.

### Switching to optional hosted PostgreSQL or Gemini

- **PostgreSQL**: Set `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<db>` (with `psycopg[binary]` or `psycopg2-binary` installed). Because seeded rows insert explicit primary-key `id` values, PostgreSQL identity sequences must be synced after seeding; `load_seed.py` executes `SELECT setval(pg_get_serial_sequence('<table>', 'id'), COALESCE((SELECT MAX(id) FROM <table>), 1))` for all five tables automatically when `engine.dialect.name == "postgresql"`.
- **Gemini**: Install `google-genai`, set `LLM_MODE=gemini`, and set `GEMINI_API_KEY` in `.env` (never commit `.env`).

## Endpoint table

| Method & Path | Role | Success | Failure cases |
| --- | --- | --- | --- |
| `GET /health` | anyone | `200` `{"status": "ok"}` | — |
| `POST /auth/register` | anyone | `201` `{"access_token", "token_type"}` | `400` email exists; `422` missing field or password `< 8` chars / `> 72` bytes |
| `POST /auth/login` | anyone | `200` `{"access_token", "token_type"}` | `401` `Wrong email or password` |
| `GET /auth/me` | signed-in user | `200` `{id, email, full_name, role}` | `401` missing, invalid, or expired token |
| `GET /trips` | anyone | `200` paged future trips (`items`, `total`, `page`, `limit`) | `422` invalid query constraint |
| `GET /trips/{trip_id}` | anyone | `200` one trip with `seats_left` | `404` unknown trip |
| `POST /bookings` | `passenger` | `201` new held booking | `401`, `403`, `422`, `404`, `400` departed or insufficient seats |
| `GET /bookings` | `passenger` (own), `operator` (all) | `200` paged bookings | `401`; `403` for `conductor` |
| `POST /bookings/{booking_id}/pay` | `passenger` (owner) | `200` confirmed booking | `403` not owner/role; `400` not `held`; `404` |
| `PATCH /bookings/{booking_id}/status` | `operator`, `conductor` | `200` updated booking | `403`; `422` invalid status literal; `400` invalid move; `404` |
| `POST /bookings/{booking_id}/cancel` | `passenger` (owner) | `200` `{"id", "status": "cancelled", "refund_inr"}` | `403` not owner/role; `400` not cancellable; `404` |
| `GET /operator/summary` | `operator` | `200` revenue, status counts, busiest route | `401`; `403` other roles |
| `POST /operator/release-stale-holds` | `operator` | `200` `{"released", "booking_ids"}` | `401`; `403` other roles |
| `GET /routes/{route_id}/timetable` | anyone | `200` merged operator trip list | `404` unknown route; `422` missing `operator_a` or `operator_b` |
| `POST /ai/search` | anyone | `200` `{parsed, total, trips}` | `422` invalid body; `502` empty or invalid model reply |
| `GET /advisories/search` | anyone | `200` ranked `[{id, title, score}]` | `422` `q` missing / `< 3` chars or `top_k` outside `1..8` |

## Algorithms

| Function | Time complexity | Notes / measured counts |
| --- | --- | --- |
| `merge_sorted(a, b, key)` | `O(n + m)` | Single two-pointer pass; equal keys pick from `a` first |
| `second_highest_fare(fares)` | `O(n)` | Single pass tracking top two distinct fares (`1500` on seed data, max `1530`) |
| `duplicate_bookings(bookings)` | `O(n + k log k)` | One pass with count dict; sorts `k` duplicate `(passenger_id, trip_id)` keys |
| `pairs_for_budget_nested(fares, budget)` | `O(n^2)` | `1225` comparisons on 50 seed fares (`50 * 49 / 2`) |
| `pairs_for_budget_hashed(fares, budget)` | `O(n)` pass (+ `O(p log p)` output sort) | `50` dictionary lookups on 50 seed fares |

A dictionary lookup does not grow with the list's length because Python dictionaries map keys through a hash table to direct bucket slots in `O(1)` average time regardless of how many elements have already been stored.

## Verification log

### Part A — Seed loader and SQL reports (`R1`–`R5`)

`python seed_data.py`:

```text
{'users': 20, 'routes': 10, 'trips': 50, 'bookings': 110, 'ledger': 102}
```

`python load_seed.py` run twice in succession:

```text
loaded: users=20 routes=10 trips=50 bookings=110 ledger=102
loaded: users=20 routes=10 trips=50 bookings=110 ledger=102
```

SQL report outputs (`sql/reports.sql` against `seatdesk.db`):

**R1** (10 rows):

| origin | destination | bookings | seats | amount_inr |
| --- | --- | --- | --- | --- |
| Bengaluru | Chennai | 6 | 24 | 16440 |
| Chennai | Bengaluru | 9 | 21 | 12230 |
| Bengaluru | Hyderabad | 11 | 27 | 33070 |
| Hyderabad | Bengaluru | 7 | 21 | 27900 |
| Pune | Mumbai | 8 | 21 | 6620 |
| Mumbai | Pune | 10 | 29 | 9730 |
| Mumbai | Goa | 7 | 17 | 15450 |
| Goa | Mumbai | 16 | 38 | 37440 |
| Pune | Goa | 8 | 24 | 22100 |
| Hyderabad | Pune | 10 | 18 | 14220 |

**R2** (2 rows):

| bus_type | amount_inr |
| --- | --- |
| AC Seater | 67750 |
| AC Sleeper | 70000 |

**R3** (4 rows):

| id | origin | destination | bookings |
| --- | --- | --- | --- |
| 13 | Bengaluru | Hyderabad | 0 |
| 17 | Hyderabad | Bengaluru | 0 |
| 20 | Hyderabad | Bengaluru | 0 |
| 50 | Hyderabad | Pune | 0 |

**R3 interpretation**: An `INNER JOIN` between `trips` and `bookings` would return `46` trips (only the trips that have at least one booking). Using `COUNT(*)` instead of `COUNT(b.id)` in R3 would report `1` for each of the four empty trips, because the `LEFT JOIN` still emits one row filled with `NULL`s on the booking columns for each unmatched trip and `COUNT(*)` counts rows rather than non-null values in `b.id`.

**R4** (12 rows):

| id | created_at |
| --- | --- |
| 8 | 2026-12-01 08:40:00 |
| 11 | 2026-12-01 08:02:00 |
| 14 | 2026-12-01 08:34:00 |
| 25 | 2026-12-01 08:02:00 |
| 28 | 2026-12-01 08:07:00 |
| 58 | 2026-12-01 08:41:00 |
| 63 | 2026-12-01 08:44:00 |
| 78 | 2026-12-01 08:29:00 |
| 104 | 2026-12-01 08:36:00 |
| 105 | 2026-12-01 08:09:00 |
| 106 | 2026-12-01 08:20:00 |
| 107 | 2026-12-01 08:21:00 |

**R5** (2 rows):

| entry_type | entries | amount_inr |
| --- | --- | --- |
| charge | 90 | 195670 |
| refund | 12 | 12965 |

### Part B — Walkthrough (`W01`–`W28`), JWT tampering, and CORS

```text
W01: GET /health -> 200 {'status': 'ok'}
W02: POST /auth/login (aarav wrong password) -> 401 {'detail': 'Wrong email or password'} | >72B login -> 401
W03: GET /auth/me (aarav) -> 200 {'id': 5, 'email': 'aarav@mail.test', 'full_name': 'Aarav Rao', 'role': 'passenger'}
Tampered JWT: GET /auth/me (tampered signature) -> 401 {'detail': 'Invalid or expired token'}
W04: GET /auth/me (no token) -> 401 {'detail': 'Not authenticated'}
W05: POST /auth/register (new.user@mail.test) -> 201 {'token_type': 'bearer', 'jwt_dots': 2} (3-part JWT)
W06: POST /auth/register (duplicate) -> 400 {'detail': 'Email already registered'}
W07: POST /auth/register (short password) -> 422 | >72B register -> 422 | blank email/name -> 422
W08: GET /trips -> 200 X-Process-Time=0.007167 total=40 page=1 limit=10 ids=[2, 3, 4, 5, 7, 8, 9, 10, 12, 13] first={'id': 2, 'origin': 'Bengaluru', 'destination': 'Chennai', 'operator': 'Highway Kings', 'departure_at': '2026-12-01 18:00:00', 'bus_type': 'AC Sleeper', 'fare_inr': 920, 'seats_left': 26}
W09: GET /trips?origin=Pune&destination=Goa -> 200 total=4 ids=[42, 43, 44, 45] | blank ?origin= -> total=40
W10: GET /trips?max_fare=600 -> 200 total=12 ids=[5, 8, 9, 10, 22, 23, 24, 25, 27, 28]
W11: GET /trips?origin=pune&destination=goa&max_fare=800 -> 200 total=2 ids=[42, 43]
W12: GET /trips?page=2&limit=15 -> 200 total=40 page=2 limit=15 ids=[20, 22, 23, 24, 25, 27, 28, 29, 30, 32, 33, 34, 35, 37, 38]
W13: GET /trips?max_fare=0 -> 422 | GET /trips?limit=51 -> 422
W14: GET /trips/22 -> 200 {'id': 22, 'origin': 'Pune', 'destination': 'Mumbai', 'operator': 'Highway Kings', 'departure_at': '2026-12-01 18:00:00', 'bus_type': 'AC Seater', 'fare_inr': 280, 'seats_left': 35} | GET /trips/999 -> 404
W15: GET /operator/summary (aarav) -> 403 {'detail': 'Insufficient permissions'}
W16: GET /operator/summary (ops.manager) -> 200 {'revenue_inr': 182705, 'bookings_by_status': {'cancelled': 18, 'completed': 16, 'confirmed': 62, 'held': 14}, 'busiest_route': 'Goa to Mumbai', 'busiest_route_seats': 38}
W17: POST /operator/release-stale-holds -> 200 {'released': 12, 'booking_ids': [8, 11, 14, 25, 28, 58, 63, 78, 104, 105, 106, 107]} | repeat -> 200 {'released': 0, 'booking_ids': []}
W18: GET /operator/summary (ops.manager) -> 200 {'revenue_inr': 182705, 'bookings_by_status': {'cancelled': 30, 'completed': 16, 'confirmed': 62, 'held': 2}, 'busiest_route': 'Goa to Mumbai', 'busiest_route_seats': 34}
W19: POST /bookings (trip 22, seats 3, aarav) -> 201 {'id': 111, 'trip_id': 22, 'passenger_id': 5, 'seats': 3, 'amount_inr': 840, 'status': 'held', 'created_at': '2026-12-01 09:00:00'}; notifications.log line: booking 111: trip=22 passenger=5 seats=3 amount_inr=840; GET /trips/22 seats_left=32
W20: invalid bookings -> seats=0: 422; seats=7: 422; trip_id=999: 404; trip_id=1 (departed): 400; ops.manager: 403; no token: 401
W21: 4x POST /bookings (trip 15, seats 6) -> 201 ids 112..115 (8940 each); GET /trips/15 seats_left=0; 5th attempt -> 400 {'detail': 'Only 0 seats are left on this trip'}
W22: POST /bookings/111/pay -> 403 (diya), 200 confirmed (aarav), 400 (aarav repeat)
W23: GET /operator/summary (ops.manager) -> 200 {'revenue_inr': 183545, 'bookings_by_status': {'cancelled': 30, 'completed': 16, 'confirmed': 63, 'held': 6}, 'busiest_route': 'Bengaluru to Hyderabad', 'busiest_route_seats': 47}
W24: PATCH /bookings/111/status + cancel -> aarav boarded: 403; conductor completed: 400; conductor held: 422; conductor boarded: 200 (boarded); conductor boarded repeat: 400; conductor completed: 200 (completed); aarav cancel: 400
W25: Cancellations -> #3 (dev): 200 {'id': 3, 'status': 'cancelled', 'refund_inr': 740}; #18 (ishaan): 200 {'id': 18, 'status': 'cancelled', 'refund_inr': 2034}; #1 (rohan): 200 {'id': 1, 'status': 'cancelled', 'refund_inr': 0}; #1 repeat: 400; #6 (kabir): 200 {'id': 6, 'status': 'cancelled', 'refund_inr': 0}; #2 (rohan): 403
W26: GET /bookings?status=held (ops.manager) -> 200 total=5 ids=[38, 112, 113, 114, 115]
W27: GET /bookings -> aarav: 200 total=15 ids=[22, 27, 28, 35, 41, 62, 72, 82, 91, 106]; conductor.one: 403; ops.manager: 200 total=115
W28: GET /operator/summary (ops.manager) -> 200 {'revenue_inr': 180771, 'bookings_by_status': {'cancelled': 34, 'completed': 17, 'confirmed': 59, 'held': 5}, 'busiest_route': 'Bengaluru to Hyderabad', 'busiest_route_seats': 45}
Post-W28 ledger check: total=105, refunds=14 | DB CHECK constraints verified
```

CORS preflight evidence (`OPTIONS /bookings`):

```text
Allowed Origin (http://localhost:5500):
  Status: 200
  access-control-allow-origin: http://localhost:5500
  access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY

Disallowed Origin (http://evil.test):
  Status: 400
  Body: Disallowed CORS origin
  access-control-allow-origin: (absent)
```

### Part C — Algorithms, timetable, AI search, and advisory search (`C1`–`C4`)

```text
C1 Algorithms:
  merge_sorted([360, 540, 1320], [375, 540, 900]) -> [360, 375, 540, 540, 900, 1320]
  merge_sorted([], [5]) -> [5]
  merge_sorted([(1, 'a'), (2, 'a')], [(1, 'b'), (2, 'b')], key=lambda t: t[0]) -> [(1, 'a'), (1, 'b'), (2, 'a'), (2, 'b')]
  second_highest_fare(seed fares) -> 1500 (max=1530)
  duplicate_bookings(seed bookings) -> [(6, 15), (15, 48), (18, 47), (20, 43)]
  pairs_for_budget(1000) -> [(0, 25), (2, 24), (23, 42), (27, 42)] | nested_cmp=1225, hashed_lookups=50
  pairs_for_budget(1500) -> [(0, 34), (2, 33), (17, 29), (20, 30), (20, 43), (25, 40), (35, 45), (35, 47), (42, 44), (45, 46), (46, 47)] | nested_cmp=1225, hashed_lookups=50
  cosine_similarity unit checks -> [1.0, 0.0, 0.0, 1.0, 0.5]

C2 Timetable (fresh DB):
  GET /routes/1/timetable?operator_a=Coastline%20Express&operator_b=Highway%20Kings ->
    [{'trip_id': 2, 'operator': 'Highway Kings', 'departure_at': '2026-12-01 18:00:00'},
     {'trip_id': 3, 'operator': 'Coastline Express', 'departure_at': '2026-12-02 06:15:00'},
     {'trip_id': 4, 'operator': 'Highway Kings', 'departure_at': '2026-12-02 21:45:00'},
     {'trip_id': 5, 'operator': 'Coastline Express', 'departure_at': '2026-12-03 10:00:00'}]
  Swapped operator_a / operator_b -> identical list
  operator_a=Highway Kings&operator_b=Nobody -> trip_ids [2, 4]
  GET /routes/999/timetable -> 404 | missing operator_b -> 422

C3 AI Search (fresh DB, LLM_MODE=mock):
  "Pune to Goa under 800" -> 200 total=2 ids=[42, 43] parsed={'origin': 'Pune', 'destination': 'Goa', 'max_fare_inr': 800, 'bus_type': None}
  "I need an AC sleeper from Mumbai to Goa below INR 1,200" -> 200 total=0 ids=[] parsed={'origin': 'Mumbai', 'destination': 'Goa', 'max_fare_inr': 1200, 'bus_type': 'AC Sleeper'}
  "non ac bus Hyderabad to Pune" -> 200 total=2 ids=[47, 48] parsed={'origin': 'Hyderabad', 'destination': 'Pune', 'max_fare_inr': None, 'bus_type': 'Non-AC Seater'}
  "anything leaving Chennai" -> 200 total=4 ids=[7, 8, 9, 10] parsed={'origin': 'Chennai', 'destination': None, 'max_fare_inr': None, 'bus_type': None}
  "cheap bus to Bengaluru within 600 rupees" -> 200 total=3 ids=[8, 9, 10] parsed={'origin': None, 'destination': 'Bengaluru', 'max_fare_inr': 600, 'bus_type': None}
  "hello there" -> 502 {'detail': 'Could not understand trip search query'}
  "Delhi to Jaipur under 500" -> 502 {'detail': 'Could not understand trip search query'}

C4 Advisories Search:
  "refund for cancelling a ticket" -> [(1, 'Cancellation and refund policy', 0.4042), (3, 'Boarding time', 0.3397), (8, 'Delayed departure', 0.2981)]
  "luggage kg allowance" -> [(2, 'Luggage allowance', 0.6236), (6, 'Rest stops', 0.2722), (3, 'Boarding time', 0.2265)]
  "pay seat hold within minutes" -> [(5, 'Seat hold timer', 0.6025), (7, 'Child fares', 0.2683), (3, 'Boarding time', 0.2631)]
  "child ticket" -> [(7, 'Child fares', 0.4243), (3, 'Boarding time', 0.2774), (8, 'Delayed departure', 0.1826)]
  q="ab" -> 422 | q="   " -> 422
```

### Part D — Browser client verification (`F1`–`F10`)

Executed against a freshly seeded database on `http://localhost:5500` talking to `http://127.0.0.1:8000`:

- **F1**: Open page -> `GET http://127.0.0.1:8000/trips` (`200`); `10` `.trip-card` elements; `#message` reads `40 trips found`.
- **F2**: Submit `origin=Pune`, `destination=Goa` -> `GET http://127.0.0.1:8000/trips?origin=Pune&destination=Goa` (`200`); `4` cards; `#message` reads `4 trips found`; first card `<h3>` reads `Pune to Goa`.
- **F3**: Submit `max-fare=abc`, then `0` -> `#message` reads `Max fare must be a positive whole number` both times; `0` network requests sent.
- **F4**: Clear `origin` and `destination`, submit `max-fare=600` -> `GET http://127.0.0.1:8000/trips?max_fare=600` (`200`); `#message` reads `12 trips found`; `10` cards rendered.
- **F5**: Clear `destination` and `max-fare`, submit `origin=Delhi` -> `GET http://127.0.0.1:8000/trips?origin=Delhi` (`200`); `0` cards; `1` `.empty` element reading `No trips found`.
- **F6**: Search `Pune` to `Goa` again (first card shows `41 seats left`), click `.book-btn` while signed out -> `#message` reads `Please log in first`; `0` `POST /bookings` requests sent.
- **F7**: Sign in as `diya@mail.test` with `wrongpass` -> `POST http://127.0.0.1:8000/auth/login` (`401`); `#message` reads `Wrong email or password`; `seatdesk_token` stays unset.
- **F8**: Sign in as `diya@mail.test` with `SeatDesk@2026` -> `POST http://127.0.0.1:8000/auth/login` (`200`); `#message` reads `Logged in as diya@mail.test`; JWT stored under `seatdesk_token` (API response confirmed 3-part / 2-dot JWT format).
- **F9**: Click `.book-btn` on trip 42 -> `POST http://127.0.0.1:8000/bookings` (`201`) followed by reload `GET http://127.0.0.1:8000/trips?origin=Pune&destination=Goa` (`200`); after reload settles, `#message` still reads `Seat held: booking #111, INR 620`.
- **F10**: Inspect trip 42 card again -> seats left decremented from `41 seats left` to `40 seats left`; `#message` still reads `Seat held: booking #111, INR 620`.
