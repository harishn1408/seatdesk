"""Offline, deterministic stand-ins for an LLM and an embedding model. No key, no network."""
import json
import re
import zlib

KNOWN_CITIES = ["Bengaluru", "Chennai", "Hyderabad", "Pune", "Mumbai", "Goa"]


def mock_parse_trip_request(text):
    """Return a JSON *string* with keys origin, destination, max_fare_inr, bus_type (null when absent), or "" (an empty reply) when nothing useful can be extracted."""
    lowered = text.lower()
    found = sorted((lowered.find(c.lower()), c) for c in KNOWN_CITIES if c.lower() in lowered)
    cities = [c for _, c in found]
    origin = destination = None
    if len(cities) >= 2:
        origin, destination = cities[0], cities[1]
    elif len(cities) == 1:
        if re.search(r"\bto\s+" + cities[0].lower(), lowered):
            destination = cities[0]
        else:
            origin = cities[0]
    fare = re.search(r"(?:under|below|within|upto|up to|max)\s*(?:inr|rs\.?|rupees)?\s*(\d[\d,]*)", lowered)
    max_fare = int(fare.group(1).replace(",", "")) if fare else None
    bus_type = None
    if re.search(r"non[- ]?ac", lowered):
        bus_type = "Non-AC Seater"
    elif "sleeper" in lowered:
        bus_type = "AC Sleeper"
    elif re.search(r"\bac\b", lowered):
        bus_type = "AC Seater"
    if not cities and re.search(r"\bto\b", lowered):  # a route between places we do not serve
        return ""
    if origin is None and destination is None and max_fare is None and bus_type is None:
        return ""
    return json.dumps({"origin": origin, "destination": destination, "max_fare_inr": max_fare, "bus_type": bus_type})


STOP_WORDS = {"a", "an", "the", "i", "if", "is", "are", "of", "to", "in", "for", "and", "or", "at", "it", "my", "you", "can", "be", "on", "this", "that", "with", "than", "each", "may"}


def mock_embed(text, dim=256):
    """Hashed bag-of-words embedding: one count per word bucket (crc32 is stable across runs)."""
    vec = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word not in STOP_WORDS:
            vec[zlib.crc32(word.encode()) % dim] += 1.0
    return vec
