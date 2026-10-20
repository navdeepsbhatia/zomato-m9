"""Preference validation for UserPreferences (edge cases P1–P12)."""

import pytest
from pydantic import ValidationError

from recommender.models import (
    Recommendation,
    RecommendationResult,
    Restaurant,
    UserPreferences,
)


def _preferences(**overrides: object) -> UserPreferences:
    values: dict[str, object] = {
        "location": "Banashankari",
        "budget": "medium",
        "cuisine": "Italian",
        "min_rating": 3.5,
    }
    values.update(overrides)
    return UserPreferences.model_validate(values)


def _error_fields(exc: ValidationError) -> set[str]:
    return {str(err["loc"][0]) for err in exc.errors() if err["loc"]}


def test_p1_blank_location_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(location="")
    assert "location" in _error_fields(exc.value)


def test_p2_whitespace_only_location_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(location="   ")
    assert "location" in _error_fields(exc.value)


def test_p3_blank_cuisine_is_accepted():
    preferences = _preferences(cuisine="")
    assert preferences.cuisine == ""


def test_p4_whitespace_only_cuisine_is_stored_blank():
    preferences = _preferences(cuisine="  ")
    assert preferences.cuisine == ""


def test_p5_location_and_cuisine_are_stored_stripped():
    preferences = _preferences(location="  Banashankari  ", cuisine="  Italian ")
    assert preferences.location == "Banashankari"
    assert preferences.cuisine == "Italian"


def test_p6_rating_below_range_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(min_rating=-0.1)
    assert "min_rating" in _error_fields(exc.value)


def test_p7_rating_above_range_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(min_rating=5.1)
    assert "min_rating" in _error_fields(exc.value)


def test_p8_rating_at_slider_ends_is_accepted():
    assert _preferences(min_rating=0.0).min_rating == 0.0
    assert _preferences(min_rating=5.0).min_rating == 5.0


def test_p9_unknown_budget_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(budget="cheap")
    assert "budget" in _error_fields(exc.value)


def test_p10_non_positive_top_n_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _preferences(top_n=0)
    assert "top_n" in _error_fields(exc.value)

    with pytest.raises(ValidationError) as exc:
        _preferences(top_n=-1)
    assert "top_n" in _error_fields(exc.value)


def test_p11_empty_additional_preferences_are_accepted():
    preferences = _preferences()
    assert preferences.additional_preferences == ""
    assert _preferences(additional_preferences="").additional_preferences == ""


def test_p12_long_additional_preferences_are_accepted():
    text = "family-friendly " * 400
    preferences = _preferences(additional_preferences=text)
    assert preferences.additional_preferences == text


def test_valid_preferences_round_trip_through_dump_and_validate():
    preferences = _preferences(
        location="  Banashankari  ",
        cuisine="  Italian ",
        additional_preferences="quick service",
        top_n=4,
    )
    restored = UserPreferences.model_validate(preferences.model_dump())
    assert restored == preferences
    assert restored.location == "Banashankari"
    assert restored.cuisine == "Italian"


def test_top_n_defaults_from_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEFAULT_TOP_N", raising=False)
    assert _preferences().top_n == 5

    monkeypatch.setenv("DEFAULT_TOP_N", "3")
    assert _preferences().top_n == 3


def test_result_models_keep_restaurant_facts_and_source():
    preferences = _preferences()
    restaurant = Restaurant(
        name="Jalsa",
        address="Banashankari",
        location="Banashankari",
        listed_in_city="Banashankari",
        cuisines=["Italian", "Cafe"],
        cost_for_two=800,
        rating=4.1,
        votes=100,
        rest_type="Casual Dining",
        online_order=True,
        book_table=False,
        dish_liked="Pasta",
        url="https://example.test/jalsa",
    )
    item = Recommendation(
        rank=1,
        name=restaurant.name,
        cuisines="Italian, Cafe",
        rating=restaurant.rating,
        cost_for_two=restaurant.cost_for_two,
        explanation="Fits the cuisine and budget.",
        url=restaurant.url,
    )
    result = RecommendationResult(
        preferences=preferences,
        summary="One nearby Italian option.",
        items=[item],
        candidate_count=1,
        relaxed_filters=[],
        source="llm",
    )
    restored = RecommendationResult.model_validate(result.model_dump())
    assert restored == result

    payload = result.model_dump()
    payload["source"] = "invented"
    with pytest.raises(ValidationError) as exc:
        RecommendationResult.model_validate(payload)
    assert "source" in _error_fields(exc.value)
