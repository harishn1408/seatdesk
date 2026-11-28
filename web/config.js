// Override before loading api.js on production.
window.API_BASE = window.API_BASE || (location.hostname.endsWith(".onrender.com")
  ? "https://seatdesk-3bdx.onrender.com"
  : "http://127.0.0.1:8000");
