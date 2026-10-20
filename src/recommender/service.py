"""One recommendation request: shortlist, Groq ranking, or fallback."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
from openai import OpenAIError

from recommender.config import Settings, load_settings
from recommender.data.loader import load_processed_table
from recommender.filtering.candidates import shortlist
from recommender.llm.client import LLMClient, completion_token_budget
from recommender.llm.parser import InvalidModelOutput, parse_recommendations
from recommender.llm.prompt import build_messages
from recommender.models import Recommendation, RecommendationResult, UserPreferences

TableLoader = Callable[[Settings], pd.DataFrame]


class RecommendationService:
    """Preferences in, a `RecommendationResult` out."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: LLMClient | None = None,
        load_table: TableLoader | None = None,
    ) -> None:
        self._settings = load_settings() if settings is None else settings
        self._client = client if client is not None else LLMClient(self._settings)
        self._load_table = load_table if load_table is not None else load_processed_table

    def location_choices(self) -> list[str]:
        """Return the sorted neighborhood names present in the restaurant table."""
        table = self._load_table(self._settings)
        names = {_text(value).strip() for value in table["location"]}
        return sorted((name for name in names if name), key=str.casefold)

    def recommend(self, preferences: UserPreferences) -> RecommendationResult:
        """Rank a shortlist, or return the rating-and-votes fallback.

        A missing cache and a failed download raise before any model call.
        """
        table = self._load_table(self._settings)
        shortlisted, relaxed = shortlist(table, preferences, self._settings)
        if shortlisted.empty:
            return RecommendationResult(
                preferences=preferences,
                summary=_empty_summary(preferences),
                items=[],
                candidate_count=0,
                relaxed_filters=relaxed,
                source="fallback",
            )
        if not self._settings.llm_api_key.strip():
            return _fallback(preferences, shortlisted, relaxed)
        try:
            visible = shortlisted.head(preferences.top_n)
            content = self._client.complete(
                build_messages(preferences, visible),
                max_tokens=completion_token_budget(preferences.top_n),
            )
            summary, items = parse_recommendations(content, visible, preferences.top_n)
        except (InvalidModelOutput, OpenAIError):
            return _fallback(preferences, shortlisted, relaxed)
        return RecommendationResult(
            preferences=preferences,
            summary=summary,
            items=items,
            candidate_count=len(shortlisted),
            relaxed_filters=relaxed,
            source="llm",
        )


def _fallback(
    preferences: UserPreferences,
    shortlisted: pd.DataFrame,
    relaxed: list[str],
) -> RecommendationResult:
    ordered = shortlisted.sort_values("score", ascending=False, kind="mergesort")
    chosen = ordered.head(preferences.top_n)
    items = [
        _fallback_card(row, rank)
        for rank, (_, row) in enumerate(chosen.iterrows(), start=1)
    ]
    return RecommendationResult(
        preferences=preferences,
        summary="These recommendations were ordered by rating and number of votes.",
        items=items,
        candidate_count=len(shortlisted),
        relaxed_filters=relaxed,
        source="fallback",
    )


def _fallback_card(row: pd.Series, rank: int) -> Recommendation:
    cuisines = _cuisines_text(row.get("cuisines")) or "the listed cuisine"
    location = _text(row.get("location")) or "the matched area"
    rating = _optional_float(row.get("rating"))
    cost = _optional_int(row.get("cost_for_two"))
    if rating is None:
        rating_text = "A rating is unavailable"
    else:
        rating_text = f"The rating is {rating}"
    if cost is None:
        cost_text = "The cost for two is unavailable"
    else:
        cost_text = f"The cost for two is {cost}"
    return Recommendation(
        rank=rank,
        name=_text(row.get("name")),
        cuisines=_cuisines_text(row.get("cuisines")),
        rating=rating,
        cost_for_two=cost,
        explanation=(
            f"{_text(row.get('name'))} serves {cuisines} in {location}. "
            f"{rating_text}. {cost_text}."
        ),
        url=_text(row.get("url")),
    )


def _empty_summary(preferences: UserPreferences) -> str:
    cuisine = f"cuisine {preferences.cuisine}" if preferences.cuisine else "any cuisine"
    return (
        f"No restaurants matched location {preferences.location}, "
        f"{cuisine}, budget {preferences.budget}, "
        f"and minimum rating {preferences.min_rating}."
    )


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


def _text(value: object) -> str:
    if _missing(value):
        return ""
    return str(value)


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
