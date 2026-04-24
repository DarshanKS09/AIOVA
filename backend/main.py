import json
import os
import re
from typing import Dict

from dateutil import parser as date_parser
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


SYSTEM_PROMPT = """Extract structured interaction data from the user input.

Return ONLY valid JSON. No explanation.

Fields:

* hcp_name
* interaction_type (Meeting / Call / Visit / Other)
* date (YYYY-MM-DD)
* time (HH:MM 24h)
* attendees
* topics
* materials

If a field is missing, return empty string.

DO NOT RETURN ANY TEXT OUTSIDE JSON."""

EXPECTED_FIELDS = {
    "hcp_name": "",
    "interaction_type": "",
    "date": "",
    "time": "",
    "attendees": "",
    "topics": "",
    "materials": "",
}

INTERACTION_TYPES = {"Meeting", "Call", "Visit", "Other"}

app = FastAPI(title="AI Interaction Logger API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    text: str


def clean_response(content: str) -> str:
    content = content.strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return match.group(0) if match else content


def normalize_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = date_parser.parse(value, fuzzy=True)
        return parsed.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError):
        return ""


def normalize_time(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = date_parser.parse(value, fuzzy=True)
        return parsed.strftime("%H:%M")
    except (ValueError, TypeError, OverflowError):
        return ""


def normalize_payload(payload: Dict[str, str]) -> Dict[str, str]:
    normalized = EXPECTED_FIELDS.copy()
    for key in normalized:
        normalized[key] = str(payload.get(key, "") or "").strip()

    if normalized["interaction_type"] not in INTERACTION_TYPES:
        normalized["interaction_type"] = ""

    normalized["date"] = normalize_date(normalized["date"])
    normalized["time"] = normalize_time(normalized["time"])
    return normalized


def fallback_parse(text: str) -> Dict[str, str]:
    normalized = EXPECTED_FIELDS.copy()

    name_match = re.search(r"\b(?:Dr\.?|Doctor)\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?", text)
    if name_match:
        normalized["hcp_name"] = name_match.group(0).replace("Doctor", "Dr")

    lowered = text.lower()
    if "call" in lowered or "called" in lowered:
        normalized["interaction_type"] = "Call"
    elif "visit" in lowered or "visited" in lowered:
        normalized["interaction_type"] = "Visit"
    elif "meet" in lowered or "meeting" in lowered or "met " in lowered:
        normalized["interaction_type"] = "Meeting"
    else:
        normalized["interaction_type"] = "Other"

    try:
        parsed = date_parser.parse(text, fuzzy=True)
        normalized["date"] = parsed.strftime("%Y-%m-%d")
        if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", lowered) or re.search(r"\b\d{1,2}:\d{2}\b", lowered):
            normalized["time"] = parsed.strftime("%H:%M")
    except (ValueError, TypeError, OverflowError):
        pass

    topic_match = re.search(r"(?:discussed|about|regarding)\s+(.+)", text, re.IGNORECASE)
    if topic_match:
        normalized["topics"] = topic_match.group(1).strip().rstrip(".")

    return normalized


def parse_with_llm(text: str) -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return fallback_parse(text)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(clean_response(content))
    return normalize_payload(parsed)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/parse")
def parse_interaction(request: ParseRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    try:
        parsed = parse_with_llm(request.text)
        return normalize_payload(parsed)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Model returned invalid JSON.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to parse the interaction right now.",
        ) from exc
