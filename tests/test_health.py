"""Offline health-check tests. Case ids match docs/edge-case.md."""

import csv
import json
from pathlib import Path

import pytest

from recommender.config import Settings
from recommender.data.cleaner import CLEANED_COLUMNS
from recommender.health import check_health, health_response


def _settings(path: Path, api_key: str = "test-key") -> Settings:
    return Settings(llm_api_key=api_key, data_cache_path=path)


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


def _block_download(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_download(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("health check must not download the dataset")

    monkeypatch.setattr("recommender.data.loader.load_dataset", fail_download)


def test_h1_readable_cache_and_key_are_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _block_download(monkeypatch)
    cache = tmp_path / "restaurants.csv"
    _write_cache(cache)

    status_code, body = health_response(_settings(cache, "super-secret-key"))

    assert status_code == 200
    assert body["status"] == "ok"
    checks = body["checks"]
    assert checks["cache"]["ok"] is True
    assert "1 row" in checks["cache"]["detail"]
    assert checks["llm"]["ok"] is True
    assert "does not call the model" in checks["llm"]["detail"]
    assert checks["huggingface"]["ok"] is True
    assert "Not called" in checks["huggingface"]["detail"]
    assert "super-secret-key" not in json.dumps(body)


def test_h2_missing_key_is_degraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _block_download(monkeypatch)
    cache = tmp_path / "restaurants.csv"
    _write_cache(cache)

    report = check_health(_settings(cache, ""))
    status_code, body = health_response(_settings(cache, ""))

    assert report.status == "degraded"
    assert status_code == 200
    assert body["status"] == "degraded"
    assert body["checks"]["cache"]["ok"] is True
    assert body["checks"]["llm"]["ok"] is False
    assert "fallback" in body["checks"]["llm"]["detail"]


def test_h3_missing_cache_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _block_download(monkeypatch)
    missing = tmp_path / "missing.csv"

    status_code, body = health_response(_settings(missing))

    assert status_code == 503
    assert body["status"] == "unavailable"
    assert body["checks"]["cache"]["ok"] is False
    assert "missing" in body["checks"]["cache"]["detail"]
    assert body["checks"]["huggingface"]["ok"] is False
    assert "Hugging Face" in body["checks"]["huggingface"]["detail"]
    assert "Not called" in body["checks"]["huggingface"]["detail"]


def test_h4_unreadable_cache_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _block_download(monkeypatch)
    broken = tmp_path / "restaurants.csv"
    broken.write_text("not a restaurant table", encoding="utf-8")

    status_code, body = health_response(_settings(broken))

    assert status_code == 503
    assert body["status"] == "unavailable"
    assert body["checks"]["cache"]["ok"] is False
    assert "could not be read" in body["checks"]["cache"]["detail"]
    assert body["checks"]["huggingface"]["ok"] is False
    assert "will not download" in body["checks"]["huggingface"]["detail"]


def test_h6_whitespace_key_is_treated_as_missing(tmp_path: Path):
    cache = tmp_path / "restaurants.csv"
    _write_cache(cache)

    report = check_health(_settings(cache, "   "))

    assert report.status == "degraded"
    assert report.checks.llm.ok is False
