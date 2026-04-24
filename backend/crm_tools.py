import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import parser as date_parser

try:
    from backend.database import (
        delete_interaction,
        get_interaction,
        insert_interaction,
        list_interactions,
        update_interaction,
    )
except ImportError:  # pragma: no cover
    from database import delete_interaction, get_interaction, insert_interaction, list_interactions, update_interaction

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None


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


def get_reference_now() -> datetime:
    timezone_name = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    try:
        return datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return datetime.now()


def parse_relative_day(value: str) -> str:
    lowered = value.lower()
    now = get_reference_now()

    if re.search(r"\byesterday\b", lowered):
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r"\btoday\b", lowered):
        return now.strftime("%Y-%m-%d")
    if re.search(r"\btomorrow\b", lowered):
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    return ""


def normalize_date(value: str) -> str:
    if not value:
        return ""

    relative_day = parse_relative_day(value)
    if relative_day:
        return relative_day

    relative_weekday = parse_relative_weekday(value)
    if relative_weekday:
        return relative_weekday

    try:
        return date_parser.parse(value, fuzzy=True).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OverflowError):
        return ""


def normalize_time(value: str) -> str:
    if not value:
        return ""
    try:
        return date_parser.parse(value, fuzzy=True).strftime("%H:%M")
    except (ValueError, TypeError, OverflowError):
        return ""


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
    today = get_reference_now()
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


def normalize_person_name(title: str, name: str) -> str:
    normalized_name = " ".join(part.capitalize() for part in name.split() if part)
    normalized_title = title.strip().lower().rstrip(".")

    if normalized_title in {"dr", "doctor"}:
        return normalize_hcp_name(f"Dr {normalized_name}")
    if normalized_title == "mr":
        return f"Mr {normalized_name}"
    if normalized_title == "mrs":
        return f"Mrs {normalized_name}"
    if normalized_title == "ms":
        return f"Ms {normalized_name}"
    return f"{normalized_title.capitalize()} {normalized_name}".strip()


def normalize_plain_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split() if part).strip()


def extract_people(text: str) -> list[str]:
    matches = re.finditer(
        r"\b(dr\.?|doctor|nurse|mr\.?|mrs\.?|ms\.?)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
        text,
        re.IGNORECASE,
    )
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
        "attended",
        "present",
        "meeting",
        "call",
        "visit",
    }
    people = []
    seen = set()
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
        key = person.lower()
        if key not in seen:
            people.append(person)
            seen.add(key)
    return people


def extract_attendee_mentions(text: str, current_state: dict[str, str]) -> list[str]:
    attendees = extract_people(text)
    current_hcp = current_state.get("hcp_name", "").strip().lower()
    filtered = [person for person in attendees if person.strip().lower() != current_hcp]
    if filtered:
        return filtered

    bare_name_match = re.search(
        r"\b(?:also|add|include|and)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s+"
        r"(?:attended|was present|present|joined|came)\b",
        text,
        re.IGNORECASE,
    )
    if bare_name_match:
        plain_name = normalize_plain_name(bare_name_match.group(1))
        if plain_name and plain_name.lower() != current_hcp:
            return [plain_name]
    return []


def normalize_payload(payload: dict[str, Any]) -> dict[str, str]:
    normalized = EXPECTED_FIELDS.copy()
    for key in normalized:
        normalized[key] = str(payload.get(key, "") or "").strip()
    normalized["hcp_name"] = normalize_hcp_name(normalized["hcp_name"])
    normalized["date"] = normalize_date(normalized["date"])
    normalized["time"] = normalize_time(normalized["time"])
    if normalized["interaction_type"] not in INTERACTION_TYPES:
        normalized["interaction_type"] = ""
    return normalized


def normalize_text_for_match(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", value.lower()).strip()


def split_items(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r",|;|\band\b", value, flags=re.IGNORECASE) if item.strip()]


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
    materials_match = re.search(r"(?:shared|sent|provided)\s+(.+)", text, re.IGNORECASE)
    topics = clean_topic_value(topic_match.group(1)) if topic_match else ""
    materials = clean_materials_value(materials_match.group(1)) if materials_match else ""
    return topics, materials


def fallback_parse(text: str) -> dict[str, str]:
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

    relative_day = parse_relative_day(text)
    relative_weekday = parse_relative_weekday(text)
    if relative_day:
        normalized["date"] = relative_day
        normalized["time"] = normalize_time(text)
    elif relative_weekday:
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


