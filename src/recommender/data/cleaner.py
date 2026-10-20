"""Clean raw Zomato rows into the working restaurant table."""

from __future__ import annotations

import math

import pandas as pd

CLEANED_COLUMNS = [
    "name",
    "address",
    "location",
    "listed_in_city",
    "cuisines",
    "cost_for_two",
    "rating",
    "votes",
    "rest_type",
    "online_order",
    "book_table",
    "dish_liked",
    "url",
]

_DISH_LIKED_LIMIT = 200


def clean_restaurants(df: pd.DataFrame) -> pd.DataFrame:
    """Return cleaned restaurant rows, one per name and address.

    `phone`, `reviews_list`, and `menu_item` are ignored when present and are
    never part of the result.
    """
    records: list[dict[str, object]] = []
    for row in df.to_dict(orient="records"):
        name = _text(row.get("name"))
        if not name:
            continue
        records.append(
            {
                "name": name,
                "address": _text(row.get("address")),
                "location": _text(row.get("location")),
                "listed_in_city": _text(row.get("listed_in(city)")),
                "cuisines": _cuisines(row.get("cuisines")),
                "cost_for_two": _cost(row.get("approx_cost(for two people)")),
                "rating": _rating(row.get("rate")),
                "votes": _votes(row.get("votes")),
                "rest_type": _text(row.get("rest_type")),
                "online_order": row.get("online_order") == "Yes",
                "book_table": row.get("book_table") == "Yes",
                "dish_liked": _dish_liked(row.get("dish_liked")),
                "url": _text(row.get("url")),
            }
        )

    if not records:
        return pd.DataFrame(columns=CLEANED_COLUMNS)

    cleaned = pd.DataFrame.from_records(records, columns=CLEANED_COLUMNS)
    cleaned["cost_for_two"] = cleaned["cost_for_two"].astype("Int64")
    cleaned["rating"] = cleaned["rating"].astype("Float64")
    cleaned["votes"] = cleaned["votes"].astype("int64")
    cleaned = cleaned.sort_values("votes", ascending=False, kind="mergesort")
    cleaned = cleaned.drop_duplicates(subset=["name", "address"], keep="first")
    return cleaned.loc[:, CLEANED_COLUMNS].reset_index(drop=True)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return False
    if isinstance(value, (list, dict, tuple)):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing)


def _text(value: object) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip()


def _rating(value: object) -> float | None:
    if _is_missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text == "-" or text.upper() == "NEW":
        return None
    number = text.split("/", 1)[0].strip()
    try:
        return float(number)
    except ValueError:
        return None


def _cost(value: object) -> int | None:
    if isinstance(value, bool) or _is_missing(value):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _votes(value: object) -> int:
    parsed = _cost(value)
    return 0 if parsed is None else parsed


def _cuisines(value: object) -> list[str]:
    if _is_missing(value):
        return []
    if isinstance(value, list):
        tokens = value
    else:
        text = str(value).strip()
        if not text:
            return []
        tokens = text.split(",")
    return [str(token).strip() for token in tokens if str(token).strip()]


def _dish_liked(value: object) -> str:
    if _is_missing(value):
        return ""
    return str(value)[:_DISH_LIKED_LIMIT]
