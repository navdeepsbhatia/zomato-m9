"""Offline recommendation service tests. Case ids match docs/edge-case.md."""

import json
from pathlib import Path

import httpx2
import pandas as pd
import pytest
from openai import APIStatusError, APITimeoutError

from recommender.config import Settings
from recommender.data.loader import DatasetDownloadError
from recommender.llm.client import GROQ_BASE_URL
from recommender.models import UserPreferences
from recommender.service import RecommendationService


class FakeClient:
    def __init__(self, content: str = "", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], **_kwargs: object) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.content


def preferences(**overrides: object) -> UserPreferences:
    values: dict[str, object] = {
        "location": "Banashankari",
        "budget": "medium",
        "cuisine": "Italian",
        "min_rating": 3.5,
        "additional_preferences": "quick service",
        "top_n": 2,
    }
    values.update(overrides)
    return UserPreferences.model_validate(values)


def restaurant(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "name": "Jalsa",
        "address": "21st Main",
        "location": "Banashankari",
        "listed_in_city": "Banashankari",
        "cuisines": ["Italian"],
        "cost_for_two": 500,
        "rating": 4.2,
        "votes": 10,
        "rest_type": "Casual Dining",
        "online_order": True,
        "book_table": False,
        "dish_liked": "Pasta",
        "url": "https://example.test/jalsa",
    }
    row.update(overrides)
    return row


