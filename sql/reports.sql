-- R1
SELECT
    r.origin,
    r.destination,
    COUNT(b.id) AS bookings,
    SUM(b.seats) AS seats,
    SUM(b.amount_inr) AS amount_inr
FROM bookings b
JOIN trips t ON b.trip_id = t.id
JOIN routes r ON t.route_id = r.id
WHERE b.status != 'cancelled'
GROUP BY r.id, r.origin, r.destination;

-- R2
SELECT
    t.bus_type,
    SUM(b.amount_inr) AS amount_inr
FROM bookings b
JOIN trips t ON b.trip_id = t.id
WHERE b.status != 'cancelled'
GROUP BY t.bus_type
HAVING SUM(b.amount_inr) > 60000;

-- R3
SELECT
    t.id,
    r.origin,
    r.destination,
    COUNT(b.id) AS bookings
FROM trips t
JOIN routes r ON t.route_id = r.id
LEFT JOIN bookings b ON b.trip_id = t.id
GROUP BY t.id, r.origin, r.destination
HAVING COUNT(b.id) = 0;

-- R4
SELECT
    id,
    created_at
FROM bookings
WHERE status = 'held'
  AND created_at < '2026-12-01 08:45:00';

-- R5
SELECT
    entry_type,
    COUNT(id) AS entries,
    SUM(amount_inr) AS amount_inr
FROM ledger
GROUP BY entry_type;
