const TOKEN_KEY = "seatdesk_token";

const loginForm = document.getElementById("login-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const logoutBtn = document.getElementById("logout-btn");

const searchForm = document.getElementById("search-form");
const originInput = document.getElementById("origin");
const destinationInput = document.getElementById("destination");
const maxFareInput = document.getElementById("max-fare");

const messageEl = document.getElementById("message");
const tripListEl = document.getElementById("trip-list");

const studioMessageEl = document.getElementById("studio-message");
const studioTabsEl = document.querySelector(".studio-tabs");
const aiForm = document.getElementById("ai-form");
const aiQueryInput = document.getElementById("ai-query");
const aiChipsEl = document.getElementById("ai-chips");
const aiParsedEl = document.getElementById("ai-parsed");
const aiResultsEl = document.getElementById("ai-results");

const advisoryForm = document.getElementById("advisory-form");
const advisoryQueryInput = document.getElementById("advisory-query");
const advisoryChipsEl = document.getElementById("advisory-chips");
const advisoryResultsEl = document.getElementById("advisory-results");

const timetableForm = document.getElementById("timetable-form");
const routeSelectEl = document.getElementById("route-select");
const opASelectEl = document.getElementById("op-a");
const opBSelectEl = document.getElementById("op-b");
const timetableResultsEl = document.getElementById("timetable-results");

const loadDeskBtn = document.getElementById("load-desk-btn");
const deskContentEl = document.getElementById("desk-content");

function setMessage(text) {
  messageEl.textContent = text;
  messageEl.classList.remove("is-updated");
  void messageEl.offsetWidth;
  messageEl.classList.add("is-updated");
}

function setStudioMessage(text) {
  studioMessageEl.textContent = text;
}

function renderTrips(items) {
  tripListEl.replaceChildren();
  if (!items || items.length === 0) {
    const emptyEl = document.createElement("p");
    emptyEl.className = "empty";
    emptyEl.textContent = "No trips found";
    tripListEl.appendChild(emptyEl);
    return;
  }

  for (const trip of items) {
    const card = document.createElement("article");
    card.className = "trip-card";

    const title = document.createElement("h3");
    title.textContent = `${trip.origin} to ${trip.destination}`;

    const meta = document.createElement("p");
    meta.textContent = `${trip.operator} - ${trip.bus_type}`;

    const departure = document.createElement("p");
    departure.textContent = trip.departure_at;

    const fare = document.createElement("p");
    fare.textContent = `INR ${trip.fare_inr}`;

    const seats = document.createElement("p");
    seats.textContent = `${trip.seats_left} seats left`;

    const bookBtn = document.createElement("button");
    bookBtn.type = "button";
    bookBtn.className = "book-btn";
    bookBtn.setAttribute("data-trip-id", String(trip.id));
    bookBtn.textContent = "Book 1 seat";

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(departure);
    card.appendChild(fare);
    card.appendChild(seats);
    card.appendChild(bookBtn);
    tripListEl.appendChild(card);
  }
}

function loadTrips(updateMessage) {
  const origin = originInput.value.trim();
  const destination = destinationInput.value.trim();
  const maxFare = maxFareInput.value.trim();

  if (maxFare !== "" && !/^[1-9]\d*$/.test(maxFare)) {
    setMessage("Max fare must be a positive whole number");
    return;
  }

  fetchTrips(origin, destination, maxFare)
    .then(data => {
      if (!Array.isArray(data.items)) {
        if (typeof data.detail === "string") {
          setMessage(data.detail);
        }
        return;
      }
      renderTrips(data.items);
      if (updateMessage) {
        setMessage(`${data.total} trips found`);
      }
    })
    .catch(() => {
      setMessage("Could not reach SeatDesk");
    });
}

searchForm.addEventListener("submit", event => {
  event.preventDefault();
  loadTrips(true);
});

loginForm.addEventListener("submit", event => {
  event.preventDefault();
  const email = emailInput.value.trim();
  const password = passwordInput.value;

  loginRequest(email, password)
    .then(result => {
      if (result.status === 200 && result.data.access_token) {
        localStorage.setItem(TOKEN_KEY, result.data.access_token);
        setMessage(`Logged in as ${email}`);
      } else if (typeof result.data.detail === "string") {
        setMessage(result.data.detail);
      }
    })
    .catch(() => {
      setMessage("Could not reach SeatDesk");
    });
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  setMessage("Signed out");
  deskContentEl.replaceChildren();
});

tripListEl.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.classList.contains("book-btn")) {
    return;
  }

  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    setMessage("Please log in first");
    return;
  }

  const tripId = Number(event.target.getAttribute("data-trip-id"));
  createBookingRequest(tripId, token)
    .then(result => {
      if (result.status === 201) {
        setMessage(`Seat held: booking #${result.data.id}, INR ${result.data.amount_inr}`);
        loadTrips(false);
      } else if (typeof result.data.detail === "string") {
        setMessage(result.data.detail);
      }
    })
    .catch(() => {
      setMessage("Could not reach SeatDesk");
    });
});

