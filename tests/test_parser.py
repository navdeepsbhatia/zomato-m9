"""Offline prompt, Groq client, and parser tests. Case ids match docs/edge-case.md."""

import json

import httpx2
import pandas as pd
import pytest
from openai import APIStatusError, APITimeoutError

from recommender.config import Settings
from recommender.llm.client import GROQ_BASE_URL, GROQ_MODEL, LLMClient
from recommender.llm.parser import InvalidModelOutput, parse_recommendations
from recommender.llm.prompt import CANDIDATE_FIELDS, build_messages
from recommender.models import UserPreferences


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


def candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "name": "Jalsa",
        "address": "21st Main",
        "location": "Banashankari",
        "listed_in_city": "Banashankari",
        "cuisines": ["North Indian", "Chinese"],
        "cost_for_two": 800,
        "rating": 4.1,
        "votes": 775,
        "rest_type": "Casual Dining",
        "online_order": True,
        "book_table": False,
        "dish_liked": "Pasta",
        "url": "https://example.test/jalsa",
        "score": 1.0,
        "phone": "080",
        "reviews_list": "a very long review",
        "menu_item": "Masala Dosa",
    }
    row.update(overrides)
    return row


def frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def payload(summary: str, items: list[dict[str, object]]) -> str:
    return json.dumps({"summary": summary, "recommendations": items})


