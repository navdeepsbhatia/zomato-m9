"""Build the chat messages sent to Groq."""

from __future__ import annotations

import json
import math

import pandas as pd

from recommender.models import UserPreferences

CANDIDATE_FIELDS = (
    "name",
    "cuisines",
    "cost_for_two",
    "rating",
)
_MAX_CUISINES = 3
_MAX_NOTE_CHARS = 180


def build_messages(preferences: UserPreferences, candidates: pd.DataFrame) -> list[dict[str, str]]:
    """Return a system message and a user message for one shortlist.

    The user message carries preferences and the compact candidate fields only.
    """
    system = (
        "Return JSON only. Rank only the given restaurants and keep each exact name. "
        f"Return exactly {preferences.top_n} items. rank starts at 1. "
        "summary is one sentence. Each explanation is one sentence."
    )
    prefs: dict[str, object] = {
        "location": preferences.location,
        "budget": preferences.budget,
        "cuisine": preferences.cuisine or "any",
        "min_rating": preferences.min_rating,
        "top_n": preferences.top_n,
    }
    note = preferences.additional_preferences.strip()[:_MAX_NOTE_CHARS].rstrip()
    if note:
        prefs["additional_preferences"] = note
    visible = candidates.head(preferences.top_n)
    payload = {
        "preferences": prefs,
        "candidates": [_candidate_record(row) for row in visible.to_dict(orient="records")],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    ]


def _candidate_record(row: dict[str, object]) -> dict[str, object]:
    return {field: _field_value(field, row.get(field)) for field in CANDIDATE_FIELDS}


def _field_value(field: str, value: object) -> object:
    if field == "cuisines":
        return _cuisine_tokens(value)
    if field == "cost_for_two":
        return _optional_int(value)
    if field == "rating":
        return _optional_float(value)
    if _missing(value):
        return ""
    return str(value)


def _cuisine_tokens(value: object) -> list[str]:
    if isinstance(value, str):
        tokens = [part.strip() for part in value.split(",") if part.strip()]
        return tokens[:_MAX_CUISINES]
    if _missing(value):
        return []
    if isinstance(value, (list, tuple)):
        items = value
    elif hasattr(value, "tolist"):
        items = value.tolist()
    else:
        return []
    tokens = [str(item).strip() for item in items if str(item).strip()]
    return tokens[:_MAX_CUISINES]


def _optional_int(value: object) -> int | None:
    number = _optional_float(value)
    if number is None:
        return None
    return int(number)


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or _missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _missing(value: object) -> bool:
    if isinstance(value, (list, tuple, dict, str)):
        return False
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing)
