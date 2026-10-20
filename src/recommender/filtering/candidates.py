"""Hard filters, budget bands, and the candidate shortlist."""

from __future__ import annotations

import math

import pandas as pd

from recommender.config import Settings
from recommender.models import UserPreferences


def budget_bounds(budget: str, settings: Settings) -> tuple[int, int | None]:
    """Return the inclusive cost-for-two band for ``low``, ``medium``, or ``high``.

    The high band has no upper bound. Cutoffs come from ``settings``.
    """
    if budget == "low":
        return settings.budget_low_min, settings.budget_low_max
    if budget == "medium":
        return settings.budget_medium_min, settings.budget_medium_max
    if budget == "high":
        return settings.budget_high_min, None
    raise ValueError(f"Unknown budget '{budget}'. Expected low, medium, or high.")


def apply_filters(
    df: pd.DataFrame,
    preferences: UserPreferences,
    settings: Settings,
    *,
    cuisine: bool = True,
    rating: bool = True,
    budget_mode: str = "exact",
) -> pd.DataFrame:
    """Return rows that match location and the requested cuisine, rating, and budget.

    Location always applies. ``cuisine`` and ``rating`` can be turned off.
    ``budget_mode`` is ``exact`` or ``widened`` by one budget step.
    ``additional_preferences`` is not a filter.
    """
    mask = _location_mask(df, preferences.location)
    if cuisine and preferences.cuisine.strip():
        mask = mask & _cuisine_mask(df, preferences.cuisine)
    if rating:
        mask = mask & _rating_mask(df, preferences.min_rating)
    mask = mask & _cost_mask(df, preferences.budget, settings, budget_mode)
    return df.loc[mask].copy()


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Copy ``df`` and set ``score`` to ``rating * log(1 + votes)``.

    A null rating scores as 0 so the column stays numeric after the rating
    filter is dropped.
    """
    scored = df.copy()
    scores = [
        _score_number(rating) * math.log(1 + _score_number(votes))
        for rating, votes in zip(scored["rating"], scored["votes"], strict=False)
    ]
    scored["score"] = pd.Series(scores, index=scored.index, dtype="float64")
    return scored


def shortlist(
    df: pd.DataFrame,
    preferences: UserPreferences,
    settings: Settings,
) -> tuple[pd.DataFrame, list[str]]:
    """Return the top candidates and the filters that were relaxed.

    Relaxation stops at the first non-empty step: original filters, drop
    cuisine, widen budget by one step, then drop the minimum rating.
    A blank cuisine is not a constraint and is not recorded as relaxed.
    Location is never dropped. Tied scores keep their incoming order.
    Rows are ordered by score descending and capped at
    ``settings.candidate_limit``.
    """
    relaxed: list[str] = []
    cuisine_requested = bool(preferences.cuisine.strip())
    matched = apply_filters(df, preferences, settings, cuisine=cuisine_requested)
    if matched.empty and cuisine_requested:
        relaxed.append("cuisine")
        matched = apply_filters(df, preferences, settings, cuisine=False)
    if matched.empty:
        relaxed.append("budget")
        matched = apply_filters(
            df,
            preferences,
            settings,
            cuisine=False,
            budget_mode="widened",
        )
    if matched.empty:
        relaxed.append("min_rating")
        matched = apply_filters(
            df,
            preferences,
            settings,
            cuisine=False,
            rating=False,
            budget_mode="widened",
        )

    ordered = score_candidates(matched).sort_values(
        "score",
        ascending=False,
        kind="mergesort",
    )
    limited = ordered.head(settings.candidate_limit).reset_index(drop=True)
    return limited, relaxed


def _bounds(budget: str, settings: Settings, mode: str) -> tuple[int, int | None]:
    if mode == "exact":
        return budget_bounds(budget, settings)
    if mode != "widened":
        raise ValueError(f"Unknown budget mode '{mode}'. Expected exact or widened.")
    if budget == "low":
        return settings.budget_low_min, settings.budget_medium_max
    if budget == "medium":
        return settings.budget_low_min, None
    if budget == "high":
        return settings.budget_medium_min, None
    raise ValueError(f"Unknown budget '{budget}'. Expected low, medium, or high.")


def _location_mask(df: pd.DataFrame, location: str) -> pd.Series:
    needle = location.strip().casefold()
    in_location = _field_contains(df["location"], needle)
    in_city = _field_contains(df["listed_in_city"], needle)
    return in_location | in_city


def _field_contains(series: pd.Series, needle: str) -> pd.Series:
    folded = series.map(_cell_text)
    return folded.map(lambda text: needle in text).astype(bool)


def _cell_text(value: object) -> str:
    if _missing(value):
        return ""
    return str(value).strip().casefold()


def _cuisine_mask(df: pd.DataFrame, cuisine: str) -> pd.Series:
    needle = cuisine.strip().casefold()
    matches = [_cuisine_match(value, needle) for value in df["cuisines"]]
    return pd.Series(matches, index=df.index, dtype=bool)


def _cuisine_match(value: object, needle: str) -> bool:
    return any(token.casefold() == needle for token in _cuisine_tokens(value))


def _cuisine_tokens(value: object) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if _missing(value):
        return []
    if isinstance(value, (list, tuple)):
        items = value
    elif hasattr(value, "tolist"):
        items = value.tolist()
    else:
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _rating_mask(df: pd.DataFrame, minimum: float) -> pd.Series:
    ratings = pd.to_numeric(df["rating"], errors="coerce")
    high_enough = ratings.ge(minimum).fillna(False)
    return ratings.notna() & high_enough


def _cost_mask(
    df: pd.DataFrame,
    budget: str,
    settings: Settings,
    mode: str,
) -> pd.Series:
    lower, upper = _bounds(budget, settings, mode)
    costs = pd.to_numeric(df["cost_for_two"], errors="coerce")
    mask = costs.notna() & costs.ge(lower).fillna(False)
    if upper is not None:
        mask = mask & costs.le(upper).fillna(False)
    return mask


def _score_number(value: object) -> float:
    if isinstance(value, bool) or _missing(value):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number) or number < 0:
        return 0.0
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