/* Studio Workspace */
studioTabsEl.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.classList.contains("studio-tab")) {
    return;
  }
  const tabName = event.target.getAttribute("data-tab");
  for (const btn of studioTabsEl.querySelectorAll(".studio-tab")) {
    btn.classList.toggle("is-active", btn === event.target);
  }
  const panes = {
    ai: document.getElementById("pane-ai"),
    timetable: document.getElementById("pane-timetable"),
    role: document.getElementById("pane-role"),
  };
  for (const [key, paneEl] of Object.entries(panes)) {
    paneEl.classList.toggle("is-hidden", key !== tabName);
  }
});

function renderAiSearch(data) {
  aiParsedEl.replaceChildren();
  const parsed = data.parsed || {};
  const labels = [
    ["origin", parsed.origin],
    ["destination", parsed.destination],
    ["max_fare_inr", parsed.max_fare_inr !== null && parsed.max_fare_inr !== undefined ? `INR ${parsed.max_fare_inr}` : null],
    ["bus_type", parsed.bus_type],
  ];
  for (const [k, v] of labels) {
    if (v) {
      const pill = document.createElement("span");
      pill.className = "filter-pill";
      pill.textContent = `${k}: ${v}`;
      aiParsedEl.appendChild(pill);
    }
  }

  aiResultsEl.replaceChildren();
  if (!data.trips || data.trips.length === 0) {
    const empty = document.createElement("p");
    empty.className = "studio-hint";
    empty.textContent = "No matching future trips.";
    aiResultsEl.appendChild(empty);
    return;
  }

  for (const trip of data.trips) {
    const card = document.createElement("article");
    card.className = "mini-card";

    const h4 = document.createElement("h4");
    h4.textContent = `${trip.origin} to ${trip.destination}`;

    const info = document.createElement("p");
    info.textContent = `${trip.operator} · ${trip.bus_type}`;

    const price = document.createElement("p");
    price.textContent = `${trip.departure_at} · INR ${trip.fare_inr} (${trip.seats_left} left)`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "studio-btn ai-book-btn";
    btn.setAttribute("data-trip-id", String(trip.id));
    btn.textContent = "Book 1 seat";

    card.appendChild(h4);
    card.appendChild(info);
    card.appendChild(price);
    card.appendChild(btn);
    aiResultsEl.appendChild(card);
  }
}

function runAiSearch(queryText) {
  aiSearchTrips(queryText)
    .then(res => {
      if (res.status === 200) {
        renderAiSearch(res.data);
        setStudioMessage(`AI search matched ${res.data.total} trip(s)`);
      } else {
        aiParsedEl.replaceChildren();
        aiResultsEl.replaceChildren();
        setStudioMessage(typeof res.data.detail === "string" ? res.data.detail : "AI search failed");
      }
    })
    .catch(() => setStudioMessage("Could not reach SeatDesk"));
}

aiForm.addEventListener("submit", event => {
  event.preventDefault();
  runAiSearch(aiQueryInput.value.trim());
});

aiChipsEl.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.classList.contains("prompt-chip")) {
    return;
  }
  const promptText = event.target.getAttribute("data-ai-prompt");
  aiQueryInput.value = promptText;
  runAiSearch(promptText);
});