def table(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def service(frame: pd.DataFrame, client: FakeClient, **settings: object) -> RecommendationService:
    values: dict[str, object] = {"llm_api_key": "groq-key", "candidate_limit": 15}
    values.update(settings)
    return RecommendationService(
        Settings.model_validate(values),
        client=client,
        load_table=lambda _settings: frame,
    )


def model_json(items: list[dict[str, object]], summary: str = "A short list.") -> str:
    return json.dumps({"summary": summary, "recommendations": items})


def test_success_uses_candidate_facts_and_marks_llm():
    frame = table(
        [
            restaurant(name="Low", votes=1, rating=4.0, cost_for_two=500, url="https://example.test/low"),
            restaurant(
                name="High",
                votes=50,
                rating=4.6,
                cost_for_two=700,
                address="2 Road",
                url="https://example.test/high",
            ),
        ]
    )
    client = FakeClient(
        model_json(
            [
                {
                    "rank": 9,
                    "name": "Low",
                    "explanation": "Quieter, and it still fits.",
                    "rating": 1.0,
                    "cost_for_two": 1,
                }
            ]
        )
    )

    result = service(frame, client, default_top_n=2).recommend(preferences(top_n=2))

    assert client.calls == 1
    assert result.source == "llm"
    assert result.candidate_count == 2
    assert result.summary == "A short list."
    assert result.relaxed_filters == []
    assert [item.name for item in result.items] == ["Low", "High"]
    low = result.items[0]
    assert low.explanation == "Quieter, and it still fits."
    assert low.rating == 4.0
    assert low.cost_for_two == 500
    assert low.url == "https://example.test/low"
    assert low.cuisines == "Italian"


def test_partial_parse_stays_llm():
    frame = table(
        [
            restaurant(name="Only", votes=3, url="https://example.test/only"),
            restaurant(name="Spare", votes=9, address="2 Road", url="https://example.test/spare"),
        ]
    )
    client = FakeClient(
        model_json([{"rank": 1, "name": "Only", "explanation": "The model picked this one."}])
    )

    result = service(frame, client).recommend(preferences(top_n=2))

    assert result.source == "llm"
    assert [item.name for item in result.items] == ["Only", "Spare"]
    assert result.items[1].url == "https://example.test/spare"
    assert result.items[1].rating == 4.2
    assert result.items[1].cost_for_two == 500


def test_invalid_model_output_falls_back_to_candidate_facts():
    frame = table(
        [
            restaurant(name="Second", votes=5, rating=4.0, cost_for_two=600, url="https://example.test/second"),
            restaurant(
                name="First",
                votes=20,
                rating=4.8,
                cost_for_two=450,
                address="2 Road",
                url="https://example.test/first",
            ),
        ]
    )
    client = FakeClient("this is not json")

    result = service(frame, client).recommend(preferences(top_n=2))

    assert client.calls == 1
    assert result.source == "fallback"
    assert [item.name for item in result.items] == ["First", "Second"]
    assert result.items[0].rating == 4.8
    assert result.items[0].cost_for_two == 450
    assert result.items[0].url == "https://example.test/first"
    assert result.items[0].cuisines == "Italian"
    assert "Banashankari" in result.items[0].explanation
    assert "model" not in result.items[0].explanation.lower()
    assert "rating and number of votes" in result.summary


def test_l21_missing_or_blank_key_does_not_call_the_client():
    frame = table([restaurant()])
    for api_key in ("", "   "):
        client = FakeClient(model_json([{"name": "Jalsa", "explanation": "Nope."}]))
        result = service(frame, client, llm_api_key=api_key).recommend(preferences(top_n=1))
        assert client.calls == 0
        assert result.source == "fallback"
        assert result.items[0].name == "Jalsa"
        assert result.items[0].rating == 4.2


def test_timeout_and_http_errors_fall_back():
    frame = table([restaurant(name="Kept", votes=4)])
    request = httpx2.Request("POST", GROQ_BASE_URL)
    errors = [
        APITimeoutError(request),
        APIStatusError("rate limit", response=httpx2.Response(429, request=request), body=None),
    ]
    for error in errors:
        client = FakeClient(error=error)
        result = service(frame, client).recommend(preferences(top_n=1))
        assert result.source == "fallback"
        assert result.items[0].name == "Kept"
        assert result.items[0].url == "https://example.test/jalsa"


def test_b1_fallback_orders_by_score_and_stops_at_top_n():
    frame = table(
        [
            restaurant(name="Low", votes=1, rating=4.0, url="https://example.test/low"),
            restaurant(name="High", votes=30, rating=4.0, address="2 Road", url="https://example.test/high"),
            restaurant(name="Mid", votes=8, rating=4.0, address="3 Road", url="https://example.test/mid"),
        ]
    )
    client = FakeClient()

    result = service(frame, client, llm_api_key="").recommend(preferences(top_n=2))

    assert result.source == "fallback"
    assert [item.name for item in result.items] == ["High", "Mid"]
    assert [item.rank for item in result.items] == [1, 2]
    assert result.candidate_count == 3


def test_fallback_explanation_names_the_facts_and_a_missing_rating():
    frame = table(
        [
            restaurant(
                name="Unrated",
                cuisines=["Chinese"],
                rating=None,
                votes=12,
                cost_for_two=200,
                location="Banashankari",
                url="https://example.test/unrated",
            )
        ]
    )
    client = FakeClient()

    result = service(frame, client, llm_api_key="").recommend(
        preferences(cuisine="Sushi", budget="low", min_rating=4.5, top_n=1)
    )

    explanation = result.items[0].explanation
    assert result.source == "fallback"
    assert "Chinese" in explanation
    assert "Banashankari" in explanation
    assert "rating" in explanation.lower()
    assert "unavailable" in explanation.lower()
    assert "cost for two" in explanation.lower()
    assert "200" in explanation
    assert "model" not in explanation.lower()
    assert "rating and number of votes" in result.summary


def test_l1_and_u6_empty_shortlist_does_not_call_the_client():
    frame = table([restaurant(name="Real", location="Banashankari")])
    client = FakeClient(model_json([{"name": "Real", "explanation": "Should not be asked."}]))

    result = service(frame, client).recommend(
        preferences(location="Delhi", cuisine="Italian", budget="medium", min_rating=3.5)
    )

    assert client.calls == 0
    assert result.items == []
    assert result.candidate_count == 0
    assert result.relaxed_filters == ["cuisine", "budget", "min_rating"]
    assert result.source == "fallback"
    for text in ("Delhi", "Italian", "medium", "3.5"):
        assert text in result.summary


def test_location_choices_lists_unique_neighborhoods_in_order():
    frame = table(
        [
            restaurant(name="A", location="Jayanagar"),
            restaurant(name="B", location="Banashankari", address="2 Road"),
            restaurant(name="C", location="  ", address="3 Road"),
            restaurant(name="D", location="Jayanagar", address="4 Road"),
        ]
    )

    assert service(frame, FakeClient()).location_choices() == ["Banashankari", "Jayanagar"]


def test_blank_cuisine_is_not_recorded_as_a_relaxed_filter():
    frame = table(
        [
            restaurant(name="Italian"),
            restaurant(
                name="Chinese",
                cuisines=["Chinese"],
                address="2 Road",
                rating=4.8,
                votes=50,
            ),
        ]
    )
    client = FakeClient(
        model_json(
            [
                {"name": "Chinese", "explanation": "Fits."},
                {"name": "Italian", "explanation": "Also fits."},
            ]
        )
    )

    result = service(frame, client).recommend(preferences(cuisine="", top_n=2))

    assert client.calls == 1
    assert result.relaxed_filters == []
    assert [item.name for item in result.items] == ["Chinese", "Italian"]


def test_download_failure_raises_before_any_llm_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fail_download(*_args: object, **_kwargs: object) -> None:
        raise OSError("network down")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_download)
    client = FakeClient(model_json([{"name": "Jalsa", "explanation": "No."}]))
    settings = Settings(llm_api_key="groq-key", data_cache_path=tmp_path / "missing.csv")
    recommender = RecommendationService(settings, client=client)

    with pytest.raises(DatasetDownloadError):
        recommender.recommend(preferences())

    assert client.calls == 0