def test_prompt_has_system_and_user_messages_with_compact_candidates():
    messages = build_messages(
        preferences(),
        frame([candidate(name="Jalsa"), candidate(name="Spice", address="2 Road", url="https://example.test/spice", score=2)]),
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    system = messages[0]["content"]
    assert "JSON only" in system
    assert "one sentence" in system
    assert "exactly 2" in system
    assert "rank starts at 1" in system

    body = json.loads(messages[1]["content"])
    assert body["preferences"]["location"] == "Banashankari"
    assert body["preferences"]["additional_preferences"] == "quick service"
    assert body["preferences"]["top_n"] == 2
    assert [row["name"] for row in body["candidates"]] == ["Jalsa", "Spice"]
    assert set(body["candidates"][0]) == set(CANDIDATE_FIELDS)
    assert body["candidates"][0]["cuisines"] == ["North Indian", "Chinese"]
    dumped = messages[1]["content"]
    for forbidden in ("reviews_list", "menu_item", "phone", "address"):
        assert forbidden not in dumped


def test_prompt_sends_only_top_n_and_omits_long_fields():
    messages = build_messages(
        preferences(top_n=1, additional_preferences=""),
        frame(
            [
                candidate(name="First", dish_liked="Pasta, " * 40, votes=9999, rest_type="Casual Dining"),
                candidate(name="Second", address="2 Road", url="https://example.test/second"),
            ]
        ),
    )
    body = json.loads(messages[1]["content"])
    assert [row["name"] for row in body["candidates"]] == ["First"]
    assert "additional_preferences" not in body["preferences"]
    dumped = messages[1]["content"]
    for omitted in ("dish_liked", "votes", "rest_type", "online_order", "book_table", "Pasta"):
        assert omitted not in dumped


def test_l4_and_l6_valid_json_copies_facts_from_the_candidate():
    candidates = frame([candidate()])
    content = payload(
        "A strong nearby pick.",
        [
            {
                "rank": 4,
                "name": "Jalsa",
                "explanation": "Fits the request.",
                "rating": 1.0,
                "cost_for_two": 10,
                "cuisines": "Italian",
                "url": "https://example.test/invented",
            }
        ],
    )

    summary, items = parse_recommendations(content, candidates, top_n=1)

    assert summary == "A strong nearby pick."
    assert len(items) == 1
    item = items[0]
    assert item.rank == 1
    assert item.name == "Jalsa"
    assert item.cuisines == "North Indian, Chinese"
    assert item.rating == 4.1
    assert item.cost_for_two == 800
    assert item.url == "https://example.test/jalsa"
    assert item.explanation == "Fits the request."


def test_l5_unknown_restaurant_is_dropped():
    candidates = frame([candidate(name="Jalsa"), candidate(name="Spice", url="https://example.test/spice", score=2)])
    content = payload(
        "Two picks.",
        [
            {"rank": 1, "name": "Invented Place", "explanation": "Not real."},
            {"rank": 2, "name": "Spice", "explanation": "Real."},
        ],
    )

    _summary, items = parse_recommendations(content, candidates, top_n=2)

    assert [item.name for item in items] == ["Spice", "Jalsa"]
    assert items[0].explanation == "Real."
    assert "added from the shortlist" in items[1].explanation


def test_l7_no_usable_names_raise():
    content = payload("None of these.", [{"rank": 1, "name": "Nowhere", "explanation": "No."}])
    with pytest.raises(InvalidModelOutput):
        parse_recommendations(content, frame([candidate()]), top_n=1)


def test_l8_partial_list_is_padded_in_score_order():
    candidates = frame(
        [
            candidate(name="Low", score=1, url="https://example.test/low"),
            candidate(name="High", score=9, url="https://example.test/high", address="2 Road"),
            candidate(name="Mid", score=5, url="https://example.test/mid", address="3 Road"),
        ]
    )
    content = payload("One direct match.", [{"rank": 1, "name": "Low", "explanation": "Kept."}])

    _summary, items = parse_recommendations(content, candidates, top_n=3)

    assert [item.name for item in items] == ["Low", "High", "Mid"]
    assert [item.rank for item in items] == [1, 2, 3]
    assert items[1].url == "https://example.test/high"
    assert items[1].rating == 4.1
    assert items[1].cost_for_two == 800


def test_l9_non_json_and_fenced_json_raise():
    candidates = frame([candidate()])
    for content in ("Here are some restaurants.", '```json\n{"summary": "x", "recommendations": []}\n```'):
        with pytest.raises(InvalidModelOutput):
            parse_recommendations(content, candidates, top_n=1)


def test_l10_missing_summary_or_recommendations_raise():
    candidates = frame([candidate()])
    with pytest.raises(InvalidModelOutput):
        parse_recommendations(json.dumps({"recommendations": [{"name": "Jalsa"}]}), candidates, top_n=1)
    with pytest.raises(InvalidModelOutput):
        parse_recommendations(json.dumps({"summary": "Only a summary."}), candidates, top_n=1)


def test_l11_recommendations_must_be_a_list():
    content = json.dumps({"summary": "Bad shape.", "recommendations": {"name": "Jalsa"}})
    with pytest.raises(InvalidModelOutput):
        parse_recommendations(content, frame([candidate()]), top_n=1)


def test_l12_empty_recommendations_raise():
    content = payload("Nothing.", [])
    with pytest.raises(InvalidModelOutput):
        parse_recommendations(content, frame([candidate()]), top_n=2)


def test_l13_duplicate_names_keep_the_first_explanation():
    content = payload(
        "Repeated.",
        [
            {"rank": 1, "name": "Jalsa", "explanation": "First."},
            {"rank": 2, "name": "Jalsa", "explanation": "Second."},
        ],
    )

    _summary, items = parse_recommendations(content, frame([candidate()]), top_n=2)

    assert [item.name for item in items] == ["Jalsa"]
    assert items[0].explanation == "First."


def test_l14_shared_display_name_uses_the_first_row():
    candidates = frame(
        [
            candidate(name="Jalsa", url="https://example.test/first", score=9),
            candidate(name="Jalsa", url="https://example.test/second", address="2 Road", score=1),
        ]
    )
    content = payload("One name.", [{"rank": 1, "name": "Jalsa", "explanation": "Matched."}])

    _summary, items = parse_recommendations(content, candidates, top_n=2)

    assert [item.url for item in items] == ["https://example.test/first"]


def test_l15_name_match_is_exact():
    candidates = frame([candidate(name="Jalsa")])
    for name in ("jalsa", "Jalsa "):
        content = payload("Close.", [{"rank": 1, "name": name, "explanation": "No."}])
        with pytest.raises(InvalidModelOutput):
            parse_recommendations(content, candidates, top_n=1)


def test_l16_ranks_follow_valid_item_order():
    candidates = frame(
        [
            candidate(name="First", url="https://example.test/first", score=1),
            candidate(name="Second", url="https://example.test/second", address="2 Road", score=2),
        ]
    )
    content = payload(
        "Reordered.",
        [
            {"rank": 3, "name": "Second", "explanation": "Later in the list."},
            {"rank": 1, "name": "First", "explanation": "Earlier in the list."},
        ],
    )

    _summary, items = parse_recommendations(content, candidates, top_n=2)

    assert [item.name for item in items] == ["Second", "First"]
    assert [item.rank for item in items] == [1, 2]


def test_l17_blank_explanation_is_kept():
    content = payload("Blank.", [{"rank": 1, "name": "Jalsa", "explanation": ""}])
    _summary, items = parse_recommendations(content, frame([candidate()]), top_n=1)
    assert items[0].explanation == ""


def test_l18_extra_items_stop_at_top_n():
    candidates = frame(
        [
            candidate(name="A", url="https://example.test/a", score=1),
            candidate(name="B", url="https://example.test/b", address="2 Road", score=2),
            candidate(name="C", url="https://example.test/c", address="3 Road", score=3),
        ]
    )
    content = payload(
        "Too many.",
        [
            {"rank": 1, "name": "A", "explanation": "A"},
            {"rank": 2, "name": "B", "explanation": "B"},
            {"rank": 3, "name": "C", "explanation": "C"},
        ],
    )

    _summary, items = parse_recommendations(content, candidates, top_n=2)

    assert [item.name for item in items] == ["A", "B"]


def test_client_returns_content_and_requests_groq_json(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class _Completions:
        def create(self, **kwargs: object) -> object:
            captured["create"] = kwargs
            message = type("Message", (), {"content": '{"summary":"ok"}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["init"] = kwargs
            self.chat = _Chat()

    monkeypatch.setattr("recommender.llm.client.OpenAI", _FakeOpenAI)
    settings = Settings(
        llm_api_key="groq-key",
        llm_base_url=GROQ_BASE_URL,
        llm_model=GROQ_MODEL,
        llm_timeout_seconds=12,
    )

    text = LLMClient(settings).complete([{"role": "user", "content": "not json on purpose"}])

    assert text == '{"summary":"ok"}'
    create = captured["create"]
    assert isinstance(create, dict)
    assert create["model"] == GROQ_MODEL
    assert create["temperature"] == 0.2
    assert create["max_tokens"] == 630
    assert create["response_format"] == {"type": "json_object"}
    assert create["extra_body"] == {"reasoning_effort": "low"}
    init = captured["init"]
    assert isinstance(init, dict)
    assert init["api_key"] == "groq-key"
    assert init["base_url"] == GROQ_BASE_URL
    assert init["timeout"] == 12


def test_client_defaults_to_the_free_groq_model(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class _Completions:
        def create(self, **kwargs: object) -> object:
            captured["create"] = kwargs
            message = type("Message", (), {"content": "{}"})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["init"] = kwargs
            self.chat = _Chat()

    monkeypatch.setattr("recommender.llm.client.OpenAI", _FakeOpenAI)

    LLMClient(Settings()).complete([{"role": "user", "content": "hi"}])

    create = captured["create"]
    init = captured["init"]
    assert isinstance(create, dict)
    assert isinstance(init, dict)
    assert create["model"] == "openai/gpt-oss-120b"
    assert init["base_url"] == "https://api.groq.com/openai/v1"


def test_client_propagates_timeout_and_http_errors(monkeypatch: pytest.MonkeyPatch):
    request = httpx2.Request("POST", GROQ_BASE_URL)
    errors = [
        APITimeoutError(request),
        APIStatusError("rate limit", response=httpx2.Response(429, request=request), body=None),
    ]

    class _Completions:
        def __init__(self, error: Exception) -> None:
            self._error = error

        def create(self, **_kwargs: object) -> object:
            raise self._error

    class _FakeOpenAI:
        def __init__(self, error: Exception) -> None:
            self.chat = type("Chat", (), {"completions": _Completions(error)})()

    for error in errors:

        def fake_openai(*_args: object, _error: Exception = error, **_kwargs: object) -> _FakeOpenAI:
            return _FakeOpenAI(_error)

        monkeypatch.setattr("recommender.llm.client.OpenAI", fake_openai)
        with pytest.raises(type(error)):
            LLMClient(Settings(llm_api_key="groq-key")).complete([{"role": "user", "content": "hi"}])