aiResultsEl.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.classList.contains("ai-book-btn")) {
    return;
  }
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    setStudioMessage("Please log in first");
    return;
  }
  const tripId = Number(event.target.getAttribute("data-trip-id"));
  createBookingRequest(tripId, token)
    .then(res => {
      if (res.status === 201) {
        setStudioMessage(`Seat held: booking #${res.data.id}, INR ${res.data.amount_inr}`);
        runAiSearch(aiQueryInput.value.trim());
        loadTrips(false);
      } else if (typeof res.data.detail === "string") {
        setStudioMessage(res.data.detail);
      }
    })
    .catch(() => setStudioMessage("Could not reach SeatDesk"));
});

function runAdvisorySearch(queryText) {
  searchAdvisories(queryText, 3)
    .then(res => {
      advisoryResultsEl.replaceChildren();
      if (res.status !== 200 || !Array.isArray(res.data)) {
        setStudioMessage(typeof res.data.detail === "string" ? res.data.detail : "Policy search error");
        return;
      }
      for (const hit of res.data) {
        const item = document.createElement("article");
        item.className = "advisory-hit";

        const title = document.createElement("h4");
        title.textContent = `#${hit.id} · ${hit.title}`;

        const score = document.createElement("p");
        score.textContent = `Cosine similarity: ${hit.score.toFixed(4)}`;

        const meter = document.createElement("progress");
        meter.className = "score-meter";
        meter.max = 1;
        meter.value = hit.score;

        item.appendChild(title);
        item.appendChild(score);
        item.appendChild(meter);
        advisoryResultsEl.appendChild(item);
      }
      setStudioMessage(`Top ${res.data.length} advisories ranked`);
    })
    .catch(() => setStudioMessage("Could not reach SeatDesk"));
}

advisoryForm.addEventListener("submit", event => {
  event.preventDefault();
  runAdvisorySearch(advisoryQueryInput.value.trim());
});

advisoryChipsEl.addEventListener("click", event => {
  if (!(event.target instanceof Element) || !event.target.classList.contains("prompt-chip")) {
    return;
  }
  const promptText = event.target.getAttribute("data-adv-prompt");
  advisoryQueryInput.value = promptText;
  runAdvisorySearch(promptText);
});

timetableForm.addEventListener("submit", event => {
  event.preventDefault();
  fetchTimetable(routeSelectEl.value, opASelectEl.value, opBSelectEl.value)
    .then(res => {
      timetableResultsEl.replaceChildren();
      if (res.status !== 200 || !Array.isArray(res.data)) {
        setStudioMessage("Could not load timetable");
        return;
      }
      if (res.data.length === 0) {
        const empty = document.createElement("p");
        empty.className = "studio-hint";
        empty.textContent = "No future departures for selected operators.";
        timetableResultsEl.appendChild(empty);
      } else {
        for (const row of res.data) {
          const item = document.createElement("div");
          item.className = "timeline-item";

          const left = document.createElement("strong");
          left.textContent = `Trip #${row.trip_id} · ${row.departure_at}`;

          const badge = document.createElement("span");
          badge.className = "status-pill";
          badge.textContent = row.operator;

          item.appendChild(left);
          item.appendChild(badge);
          timetableResultsEl.appendChild(item);
        }
      }
      setStudioMessage(`Merged ${res.data.length} departure(s) via merge_sorted`);
    })
    .catch(() => setStudioMessage("Could not reach SeatDesk"));
});

