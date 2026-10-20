"""Typed preferences, restaurant records, and recommendation results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from recommender.config import load_settings

Budget = Literal["low", "medium", "high"]
RecommendationSource = Literal["llm", "fallback"]


def _default_top_n() -> int:
    return load_settings().default_top_n


class UserPreferences(BaseModel):
    """Filters and free-text notes for one recommendation request."""

    location: str = Field(min_length=1)
    budget: Budget
    cuisine: str = ""
    min_rating: float = Field(ge=0.0, le=5.0)
    additional_preferences: str = ""
    top_n: int = Field(default_factory=_default_top_n, gt=0)

    @field_validator("location", "cuisine", mode="before")
    @classmethod
    def strip_location_and_cuisine(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Restaurant(BaseModel):
    """One cleaned restaurant row from the processed table."""

    name: str
    address: str
    location: str
    listed_in_city: str
    cuisines: list[str]
    cost_for_two: int | None
    rating: float | None
    votes: int
    rest_type: str
    online_order: bool
    book_table: bool
    dish_liked: str
    url: str


class Recommendation(BaseModel):
    """One result card. Displayed facts are copied from the candidate row."""

    rank: int
    name: str
    cuisines: str
    rating: float | None
    cost_for_two: int | None
    explanation: str
    url: str


class RecommendationResult(BaseModel):
    """Everything the UI renders for one request."""

    preferences: UserPreferences
    summary: str
    items: list[Recommendation]
    candidate_count: int
    relaxed_filters: list[str]
    source: RecommendationSource
