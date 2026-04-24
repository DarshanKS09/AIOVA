import json
import os
import re
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Dict, Optional

from dateutil import parser as date_parser
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


SYSTEM_PROMPT = """You are an AI that updates structured CRM interaction data.

You will receive:

1. Current form state
2. User instruction

Your job:

* Identify if user wants to MODIFY existing data
* Return ONLY the fields that need to be updated

Rules:

* DO NOT return unchanged fields
* DO NOT return explanations
* Return ONLY valid JSON
* If user says 'remove', set value to empty string
* If user adds info, merge intelligently

Fields:

* hcp_name
* interaction_type
* date
* time
* attendees
* topics
* materials"""

DUPLICATE_CHECK_PROMPT = """You are an AI that detects duplicate CRM interaction records.

Compare the NEW entry with EXISTING entries.

Rules:

* If same doctor (or similar name) AND same date/time -> high chance duplicate
* If topics are similar -> increase confidence
* Allow fuzzy matching (Dr Mehta vs Dr. Mehta)

Return ONLY JSON:

{
  "is_duplicate": true,
  "confidence": 0,
  "matched_index": 0,
  "reason": "short explanation"
}"""

MERGE_PROMPT = """You are merging two CRM interaction records.

Rules:

* Keep the most complete data
* Combine attendees (remove duplicates)
* Combine materials
* Prefer latest time if conflict
* Do NOT lose information

Return ONLY merged JSON object."""

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
    current_state: Optional[Dict[str, str]] = None


class DuplicateCheckRequest(BaseModel):
    new_entry: Dict[str, str]
    existing_entries: list[Dict[str, str]]


class MergeRequest(BaseModel):
    existing: Dict[str, str]
    new: Dict[str, str]


class DuplicateCheckResult(BaseModel):
    is_duplicate: bool
    confidence: int
    matched_index: Optional[int]
    reason: str


def clean_response(content: str) -> str:
    content = content.strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return match.group(0) if match else content


def normalize_date(value: str) -> str:
    if not value:
        return ""

    relative_weekday = parse_relative_weekday(value)
    if relative_weekday:
        return relative_weekday

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


def normalize_hcp_name(value: str) -> str:
    if not value:
        return ""

    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = re.sub(r"^(doctor|dr\.?)\s+", "Dr ", cleaned, flags=re.IGNORECASE)

    parts = []
    for part in cleaned.split():
        if part.lower() == "dr":
            parts.append("Dr")
        else:
            parts.append(part.capitalize())

    return " ".join(parts)


