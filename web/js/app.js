const TOKEN_KEY = "seatdesk_token";

const loginForm = document.getElementById("login-form");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");

const searchForm = document.getElementById("search-form");
const originInput = document.getElementById("origin");
const destinationInput = document.getElementById("destination");
const maxFareInput = document.getElementById("max-fare");

const messageEl = document.getElementById("message");
const tripListEl = document.getElementById("trip-list");

function setMessage(text) {
  if (!messageEl) {
    return;
  }
  messageEl.textContent = text;
  messageEl.classList.remove("is-updated");
  void messageEl.offsetWidth;
  messageEl.classList.add("is-updated");
}

function renderTrips(items) {
  if (!tripListEl) {
    return;
  }
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
  if (!searchForm || !tripListEl) {
    return;
  }
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

if (loginForm) {
  loginForm.addEventListener("submit", event => {
    event.preventDefault();
    const email = emailInput.value.trim();
    const password = passwordInput.value;

    loginRequest(email, password)
      .then(result => {
        if (result.status === 200 && result.data.access_token) {
          localStorage.setItem(TOKEN_KEY, result.data.access_token);
          setMessage(`Logged in as ${email}`);
          if (!tripListEl) {
            setTimeout(() => {
              window.location.href = "index.html";
            }, 450);
          }
        } else if (typeof result.data.detail === "string") {
          setMessage(result.data.detail);
        }
      })
      .catch(() => {
        setMessage("Could not reach SeatDesk");
      });
  });
}

if (searchForm && tripListEl) {
  searchForm.addEventListener("submit", event => {
    event.preventDefault();
    loadTrips(true);
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

  document.addEventListener("DOMContentLoaded", () => {
    loadTrips(true);
  });
}
