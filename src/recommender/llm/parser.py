"""Turn Groq's JSON into recommendations grounded in the shortlist."""

from __future__ import annotations

import json
import math

import pandas as pd

from recommender.models import Recommendation


class InvalidModelOutput(Exception):
    """The model response is not JSON or names none of the candidates."""


def parse_recommendations(
    content: str,
    candidates: pd.DataFrame,
    top_n: int,
) -> tuple[str, list[Recommendation]]:
    """Return the summary and up to ``top_n`` recommendations.

    Facts are copied from the candidate row. A partial list is filled from
    unused candidates in score order. Ranks are numbered from 1 in that order.
    """
    payload = _load_payload(content)
    summary = payload.get("summary")
    raw_items = payload.get("recommendations")
    if not isinstance(summary, str) or not isinstance(raw_items, list):
        raise InvalidModelOutput("Model JSON must include summary and a recommendations list.")
    if not raw_items:
        raise InvalidModelOutput("Model JSON recommendations list is empty.")

    frame = candidates.reset_index(drop=True)
    first_row = _first_row_for_name(frame)
    used_rows: set[int] = set()
    used_names: set[str] = set()
    items: list[Recommendation] = []

    for entry in raw_items:
        if len(items) >= top_n:
            break
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        row_number = first_row.get(name)
        if row_number is None or row_number in used_rows or name in used_names:
            continue
        used_rows.add(row_number)
        used_names.add(name)
        explanation = entry.get("explanation")
        items.append(
            _from_row(
                frame.iloc[row_number],
                rank=len(items) + 1,
                explanation=explanation if isinstance(explanation, str) else "",
            )
        )

    if not items:
        raise InvalidModelOutput("No recommendation name matched a candidate.")

    if len(items) < top_n:
        spare = [
            row_number
            for row_number in range(len(frame))
            if row_number not in used_rows and _row_name(frame.at[row_number, "name"]) not in used_names
        ]
        spare.sort(key=lambda row_number: _score(frame.iloc[row_number]), reverse=True)
        for row_number in spare:
            if len(items) >= top_n:
                break
            row = frame.iloc[row_number]
            used_names.add(_row_name(row["name"]))
            items.append(
                _from_row(
                    row,
                    rank=len(items) + 1,
                    explanation=_pad_explanation(row),
                )
            )

    return summary, items


def _load_payload(content: str) -> dict[str, object]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutput("Model response is not JSON.") from exc
    if not isinstance(payload, dict):
        raise InvalidModelOutput("Model JSON must be an object.")
    return payload


def _first_row_for_name(frame: pd.DataFrame) -> dict[str, int]:
    found: dict[str, int] = {}
    for row_number in range(len(frame)):
        found.setdefault(_row_name(frame.at[row_number, "name"]), row_number)
    return found


def _from_row(row: pd.Series, *, rank: int, explanation: str) -> Recommendation:
    return Recommendation(
        rank=rank,
        name=_row_name(row["name"]),
        cuisines=_cuisines_text(row.get("cuisines")),
        rating=_optional_float(row.get("rating")),
        cost_for_two=_optional_int(row.get("cost_for_two")),
        explanation=explanation,
        url=_text(row.get("url")),
    )


def _pad_explanation(row: pd.Series) -> str:
    name = _row_name(row["name"])
    cuisines = _cuisines_text(row.get("cuisines")) or "the listed cuisine"
    location = _text(row.get("location")) or "the matched area"
    rating = _optional_float(row.get("rating"))
    cost = _optional_int(row.get("cost_for_two"))
    rating_text = "unavailable" if rating is None else str(rating)
    cost_text = "unavailable" if cost is None else str(cost)
    return (
        f"{name} was added from the shortlist to complete the list. "
        f"It serves {cuisines} in {location}, with rating {rating_text} "
        f"and cost for two {cost_text}."
    )


def _score(row: pd.Series) -> float:
    if "score" not in row.index:
        return 0.0
    number = _optional_float(row.get("score"))
    return 0.0 if number is None else number


def _row_name(value: object) -> str:
    if _missing(value):
        return ""
    return str(value)


def _text(value: object) -> str:
    if _missing(value):
        return ""
    return str(value)


def _cuisines_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if _missing(value):
        return ""
    if isinstance(value, (list, tuple)):
        items = value
    elif hasattr(value, "tolist"):
        items = value.tolist()
    else:
        return str(value).strip()
    return ", ".join(str(item).strip() for item in items if str(item).strip())


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