def parse_relative_weekday(value: str) -> str:
    match = re.search(
        r"\b(this|next|last)\s+"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        return ""

    modifier = match.group(1).lower()
    weekday_name = match.group(2).lower()
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    today = datetime.now()
    current_weekday = today.weekday()
    target_weekday = weekday_map[weekday_name]

    if modifier == "this":
        start_of_week = today - timedelta(days=current_weekday)
        target_date = start_of_week + timedelta(days=target_weekday)
    elif modifier == "next":
        days_ahead = (target_weekday - current_weekday) % 7
        days_ahead = 7 if days_ahead == 0 else days_ahead
        target_date = today + timedelta(days=days_ahead)
    else:
        days_back = (current_weekday - target_weekday) % 7
        days_back = 7 if days_back == 0 else days_back
        target_date = today - timedelta(days=days_back)

    return target_date.strftime("%Y-%m-%d")


def normalize_person_name(title: str, name: str) -> str:
    normalized_name = " ".join(part.capitalize() for part in name.split() if part)
    normalized_title = title.strip().lower().rstrip(".")

    if normalized_title in {"dr", "doctor"}:
        return normalize_hcp_name(f"Dr {normalized_name}")
    if normalized_title == "mr":
        return f"Mr {normalized_name}".strip()
    if normalized_title == "mrs":
        return f"Mrs {normalized_name}".strip()
    if normalized_title == "ms":
        return f"Ms {normalized_name}".strip()

    return f"{normalized_title.capitalize()} {normalized_name}".strip()


def extract_people(text: str) -> list[str]:
    matches = re.finditer(
        r"\b(dr\.?|doctor|nurse|mr\.?|mrs\.?|ms\.?)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
        text,
        re.IGNORECASE,
    )
    people = []
    seen = set()
    stopwords = {
        "this",
        "next",
        "last",
        "i",
        "and",
        "at",
        "on",
        "by",
        "with",
        "today",
        "yesterday",
        "tomorrow",
        "regarding",
        "about",
        "discussed",
        "shared",
        "called",
        "met",
        "meeting",
        "call",
        "visit",
    }

    for match in matches:
        title = match.group(1)
        tokens = re.findall(r"[a-zA-Z]+", match.group(2))
        name_parts = []

        for token in tokens:
            if token.lower() in stopwords:
                break
            name_parts.append(token)
            if len(name_parts) == 2:
                break

        if not name_parts:
            continue

        person = normalize_person_name(title, " ".join(name_parts))
        person_key = person.lower()
        if person_key not in seen:
            people.append(person)
            seen.add(person_key)

    return people


def extract_hcp_name(text: str) -> str:
    people = extract_people(text)
    return people[0] if people else ""


def normalize_payload(payload: Dict[str, str]) -> Dict[str, str]:
    normalized = EXPECTED_FIELDS.copy()
    for key in normalized:
        normalized[key] = str(payload.get(key, "") or "").strip()

    normalized["hcp_name"] = normalize_hcp_name(normalized["hcp_name"])

    if normalized["interaction_type"] not in INTERACTION_TYPES:
        normalized["interaction_type"] = ""

    normalized["date"] = normalize_date(normalized["date"])
    normalized["time"] = normalize_time(normalized["time"])
    return normalized


def normalize_partial_payload(payload: Dict[str, str]) -> Dict[str, str]:
    normalized = {}
    for key, value in payload.items():
        if key not in EXPECTED_FIELDS:
            continue

        normalized_value = str(value or "").strip()
        if key == "hcp_name":
            normalized_value = normalize_hcp_name(normalized_value)
        elif key == "interaction_type":
            normalized_value = normalized_value.title()
            if normalized_value not in INTERACTION_TYPES:
                normalized_value = ""
        elif key == "date":
            normalized_value = normalize_date(normalized_value)
        elif key == "time":
            normalized_value = normalize_time(normalized_value)

        normalized[key] = normalized_value

    return normalized


def diff_payload(current_state: Dict[str, str], next_state: Dict[str, str]) -> Dict[str, str]:
    updates = {}
    for key, value in next_state.items():
        if key in EXPECTED_FIELDS and current_state.get(key, "") != value:
            updates[key] = value
    return updates


def split_items(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r",|;|\band\b", value, flags=re.IGNORECASE) if item.strip()]


def normalize_text_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", value.lower()).strip()


def tokenize_text(value: str) -> set[str]:
    stopwords = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "for",
        "with",
        "on",
        "at",
        "in",
        "about",
        "regarding",
        "related",
    }
    return {
        token
        for token in normalize_text_for_match(value).split()
        if token and token not in stopwords
    }


def similarity_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, normalize_text_for_match(left), normalize_text_for_match(right)).ratio()


def topic_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0

    left_tokens = tokenize_text(left)
    right_tokens = tokenize_text(right)
    if not left_tokens or not right_tokens:
        return similarity_score(left, right)

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    overlap = intersection / union if union else 0.0
    return max(overlap, similarity_score(left, right))


