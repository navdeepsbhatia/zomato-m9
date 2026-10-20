"""Runtime settings loaded from the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

DEFAULT_CACHE_PATH = Path("data/processed/restaurants.csv")


class Settings(BaseModel):
    """Configuration for data cache, shortlist size, budget bands, and the LLM."""

    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = ""
    llm_timeout_seconds: float = 30
    data_cache_path: Path = DEFAULT_CACHE_PATH
    candidate_limit: int = 15
    default_top_n: int = 5
    budget_low_min: int = 1
    budget_low_max: int = 400
    budget_medium_min: int = 401
    budget_medium_max: int = 800
    budget_high_min: int = 801

    model_config = {"frozen": True}


def load_settings() -> Settings:
    """Read `.env` and return settings, using defaults for unset optional variables."""
    load_dotenv()
    return Settings(
        llm_api_key=_text("LLM_API_KEY"),
        llm_base_url=_text("LLM_BASE_URL") or None,
        llm_model=_text("LLM_MODEL"),
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 30),
        data_cache_path=Path(_text("DATA_CACHE_PATH") or str(DEFAULT_CACHE_PATH)),
        candidate_limit=_int("CANDIDATE_LIMIT", 15),
        default_top_n=_int("DEFAULT_TOP_N", 5),
    )


def _text(name: str) -> str:
    return os.getenv(name, "").strip()


def _int(name: str, default: int) -> int:
    raw = _text(name)
    if not raw:
        return default
    return int(raw)


def _float(name: str, default: float) -> float:
    raw = _text(name)
    if not raw:
        return default
    return float(raw)