def extract_named_value(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")
    return ""


def fallback_edit(text: str, current_state: dict[str, str]) -> dict[str, str]:
    updates: dict[str, str] = {}
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
    if interaction_type_match and any(token in lowered for token in ["actually", "instead", "not a", "it was", "change", "update"]):
        updates["interaction_type"] = interaction_type_match.group(1).title()

    time_value = extract_named_value(text, [r"(?:change|update|set)\s+time\s+(?:to\s+)?(.+)", r"\btime\s+(?:to\s+)?(.+)"])
    if time_value:
        updates["time"] = time_value

    date_value = extract_named_value(text, [r"(?:change|update|set)\s+date\s+(?:to\s+)?(.+)", r"\bdate\s+(?:to\s+)?(.+)"])
    if date_value:
        updates["date"] = date_value

    hcp_name_value = extract_named_value(
        text,
        [r"(?:change|update|set)\s+(?:hcp name|name)\s+(?:to\s+)?(.+)", r"(?:change|update|set)\s+doctor\s+(?:to\s+)?(.+)"],
    )
    if hcp_name_value:
        updates["hcp_name"] = hcp_name_value

    attendees_value = extract_named_value(
        text,
        [r"(?:change|update|set)\s+attendees?\s+(?:to\s+)?(.+)", r"(?:add|include)\s+(.+?)\s+to\s+attendees?"],
    )
    mentioned_attendees = extract_attendee_mentions(text, current_state)
    is_attendee_replace = bool(re.search(r"\b(change|update|set)\s+attendees?\b", lowered))
    is_attendee_add = bool(re.search(r"\b(add|include|also|along with|met|attended|present|joined)\b", lowered))
    if not attendees_value and mentioned_attendees and is_attendee_add:
        attendees_value = ", ".join(mentioned_attendees)
    if attendees_value:
        current_hcp = current_state.get("hcp_name", "").strip().lower()
        attendees_value = ", ".join(
            person for person in split_items(attendees_value) if person.lower() != current_hcp
        )
        if attendees_value:
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
        materials_value = clean_materials_value(materials_value)
        if re.search(r"\b(add|include|shared|sent|provided)\b", lowered):
            updates["materials"] = merge_text_values(current_state.get("materials", ""), materials_value)
        else:
            updates["materials"] = materials_value

    merged = normalize_payload({**current_state, **updates})
    return {key: value for key, value in merged.items() if current_state.get(key, "") != value}


def tokenize_text(value: str) -> set[str]:
    stopwords = {"the", "a", "an", "and", "or", "to", "of", "for", "with", "on", "at", "in", "about", "regarding", "related"}
    return {token for token in normalize_text_for_match(value).split() if token and token not in stopwords}


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


def time_difference_minutes(left: str, right: str) -> int | None:
    if not left or not right:
        return None
    try:
        left_time = date_parser.parse(left)
        right_time = date_parser.parse(right)
    except (ValueError, TypeError, OverflowError):
        return None
    return abs(int((left_time - right_time).total_seconds() // 60))


def heuristic_duplicate_check(new_entry: dict[str, str], existing_entries: list[dict[str, Any]]) -> dict[str, Any]:
    best_index = None
    best_score = -1
    best_reason = "No close interaction found."

    for index, entry in enumerate(existing_entries):
        normalized_existing = normalize_payload(entry)
        score = 0
        reasons = []
        hcp_similarity = similarity_score(new_entry["hcp_name"], normalized_existing["hcp_name"])
        if hcp_similarity >= 0.9:
            score += 40
            reasons.append("doctor name is almost identical")
        elif hcp_similarity >= 0.75:
            score += 30
            reasons.append("doctor name is similar")

        if new_entry["date"] and normalized_existing["date"] and new_entry["date"] == normalized_existing["date"]:
            score += 25
            reasons.append("interaction date matches")

        minutes_apart = time_difference_minutes(new_entry["time"], normalized_existing["time"])
        if minutes_apart is not None:
            if minutes_apart <= 10:
                score += 20
                reasons.append("interaction time is very close")
            elif minutes_apart <= 30:
                score += 15
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

    if best_index is None:
        return {"is_duplicate": False, "confidence": 0, "matched_record": None, "reason": "No saved interactions found."}

    matched_record = normalize_with_metadata(existing_entries[best_index])
    confidence = max(0, min(100, best_score))
    name_anchor = similarity_score(new_entry["hcp_name"], matched_record["hcp_name"]) >= 0.75
    date_anchor = bool(new_entry["date"] and matched_record["date"] and new_entry["date"] == matched_record["date"])
    topics_anchor = topic_similarity(new_entry["topics"], matched_record["topics"]) >= 0.4
    time_anchor = (
        (time_difference_minutes(new_entry["time"], matched_record["time"]) or 10**9) <= 30
        if new_entry["time"] and matched_record["time"]
        else False
    )
    is_duplicate = name_anchor and date_anchor and (time_anchor or topics_anchor)
    if is_duplicate and confidence < 60:
        confidence = 60
    return {
        "is_duplicate": is_duplicate,
        "confidence": confidence,
        "matched_record": matched_record if is_duplicate else None,
        "reason": best_reason,
    }


def combine_field_values(existing_value: str, new_value: str) -> str:
    existing_value = (existing_value or "").strip()
    new_value = (new_value or "").strip()
    if not existing_value:
        return new_value
    if not new_value:
        return existing_value
    if existing_value.lower() == new_value.lower():
        return existing_value
    return new_value if len(new_value) > len(existing_value) else existing_value


def normalize_with_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_payload(entry)
    return {
        **normalized,
        "id": entry.get("id"),
        "sentiment": str(entry.get("sentiment", "") or "").strip(),
        "outcomes": str(entry.get("outcomes", "") or "").strip(),
        "follow_up_actions": str(entry.get("follow_up_actions", "") or "").strip(),
    }


def heuristic_merge_records(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    existing_payload = normalize_with_metadata(existing)
    new_payload = normalize_with_metadata(new)
    merged = {
        "id": existing_payload.get("id"),
        "hcp_name": existing_payload["hcp_name"] or new_payload["hcp_name"],
        "interaction_type": new_payload["interaction_type"] or existing_payload["interaction_type"],
        "date": new_payload["date"] or existing_payload["date"],
        "time": max(existing_payload["time"], new_payload["time"]) if existing_payload["time"] and new_payload["time"] else existing_payload["time"] or new_payload["time"],
        "attendees": merge_text_values(existing_payload["attendees"], new_payload["attendees"]),
        "topics": merge_text_values(existing_payload["topics"], new_payload["topics"]),
        "materials": merge_text_values(existing_payload["materials"], new_payload["materials"]),
        "sentiment": combine_field_values(existing_payload.get("sentiment", ""), new_payload.get("sentiment", "")),
        "outcomes": combine_field_values(existing_payload.get("outcomes", ""), new_payload.get("outcomes", "")),
        "follow_up_actions": merge_text_values(existing_payload.get("follow_up_actions", ""), new_payload.get("follow_up_actions", "")),
    }
    return merged


def heuristic_follow_up(entry: dict[str, Any]) -> dict[str, str]:
    topics = str(entry.get("topics", "") or "").strip()
    interaction_type = str(entry.get("interaction_type", "") or "").strip()
    hcp_name = str(entry.get("hcp_name", "") or "").strip()
    date = str(entry.get("date", "") or "").strip()
    time = str(entry.get("time", "") or "").strip()
    lowered = topics.lower()

    has_context = any([topics, interaction_type, hcp_name, date, time])
    if not has_context:
        return {
            "sentiment": "",
            "outcomes": "",
            "follow_up_actions": "",
            "message": "Insufficient data to suggest follow-up.",
        }

    sentiment = "Neutral"
    if any(token in lowered for token in ["positive", "interested", "good", "strong", "supportive"]):
        sentiment = "Positive"
    elif any(token in lowered for token in ["concern", "risk", "issue", "negative", "problem"]):
        sentiment = "Negative"

    follow_up_steps = [
        "Send a follow-up summary and confirm next steps.",
        "Schedule the next touchpoint and confirm availability.",
    ]
    outcomes = "Follow-up pending."
    if "pricing" in lowered:
        follow_up_steps = [
            "Share a pricing summary tailored to the discussion.",
            "Confirm any budget questions or approval blockers.",
            "Schedule a short follow-up call to review pricing options.",
        ]
        outcomes = "Pricing discussion captured."
    elif "efficacy" in lowered or "clinical" in lowered:
        follow_up_steps = [
            "Send the most relevant clinical evidence discussed.",
            "Offer a scientific follow-up meeting for deeper review.",
            "Capture any unanswered efficacy questions for the next call.",
        ]
        outcomes = "Clinical discussion captured."
    elif topics:
        follow_up_steps = [
            f"Send a recap covering {topics}.",
            "Confirm whether any supporting material should be shared next.",
            "Set a follow-up check-in to continue the discussion.",
        ]
        outcomes = f"Discussed {topics}."

    context_bits = [bit for bit in [hcp_name, interaction_type, date, time] if bit]
    context_line = f" for {', '.join(context_bits)}" if context_bits else ""
    message = "\n".join(f"- {step}" for step in follow_up_steps[:3])

    return {
        "sentiment": sentiment,
        "outcomes": outcomes,
        "follow_up_actions": "; ".join(follow_up_steps[:3]),
        "message": f"Suggested follow-up{context_line}:\n{message}",
    }


def llm_extract(text: str, current_state: dict[str, str] | None = None) -> dict[str, str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or ChatOpenAI is None:
        return None

    model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), api_key=api_key, temperature=0)
    if current_state and any(current_state.values()):
        system_prompt = (
            "Update structured CRM interaction data. Return only valid JSON with only changed fields. "
            "Use fields hcp_name, interaction_type, date, time, attendees, topics, materials."
        )
        user_content = json.dumps({"current_state": current_state, "instruction": text})
    else:
        system_prompt = (
            "Extract structured CRM interaction data from the input. Return only valid JSON using fields "
            "hcp_name, interaction_type, date, time, attendees, topics, materials."
        )
        user_content = text

    try:
        response = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        )
        content = getattr(response, "content", "") or "{}"
        parsed = json.loads(re.search(r"\{.*\}", content, re.DOTALL).group(0))
        if current_state and any(current_state.values()):
            updated = normalize_payload({**current_state, **parsed})
            return {key: value for key, value in updated.items() if current_state.get(key, "") != value}
        return normalize_payload(parsed)
    except Exception:
        return None


@dataclass
class LogInteractionTool:
    name: str = "LogInteractionTool"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = payload.get("operation", "extract")
        if operation == "list":
            return {"entries": list_interactions()}

        if operation == "load":
            entry_id = payload.get("entry_id")
            if entry_id in (None, ""):
                raise ValueError("Entry ID is required.")
            entry = get_interaction(entry_id)
            if entry is None:
                raise ValueError("Saved interaction not found.")
            return {"entry": entry}

        if operation == "save":
            entry = {
                **normalize_payload(payload.get("entry", {})),
                "sentiment": str(payload.get("entry", {}).get("sentiment", "") or "").strip(),
                "outcomes": str(payload.get("entry", {}).get("outcomes", "") or "").strip(),
                "follow_up_actions": str(payload.get("entry", {}).get("follow_up_actions", "") or "").strip(),
            }
            saved_entry = insert_interaction(entry)
            return {"entry": saved_entry, "entries": list_interactions()}

        if operation == "update":
            entry_id = payload.get("entry_id")
            if entry_id in (None, ""):
                raise ValueError("Entry ID is required.")
            entry = {
                **normalize_payload(payload.get("entry", {})),
                "sentiment": str(payload.get("entry", {}).get("sentiment", "") or "").strip(),
                "outcomes": str(payload.get("entry", {}).get("outcomes", "") or "").strip(),
                "follow_up_actions": str(payload.get("entry", {}).get("follow_up_actions", "") or "").strip(),
            }
            updated_entry = update_interaction(entry_id, entry)
            return {"entry": updated_entry, "entries": list_interactions()}

        if operation == "delete":
            entry_id = payload.get("entry_id")
            if entry_id in (None, ""):
                raise ValueError("Entry ID is required.")
            was_deleted = delete_interaction(entry_id)
            if not was_deleted:
                raise ValueError("Saved interaction not found.")
            return {"deleted": True, "entries": list_interactions()}

        text = str(payload.get("text", "") or "")
        extracted = llm_extract(text)
        if extracted is None:
            extracted = fallback_parse(text)
        return {"form_data": extracted}


@dataclass
class EditInteractionTool:
    name: str = "EditInteractionTool"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        instruction = str(payload.get("instruction", "") or "")
        current_state = normalize_payload(payload.get("current_state", {}) or {})
        extracted = llm_extract(instruction, current_state)
        if extracted is None:
            extracted = fallback_edit(instruction, current_state)
        updated = normalize_payload({**current_state, **extracted})
        return {"form_data": updated}


@dataclass
class DuplicateCheckTool:
    name: str = "DuplicateCheckTool"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        entry = normalize_payload(payload.get("entry", {}) or {})
        existing_entries = list_interactions()
        return heuristic_duplicate_check(entry, existing_entries)


@dataclass
class MergeInteractionTool:
    name: str = "MergeInteractionTool"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        existing_id = payload.get("existing_id")
        if existing_id in (None, ""):
            raise ValueError("Existing interaction ID is required.")
        existing = get_interaction(existing_id)
        if existing is None:
            raise ValueError("Existing interaction not found.")
        merged = heuristic_merge_records(existing, payload.get("new_entry", {}) or {})
        updated = update_interaction(existing_id, merged)
        return {"entry": updated, "entries": list_interactions()}


@dataclass
class FollowUpSuggestionTool:
    name: str = "FollowUpSuggestionTool"

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        entry = payload.get("entry", {}) or {}
        return heuristic_follow_up(entry)


def build_tool_registry() -> dict[str, Any]:
    tools = [
        LogInteractionTool(),
        EditInteractionTool(),
        DuplicateCheckTool(),
        MergeInteractionTool(),
        FollowUpSuggestionTool(),
    ]
    return {tool.name: tool for tool in tools}