def time_difference_minutes(left: str, right: str) -> Optional[int]:
    if not left or not right:
        return None

    try:
        left_time = date_parser.parse(left)
        right_time = date_parser.parse(right)
    except (ValueError, TypeError, OverflowError):
        return None

    return abs(int((left_time - right_time).total_seconds() // 60))


def merge_text_values(current_value: str, new_value: str) -> str:
    if not current_value:
        return new_value

    current_items = split_items(current_value)
    new_items = split_items(new_value)
    merged = current_items[:]
    seen = {item.lower() for item in merged}

    for item in new_items:
        if item.lower() not in seen:
            merged.append(item)
            seen.add(item.lower())

    return ", ".join(merged)


def combine_field_values(existing_value: str, new_value: str) -> str:
    existing_value = (existing_value or "").strip()
    new_value = (new_value or "").strip()
    if not existing_value:
        return new_value
    if not new_value:
        return existing_value
    if existing_value.lower() == new_value.lower():
        return existing_value

    if len(new_value) > len(existing_value):
        return new_value
    return existing_value


def heuristic_duplicate_check(
    new_entry: Dict[str, str],
    existing_entries: list[Dict[str, str]],
) -> DuplicateCheckResult:
    best_index = None
    best_score = -1
    best_reason = "No close interaction found."

    for index, entry in enumerate(existing_entries):
        normalized_existing = normalize_payload(entry)
        score = 0
        reasons = []

        hcp_similarity = similarity_score(new_entry["hcp_name"], normalized_existing["hcp_name"])
        if hcp_similarity >= 0.9:
            score += 35
            reasons.append("doctor name is almost identical")
        elif hcp_similarity >= 0.75:
            score += 25
            reasons.append("doctor name is similar")
        elif new_entry["hcp_name"] and normalized_existing["hcp_name"]:
            reasons.append("doctor name is different")

        if new_entry["date"] and normalized_existing["date"]:
            if new_entry["date"] == normalized_existing["date"]:
                score += 20
                reasons.append("interaction date matches")

        minutes_apart = time_difference_minutes(new_entry["time"], normalized_existing["time"])
        if minutes_apart is not None:
            if minutes_apart <= 10:
                score += 20
                reasons.append("interaction time is very close")
            elif minutes_apart <= 30:
                score += 10
                reasons.append("interaction time is somewhat close")

        topics_score = topic_similarity(new_entry["topics"], normalized_existing["topics"])
        if topics_score >= 0.65:
            score += 15
            reasons.append("topics are similar")
        elif topics_score >= 0.4:
            score += 8
            reasons.append("topics overlap")

        if score > best_score:
            best_score = score
            best_index = index
            best_reason = ", ".join(reasons) if reasons else "No close interaction found."

    confidence = max(0, min(100, best_score if best_score > 0 else 0))
    matched_entry = (
        normalize_payload(existing_entries[best_index])
        if best_index is not None and 0 <= best_index < len(existing_entries)
        else EXPECTED_FIELDS.copy()
    )
    name_anchor = similarity_score(new_entry["hcp_name"], matched_entry["hcp_name"]) >= 0.75
    topics_anchor = topic_similarity(new_entry["topics"], matched_entry["topics"]) >= 0.4
    time_anchor = (
        (time_difference_minutes(new_entry["time"], matched_entry["time"]) or 10**9) <= 30
        if new_entry["time"] and matched_entry["time"]
        else False
    )
    is_duplicate = confidence >= 60 and name_anchor and (time_anchor or topics_anchor)
    return DuplicateCheckResult(
        is_duplicate=is_duplicate,
        confidence=confidence,
        matched_index=best_index if is_duplicate else None,
        reason=best_reason,
    )


def heuristic_merge_records(existing: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    merged = {}
    for field in EXPECTED_FIELDS:
        existing_value = existing.get(field, "")
        new_value = new.get(field, "")

        if field in {"attendees", "materials", "topics"}:
            merged[field] = merge_text_values(existing_value, new_value)
        elif field == "time":
            merged[field] = max(existing_value, new_value) if existing_value and new_value else existing_value or new_value
        else:
            merged[field] = combine_field_values(existing_value, new_value)

    return normalize_payload(merged)


def extract_named_value(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")
    return ""


def clean_topic_value(value: str) -> str:
    return re.sub(r"^(topics?\s+(?:related\s+to|about|on)\s+)", "", value, flags=re.IGNORECASE).strip()


def clean_materials_value(value: str) -> str:
    cleaned = re.sub(
        r"^(materials?\s+(?:related\s+to|about|on)\s+)",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned.rstrip(".")


def split_topics_and_materials(text: str) -> tuple[str, str]:
    topic_match = re.search(
        r"(?:to\s+discuss|discuss|discussed|about|regarding)\s+(.+?)(?=\s+(?:and\s+)?(?:shared|sent|provided)\b|$)",
        text,
        re.IGNORECASE,
    )
    materials_match = re.search(
        r"(?:shared|sent|provided)\s+(.+)",
        text,
        re.IGNORECASE,
    )

    topics = clean_topic_value(topic_match.group(1)) if topic_match else ""
    materials = clean_materials_value(materials_match.group(1)) if materials_match else ""
    return topics, materials


def fallback_parse(text: str) -> Dict[str, str]:
    normalized = EXPECTED_FIELDS.copy()

    people = extract_people(text)
    normalized["hcp_name"] = people[0] if people else ""
    additional_people = [person for person in people if person != normalized["hcp_name"]]
    if additional_people:
        normalized["attendees"] = ", ".join(additional_people)

    lowered = text.lower()
    if "call" in lowered or "called" in lowered:
        normalized["interaction_type"] = "Call"
    elif "visit" in lowered or "visited" in lowered:
        normalized["interaction_type"] = "Visit"
    elif "meet" in lowered or "meeting" in lowered or "met " in lowered:
        normalized["interaction_type"] = "Meeting"
    else:
        normalized["interaction_type"] = "Other"

    relative_weekday = parse_relative_weekday(text)
    if relative_weekday:
        normalized["date"] = relative_weekday
        normalized["time"] = normalize_time(text)
    else:
        try:
            parsed = date_parser.parse(text, fuzzy=True)
            normalized["date"] = parsed.strftime("%Y-%m-%d")
            if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", lowered) or re.search(r"\b\d{1,2}:\d{2}\b", lowered):
                normalized["time"] = parsed.strftime("%H:%M")
        except (ValueError, TypeError, OverflowError):
            pass

    topics, materials = split_topics_and_materials(text)
    if topics:
        normalized["topics"] = topics
    if materials:
        normalized["materials"] = materials

    return normalized


def fallback_edit(text: str, current_state: Dict[str, str]) -> Dict[str, str]:
    updates = {}
    lowered = text.lower()

    remove_patterns = {
        "hcp_name": [r"\bremove\b.*\b(?:hcp|name|doctor|dr)\b", r"\bclear\b.*\b(?:hcp|name)\b"],
        "interaction_type": [r"\bremove\b.*\b(?:type|interaction)\b", r"\bclear\b.*\b(?:type|interaction)\b"],
        "date": [r"\bremove\b.*\bdate\b", r"\bclear\b.*\bdate\b"],
        "time": [r"\bremove\b.*\btime\b", r"\bclear\b.*\btime\b"],
        "attendees": [r"\bremove\b.*\battendees?\b", r"\bclear\b.*\battendees?\b"],
        "topics": [r"\bremove\b.*\btopics?\b", r"\bclear\b.*\btopics?\b"],
        "materials": [r"\bremove\b.*\bmaterials?\b", r"\bclear\b.*\bmaterials?\b"],
    }
    for field, patterns in remove_patterns.items():
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            updates[field] = ""

    interaction_type_match = re.search(r"\b(meeting|call|visit|other)\b", lowered)
    if interaction_type_match and (
        "actually" in lowered
        or "instead" in lowered
        or "not a" in lowered
        or "it was" in lowered
        or "change" in lowered
        or "update" in lowered
    ):
        updates["interaction_type"] = interaction_type_match.group(1).title()

    time_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+time\s+(?:to\s+)?(.+)",
            r"\btime\s+(?:to\s+)?(.+)",
        ],
    )
    if time_value:
        updates["time"] = time_value

    date_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+date\s+(?:to\s+)?(.+)",
            r"\bdate\s+(?:to\s+)?(.+)",
        ],
    )
    if date_value:
        updates["date"] = date_value

    hcp_name_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+(?:hcp name|name)\s+(?:to\s+)?(.+)",
            r"(?:change|update|set)\s+doctor\s+(?:to\s+)?(.+)",
        ],
    )
    if hcp_name_value:
        updates["hcp_name"] = hcp_name_value

    attendees_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+attendees?\s+(?:to\s+)?(.+)",
            r"(?:add|include)\s+(.+?)\s+to\s+attendees?",
        ],
    )
    mentioned_people = extract_people(text)
    current_hcp = current_state.get("hcp_name", "").strip().lower()
    mentioned_attendees = [
        person for person in mentioned_people if person.strip().lower() != current_hcp
    ]

    is_attendee_replace = bool(
        re.search(r"\b(change|update|set)\s+attendees?\b", lowered)
    )
    is_attendee_add = bool(
        re.search(r"\b(add|include|also|along with|met)\b", lowered)
    )

    if not attendees_value and mentioned_attendees and is_attendee_add:
        attendees_value = ", ".join(mentioned_attendees)
    if attendees_value:
        attendees_value = ", ".join(
            person for person in split_items(attendees_value) if person.lower() != current_hcp
        )
        if not attendees_value:
            return normalize_partial_payload(updates)

        if is_attendee_replace:
            updates["attendees"] = attendees_value
        elif is_attendee_add or mentioned_attendees:
            updates["attendees"] = merge_text_values(current_state.get("attendees", ""), attendees_value)
        else:
            updates["attendees"] = attendees_value

    topics_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+topics?\s+(?:to\s+)?(.+)",
            r"(?:add|include)\s+(.+?)\s+to\s+topics?",
            r"(?:discuss|discussed|discussing)\s+(.+)",
            r"topics?\s+(?:related\s+to|about|on)\s+(.+)",
            r"(?:discussed|about|regarding)\s+(.+)",
        ],
    )
    if topics_value:
        topics_value = clean_topic_value(topics_value)
        if re.search(r"\b(add|include)\b", lowered):
            updates["topics"] = merge_text_values(current_state.get("topics", ""), topics_value)
        elif re.search(r"\b(discussed|about|regarding)\b", lowered) and current_state.get("topics", ""):
            updates["topics"] = merge_text_values(current_state.get("topics", ""), topics_value)
        else:
            updates["topics"] = topics_value

    materials_value = extract_named_value(
        text,
        [
            r"(?:change|update|set)\s+materials?\s+(?:to\s+)?(.+)",
            r"(?:add|include)\s+(.+?)\s+to\s+materials?",
            r"(?:shared|sent|provided)\s+(.+)",
        ],
    )
    if materials_value:
        if re.search(r"\b(add|include|shared|sent|provided)\b", lowered):
            updates["materials"] = merge_text_values(current_state.get("materials", ""), materials_value)
        else:
            updates["materials"] = materials_value

    return normalize_partial_payload(updates)


