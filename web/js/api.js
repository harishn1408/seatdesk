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

function requestJsonWithStatus(path, method, body, token) {
  const headers = {};
  if (body !== null && body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const options = { method: method, headers: headers };
  if (body !== null && body !== undefined) {
    options.body = JSON.stringify(body);
  }
  return fetch(`${API_BASE}${path}`, options).then(res =>
    res.json().then(data => ({ status: res.status, data: data }))
  );
}

function postJsonWithStatus(path, body, token) {
  return requestJsonWithStatus(path, "POST", body, token);
}

function loginRequest(email, password) {
  return postJsonWithStatus("/auth/login", { email: email, password: password }, null);
}

function createBookingRequest(tripId, token) {
  return postJsonWithStatus("/bookings", { trip_id: tripId, seats: 1 }, token);
}

function aiSearchTrips(query) {
  return postJsonWithStatus("/ai/search", { query: query }, null);
}

function searchAdvisories(query, topK) {
  const url = `/advisories/search?q=${encodeURIComponent(query)}&top_k=${encodeURIComponent(topK || 3)}`;
  return requestJsonWithStatus(url, "GET", null, null);
}

function fetchTimetable(routeId, operatorA, operatorB) {
  const url = `/routes/${encodeURIComponent(routeId)}/timetable?operator_a=${encodeURIComponent(operatorA)}&operator_b=${encodeURIComponent(operatorB)}`;
  return requestJsonWithStatus(url, "GET", null, null);
}

function fetchMe(token) {
  return requestJsonWithStatus("/auth/me", "GET", null, token);
}

function fetchBookings(token) {
  return requestJsonWithStatus("/bookings?limit=20", "GET", null, token);
}

function payBookingRequest(bookingId, token) {
  return postJsonWithStatus(`/bookings/${encodeURIComponent(bookingId)}/pay`, null, token);
}

function cancelBookingRequest(bookingId, token) {
  return postJsonWithStatus(`/bookings/${encodeURIComponent(bookingId)}/cancel`, null, token);
}

function updateBookingStatusRequest(bookingId, statusValue, token) {
  return requestJsonWithStatus(`/bookings/${encodeURIComponent(bookingId)}/status`, "PATCH", { status: statusValue }, token);
}

function fetchOperatorSummary(token) {
  return requestJsonWithStatus("/operator/summary", "GET", null, token);
}

function releaseStaleHoldsRequest(token) {
  return postJsonWithStatus("/operator/release-stale-holds", null, token);
}
