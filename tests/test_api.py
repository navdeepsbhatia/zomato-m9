"""HTTP contract for the Railway API. Does not download data or call the model."""

import csv
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.api import app
from recommender.data.cleaner import CLEANED_COLUMNS
from recommender.data.loader import CacheReadError
from recommender.models import Recommendation, RecommendationResult, UserPreferences

client = TestClient(app)


def _write_cache(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "name": "Jalsa",
        "address": "21st Main",
        "location": "Banashankari",
        "listed_in_city": "Banashankari",
        "cuisines": "North Indian, Chinese",
        "cost_for_two": "800",
        "rating": "4.1",
        "votes": "775",
        "rest_type": "Casual Dining",
        "online_order": "True",
        "book_table": "False",
        "dish_liked": "Pasta",
        "url": "https://example.test/jalsa",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLEANED_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _preferences() -> UserPreferences:
    return UserPreferences(
        location="Banashankari",
        budget="medium",
        cuisine="Italian",
        min_rating=3.5,
    )


def _result() -> RecommendationResult:
    return RecommendationResult(
        preferences=_preferences(),
        summary="One Italian place in Banashankari.",
        items=[
            Recommendation(
                rank=1,
                name="Onesta",
                cuisines="Pizza, Italian",
                rating=4.6,
                cost_for_two=600,
                explanation="Fits the request.",
                url="https://example.test/onesta",
            )
        ],
        candidate_count=4,
        relaxed_filters=["cuisine"],
        source="fallback",
    )


class _FakeService:
    def location_choices(self) -> list[str]:
        return ["Banashankari", "Koramangala"]

    def recommend(self, _preferences: UserPreferences) -> RecommendationResult:
        return _result()


def test_health_ok_hides_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache = tmp_path / "restaurants.csv"
    _write_cache(cache)
    monkeypatch.setenv("DATA_CACHE_PATH", str(cache))
    monkeypatch.setenv("LLM_API_KEY", "super-secret-key")

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "super-secret-key" not in response.text


def test_health_missing_cache_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_CACHE_PATH", str(tmp_path / "missing.csv"))
    monkeypatch.setenv("LLM_API_KEY", "super-secret-key")

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_locations_returns_names(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.get_service", lambda: _FakeService())

    response = client.get("/api/locations")

    assert response.status_code == 200
    assert response.json() == {"locations": ["Banashankari", "Koramangala"]}


def test_locations_cache_error_is_503(monkeypatch: pytest.MonkeyPatch):
    class Broken:
        def location_choices(self) -> list[str]:
            raise CacheReadError("Could not read the restaurant cache.")

    monkeypatch.setattr("app.api.get_service", lambda: Broken())

    response = client.get("/api/locations")

    assert response.status_code == 503
    assert "cache" in response.json()["detail"]


def test_recommendations_returns_cards(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.get_service", lambda: _FakeService())

    response = client.post(
        "/api/recommendations",
        json={
            "location": "Banashankari",
            "budget": "medium",
            "cuisine": "Italian",
            "min_rating": 3.5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "fallback"
    assert body["relaxed_filters"] == ["cuisine"]
    item = body["items"][0]
    assert item["rank"] == 1
    assert item["name"] == "Onesta"
    assert item["cuisines"] == "Pizza, Italian"
    assert item["rating"] == 4.6
    assert item["cost_for_two"] == 600
    assert item["explanation"] == "Fits the request."
    assert item["url"] == "https://example.test/onesta"


def test_recommendations_reject_invalid_preferences():
    response = client.post(
        "/api/recommendations",
        json={"location": "  ", "budget": "medium", "min_rating": 3.5},
    )

    assert response.status_code == 422


def test_recommendations_reject_non_json():
    response = client.post(
        "/api/recommendations",
        content="not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_cors_allows_the_configured_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://table.vercel.app, http://127.0.0.1:5173")
    monkeypatch.setattr("app.api.get_service", lambda: _FakeService())

    response = client.get("/api/locations", headers={"Origin": "https://table.vercel.app"})

    assert response.headers["access-control-allow-origin"] == "https://table.vercel.app"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_cors_preflight_rejects_a_different_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://table.vercel.app")

    response = client.options(
        "/api/recommendations",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_health_body_is_json_without_a_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def fail_download(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("health check must not download the dataset")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_download)
    cache = tmp_path / "restaurants.csv"
    _write_cache(cache)
    monkeypatch.setenv("DATA_CACHE_PATH", str(cache))
    monkeypatch.setenv("LLM_API_KEY", "")

    response = client.get("/api/health")

    assert response.status_code == 200
    body = json.loads(response.text)
    assert body["status"] == "degraded"
    assert body["checks"]["huggingface"]["detail"].startswith("Not called")