def parse_with_llm(text: str, current_state: Dict[str, str]) -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        if any(current_state.values()):
            return diff_payload(
                current_state,
                {**current_state, **fallback_edit(text, current_state)},
            )

        initial_parse = normalize_payload(fallback_parse(text))
        return diff_payload(current_state, initial_parse)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_state": current_state,
                        "instruction": text,
                    }
                ),
            },
        ],
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(clean_response(content))
    normalized_updates = normalize_partial_payload(parsed)
    next_state = {**current_state, **normalized_updates}
    return diff_payload(current_state, next_state)


def duplicate_check_with_llm(
    new_entry: Dict[str, str],
    existing_entries: list[Dict[str, str]],
) -> DuplicateCheckResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return heuristic_duplicate_check(new_entry, existing_entries)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DUPLICATE_CHECK_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "new_entry": new_entry,
                        "existing_entries": existing_entries,
                    }
                ),
            },
        ],
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(clean_response(content))
    return DuplicateCheckResult(
        is_duplicate=bool(parsed.get("is_duplicate", False)),
        confidence=max(0, min(100, int(parsed.get("confidence", 0) or 0))),
        matched_index=parsed.get("matched_index"),
        reason=str(parsed.get("reason", "") or "").strip() or "Potential duplicate detected.",
    )


