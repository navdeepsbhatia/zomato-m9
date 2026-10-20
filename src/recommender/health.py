"""Readiness report for the local cache and the LLM key.

The report does not download the dataset and does not call the model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from recommender.config import Settings, load_settings
from recommender.data.loader import _read_cache

HealthStatus = Literal["ok", "degraded", "unavailable"]


class HealthCheck(BaseModel):
    """One dependency in the readiness report."""

    ok: bool
    detail: str


class HealthChecks(BaseModel):
    """Cache, LLM key, and whether Hugging Face would be involved."""

    cache: HealthCheck
    llm: HealthCheck
    huggingface: HealthCheck


class HealthReport(BaseModel):
    """Result of `GET /api/health`."""

    status: HealthStatus
    checks: HealthChecks


def check_health(settings: Settings | None = None) -> HealthReport:
    """Return cache and LLM-key readiness for the given settings.

    A missing argument loads settings from the environment. `ok` means the
    cache is readable and an LLM key is set. `degraded` means recommendations
    can still use the rating-and-votes fallback. `unavailable` means the cache
    is missing or unreadable.
    """
    resolved = load_settings() if settings is None else settings
    cache_path = Path(resolved.data_cache_path)
    cache = _cache_check(cache_path)
    llm = _llm_check(resolved)
    huggingface = _huggingface_check(cache.ok, cache_path.is_file())
    return HealthReport(
        status=_status(cache.ok, llm.ok),
        checks=HealthChecks(cache=cache, llm=llm, huggingface=huggingface),
    )


def health_status_code(report: HealthReport) -> int:
    """Map a report to an HTTP status.

    `ok` and `degraded` answer 200 because the app can still recommend.
    `unavailable` answers 503.
    """
    if report.status == "unavailable":
        return 503
    return 200


def health_response(settings: Settings | None = None) -> tuple[int, dict[str, object]]:
    """Return the HTTP status and JSON body for `GET /api/health`."""
    report = check_health(settings)
    return health_status_code(report), report.model_dump()


def _status(cache_ok: bool, llm_ok: bool) -> HealthStatus:
    if not cache_ok:
        return "unavailable"
    if not llm_ok:
        return "degraded"
    return "ok"


def _cache_check(path: Path) -> HealthCheck:
    if not path.is_file():
        return HealthCheck(
            ok=False,
            detail=(
                f"Restaurant cache is missing at {path}. "
                "The next recommendation request will download the dataset from Hugging Face."
            ),
        )
    try:
        frame = _read_cache(path)
    except Exception as exc:
        return HealthCheck(
            ok=False,
            detail=(
                f"Restaurant cache at {path} could not be read ({exc}). "
                "The app will not download the dataset again."
            ),
        )
    rows = len(frame)
    noun = "row" if rows == 1 else "rows"
    return HealthCheck(
        ok=True,
        detail=f"Restaurant cache is readable at {path} ({rows} {noun}).",
    )


def _llm_check(settings: Settings) -> HealthCheck:
    if settings.llm_api_key.strip():
        return HealthCheck(
            ok=True,
            detail="LLM API key is set. This check does not call the model.",
        )
    return HealthCheck(
        ok=False,
        detail=(
            "LLM API key is missing. Recommendations still work with the "
            "rating-and-votes fallback."
        ),
    )


def _huggingface_check(cache_ok: bool, cache_exists: bool) -> HealthCheck:
    if cache_ok:
        return HealthCheck(
            ok=True,
            detail="Not called. The local restaurant cache is in use.",
        )
    if cache_exists:
        return HealthCheck(
            ok=False,
            detail=(
                "Not called. The cache cannot be read, and the app will not "
                "download the dataset again."
            ),
        )
    return HealthCheck(
        ok=False,
        detail=(
            "Not called. The cache is missing, so the next recommendation "
            "request will try Hugging Face."
        ),
    )
