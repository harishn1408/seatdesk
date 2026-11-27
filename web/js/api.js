const API_BASE = "http://127.0.0.1:8000";

function buildTripsUrl(origin, destination, maxFare) {
  const params = [];
  if (origin) {
    params.push("origin=" + encodeURIComponent(origin));
  }
  if (destination) {
    params.push("destination=" + encodeURIComponent(destination));
  }
  if (maxFare) {
    params.push("max_fare=" + encodeURIComponent(maxFare));
  }
  const query = params.join("&");
  return query ? `${API_BASE}/trips?${query}` : `${API_BASE}/trips`;
}

function fetchTrips(origin, destination, maxFare) {
  return fetch(buildTripsUrl(origin, destination, maxFare)).then(res => res.json());
}

function postJsonWithStatus(path, body, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(body),
  }).then(res =>
    res.json().then(data => ({ status: res.status, data: data }))
  );
}

function loginRequest(email, password) {
  return postJsonWithStatus("/auth/login", { email: email, password: password }, null);
}

function createBookingRequest(tripId, token) {
  return postJsonWithStatus("/bookings", { trip_id: tripId, seats: 1 }, token);
}