def merge_records_with_llm(existing: Dict[str, str], new: Dict[str, str]) -> Dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return heuristic_merge_records(existing, new)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": MERGE_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "existing": existing,
                        "new": new,
                    }
                ),
            },
        ],
    )

    content = response.choices[0].message.content or "{}"
    parsed = json.loads(clean_response(content))
    normalized = normalize_payload(parsed)
    return heuristic_merge_records(existing, normalized)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/parse")
def parse_interaction(request: ParseRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required.")

    try:
        current_state = normalize_payload(request.current_state or {})
        parsed = parse_with_llm(request.text, current_state)
        return parsed
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Model returned invalid JSON.") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to parse the interaction right now.",
        ) from exc


@app.post("/check-duplicate", response_model=DuplicateCheckResult)
def check_duplicate(request: DuplicateCheckRequest):
    try:
        new_entry = normalize_payload(request.new_entry or {})
        existing_entries = [normalize_payload(entry) for entry in request.existing_entries or []]
        return duplicate_check_with_llm(new_entry, existing_entries)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Duplicate check returned invalid JSON.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to check duplicates right now.") from exc


@app.post("/merge-entry")
def merge_entry(request: MergeRequest):
    try:
        existing = normalize_payload(request.existing or {})
        new = normalize_payload(request.new or {})
        return merge_records_with_llm(existing, new)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Merge returned invalid JSON.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to merge entries right now.") from exc