function buildBookingRows(bookings, role) {
  const list = document.createElement("div");
  list.className = "booking-list";
  for (const b of bookings) {
    const row = document.createElement("div");
    row.className = "booking-row";

    const label = document.createElement("span");
    label.textContent = `#${b.id} · Trip ${b.trip_id} · ${b.seats} seat(s) · INR ${b.amount_inr} · ${b.status}`;

    const actions = document.createElement("div");
    actions.className = "booking-actions";

    if (role === "passenger" && b.status === "held") {
      const payBtn = document.createElement("button");
      payBtn.type = "button";
      payBtn.className = "studio-btn";
      payBtn.setAttribute("data-action", "pay");
      payBtn.setAttribute("data-booking-id", String(b.id));
      payBtn.textContent = "Pay Hold";
      actions.appendChild(payBtn);
    }
    if (role === "passenger" && (b.status === "held" || b.status === "confirmed")) {
      const cancelBtn = document.createElement("button");
      cancelBtn.type = "button";
      cancelBtn.className = "secondary-btn";
      cancelBtn.setAttribute("data-action", "cancel");
      cancelBtn.setAttribute("data-booking-id", String(b.id));
      cancelBtn.textContent = "Cancel";
      actions.appendChild(cancelBtn);
    }
    if ((role === "operator" || role === "conductor") && b.status === "confirmed") {
      const boardBtn = document.createElement("button");
      boardBtn.type = "button";
      boardBtn.className = "secondary-btn";
      boardBtn.setAttribute("data-action", "boarded");
      boardBtn.setAttribute("data-booking-id", String(b.id));
      boardBtn.textContent = "Mark Boarded";
      actions.appendChild(boardBtn);
    }
    if ((role === "operator" || role === "conductor") && b.status === "boarded") {
      const compBtn = document.createElement("button");
      compBtn.type = "button";
      compBtn.className = "secondary-btn";
      compBtn.setAttribute("data-action", "completed");
      compBtn.setAttribute("data-booking-id", String(b.id));
      compBtn.textContent = "Mark Completed";
      actions.appendChild(compBtn);
    }

    row.appendChild(label);
    row.appendChild(actions);
    list.appendChild(row);
  }
  return list;
}

function loadRoleDesk(showMessage = true) {
  const token = localStorage.getItem(TOKEN_KEY);
  deskContentEl.replaceChildren();
  if (!token) {
    const p = document.createElement("p");
    p.className = "studio-hint";
    p.textContent = "Sign in above first, then click Load My Desk.";
    deskContentEl.appendChild(p);
    if (showMessage) {
      setStudioMessage("Please log in first");
    }
    return;
  }

  fetchMe(token)
    .then(meRes => {
      if (meRes.status !== 200) {
        if (showMessage) {
          setStudioMessage(typeof meRes.data.detail === "string" ? meRes.data.detail : "Session invalid");
        }
        return;
      }
      const user = meRes.data;
      const banner = document.createElement("p");
      banner.className = "status-pill";
      banner.textContent = `${user.full_name} (${user.role}) · ${user.email}`;
      deskContentEl.appendChild(banner);

      if (user.role === "passenger") {
        fetchBookings(token).then(bRes => {
          if (bRes.status === 200) {
            deskContentEl.appendChild(buildBookingRows(bRes.data.items, user.role));
            if (showMessage) {
              setStudioMessage(`Loaded ${bRes.data.total} booking(s) for ${user.email}`);
            }
          }
        });
      } else if (user.role === "conductor") {
        const form = document.createElement("form");
        form.id = "conductor-form";
        form.className = "inline-action-form";
        const idInput = document.createElement("input");
        idInput.id = "conductor-booking-id";
        idInput.type = "number";
        idInput.min = "1";
        idInput.placeholder = "Booking ID (e.g. 111)";
        idInput.required = true;

        const boardBtn = document.createElement("button");
        boardBtn.type = "button";
        boardBtn.className = "studio-btn";
        boardBtn.setAttribute("data-conductor-status", "boarded");
        boardBtn.textContent = "Mark Boarded";

        const compBtn = document.createElement("button");
        compBtn.type = "button";
        compBtn.className = "secondary-btn";
        compBtn.setAttribute("data-conductor-status", "completed");
        compBtn.textContent = "Mark Completed";

        form.appendChild(idInput);
        form.appendChild(boardBtn);
        form.appendChild(compBtn);
        deskContentEl.appendChild(form);
        if (showMessage) {
          setStudioMessage(`Conductor boarding desk ready for ${user.full_name}`);
        }
      } else if (user.role === "operator") {
        Promise.all([fetchOperatorSummary(token), fetchBookings(token)]).then(([sumRes, bRes]) => {
          if (sumRes.status === 200) {
            const s = sumRes.data;
            const kpis = document.createElement("div");
            kpis.className = "kpi-grid";
            const items = [
              ["Net Revenue", `INR ${s.revenue_inr}`],
              ["Busiest Corridor", `${s.busiest_route} (${s.busiest_route_seats} seats)`],
              ["Confirmed", String(s.bookings_by_status.confirmed || 0)],
              ["Active Holds", String(s.bookings_by_status.held || 0)],
            ];
            for (const [k, v] of items) {
              const box = document.createElement("div");
              box.className = "kpi-box";
              const lbl = document.createElement("span");
              lbl.className = "kpi-label";
              lbl.textContent = k;
              const val = document.createElement("span");
              val.className = "kpi-value";
              val.textContent = v;
              box.appendChild(lbl);
              box.appendChild(val);
              kpis.appendChild(box);
            }
            deskContentEl.appendChild(kpis);

            const actions = document.createElement("div");
            actions.className = "desk-actions";
            const relBtn = document.createElement("button");
            relBtn.type = "button";
            relBtn.className = "studio-btn";
            relBtn.setAttribute("data-action", "release-stale");
            relBtn.textContent = "Release Stale Holds (>15m)";
            actions.appendChild(relBtn);
            deskContentEl.appendChild(actions);
          }
          if (bRes.status === 200) {
            deskContentEl.appendChild(buildBookingRows(bRes.data.items, user.role));
          }
          if (showMessage) {
            setStudioMessage("Operator summary loaded");
          }
        });
      }
    })
    .catch(() => setStudioMessage("Could not reach SeatDesk"));
}

