"""LLM query extraction client (offline mock default, optional Gemini mode)."""
import os

from dotenv import load_dotenv
from pydantic import ValidationError

from mock_llm import mock_parse_trip_request
from schemas import TripQuery

load_dotenv()


class LLMParseError(Exception):
    """Raised when the model returns an empty or schema-invalid response."""


def _validate_trip_query_json(raw: str, source: str) -> TripQuery:
    if not raw or not raw.strip():
        raise LLMParseError("Could not understand trip search query")
    try:
        return TripQuery.model_validate_json(raw)
    except ValidationError as exc:
        raise LLMParseError(f"Invalid structured query from {source}") from exc


def extract_trip_query(text: str) -> TripQuery:
    """Parse free-text trip search input into a validated TripQuery."""
    mode = (os.getenv("LLM_MODE") or "mock").strip().lower()
    if mode == "mock":
        return _validate_trip_query_json(mock_parse_trip_request(text), "mock")

    if mode == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or ""
        if not api_key:
            raise LLMParseError("GEMINI_API_KEY is not configured")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMParseError("google-genai package is not installed") from exc

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TripQuery,
                system_instruction=(
                    "Extract origin, destination, max_fare_inr, and bus_type "
                    "(AC Sleeper, AC Seater, or Non-AC Seater) from the request."
                ),
            ),
        )
        return _validate_trip_query_json(getattr(response, "text", None) or "", "Gemini")

    raise LLMParseError(f"Unsupported LLM_MODE: {mode}")
