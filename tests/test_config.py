"""Settings fall back to documented defaults when optional variables are unset."""

from pathlib import Path

from recommender.config import DEFAULT_CACHE_PATH, Settings, load_settings

OPTIONAL_VARS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "DATA_CACHE_PATH",
    "CANDIDATE_LIMIT",
    "DEFAULT_TOP_N",
)


def test_settings_defaults_when_optional_variables_are_unset(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("recommender.config.load_dotenv", lambda *_args, **_kwargs: False)
    for name in OPTIONAL_VARS:
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings == Settings()
    assert settings.llm_api_key == ""
    assert settings.llm_base_url is None
    assert settings.llm_model == ""
    assert settings.llm_timeout_seconds == 30
    assert settings.data_cache_path == DEFAULT_CACHE_PATH
    assert settings.candidate_limit == 15
    assert settings.default_top_n == 5
    assert (settings.budget_low_min, settings.budget_low_max) == (1, 400)
    assert (settings.budget_medium_min, settings.budget_medium_max) == (401, 800)
    assert settings.budget_high_min == 801


def test_settings_reads_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "demo-model")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("DATA_CACHE_PATH", "cache/restaurants.csv")
    monkeypatch.setenv("CANDIDATE_LIMIT", "7")
    monkeypatch.setenv("DEFAULT_TOP_N", "3")

    settings = load_settings()

    assert settings.llm_api_key == "secret"
    assert settings.llm_base_url == "https://example.test/v1"
    assert settings.llm_model == "demo-model"
    assert settings.llm_timeout_seconds == 12.5
    assert settings.data_cache_path == Path("cache/restaurants.csv")
    assert settings.candidate_limit == 7
    assert settings.default_top_n == 3