loadDeskBtn.addEventListener("click", () => loadRoleDesk(true));

deskContentEl.addEventListener("click", event => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    setStudioMessage("Please log in first");
    return;
  }

  const conductorStatus = event.target.getAttribute("data-conductor-status");
  if (conductorStatus) {
    const idField = document.getElementById("conductor-booking-id");
    const bid = Number(idField ? idField.value : 0);
    if (!bid) {
      setStudioMessage("Enter a valid booking ID");
      return;
    }
    updateBookingStatusRequest(bid, conductorStatus, token).then(res => {
      if (res.status === 200) {
        setStudioMessage(`Booking #${res.data.id} moved to ${res.data.status}`);
      } else if (typeof res.data.detail === "string") {
        setStudioMessage(res.data.detail);
      }
    });
    return;
  }

  const action = event.target.getAttribute("data-action");
  if (!action) {
    return;
  }
  if (action === "release-stale") {
    releaseStaleHoldsRequest(token).then(res => {
      if (res.status === 200) {
        setStudioMessage(`Released ${res.data.released} stale hold(s): [${res.data.booking_ids.join(", ")}]`);
        loadRoleDesk(false);
        loadTrips(false);
      }
    });
    return;
  }

  const bookingId = Number(event.target.getAttribute("data-booking-id"));
  if (action === "pay") {
    payBookingRequest(bookingId, token).then(res => {
      if (res.status === 200) {
        setStudioMessage(`Booking #${res.data.id} confirmed (INR ${res.data.amount_inr} charged)`);
        loadRoleDesk(false);
      } else if (typeof res.data.detail === "string") {
        setStudioMessage(res.data.detail);
      }
    });
  } else if (action === "cancel") {
    cancelBookingRequest(bookingId, token).then(res => {
      if (res.status === 200) {
        setStudioMessage(`Booking #${res.data.id} cancelled · refund INR ${res.data.refund_inr}`);
        loadRoleDesk(false);
        loadTrips(false);
      } else if (typeof res.data.detail === "string") {
        setStudioMessage(res.data.detail);
      }
    });
  } else if (action === "boarded" || action === "completed") {
    updateBookingStatusRequest(bookingId, action, token).then(res => {
      if (res.status === 200) {
        setStudioMessage(`Booking #${res.data.id} updated to ${res.data.status}`);
        loadRoleDesk(false);
      } else if (typeof res.data.detail === "string") {
        setStudioMessage(res.data.detail);
      }
    });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  loadTrips(true);
});
