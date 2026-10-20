"""JSON API for Railway. The Streamlit page stays a local entry point."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from recommender.data.loader import CacheReadError, DatasetDownloadError
from recommender.health import health_response
from recommender.models import UserPreferences
from recommender.service import RecommendationService

load_dotenv()

_service: RecommendationService | None = None


def get_service() -> RecommendationService:
    """Return the process-wide recommendation service."""
    global _service
    if _service is None:
        _service = RecommendationService()
    return _service


def allowed_origins() -> set[str]:
    """Origins from ALLOWED_ORIGINS that may call this API from a browser."""
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def _cache_error(exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=503)


async def health(_request: Request) -> JSONResponse:
    """Report cache and LLM-key readiness. Does not download or call the model."""
    status_code, body = health_response()
    return JSONResponse(
        body,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


async def locations(_request: Request) -> JSONResponse:
    """Return neighborhood names from the restaurant cache."""
    try:
        names = get_service().location_choices()
    except (DatasetDownloadError, CacheReadError) as exc:
        return _cache_error(exc)
    return JSONResponse({"locations": names}, headers={"Cache-Control": "no-store"})


async def recommendations(request: Request) -> JSONResponse:
    """Rank restaurants for one preference payload."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Request body must be JSON."}, status_code=422)
    if not isinstance(payload, dict):
        return JSONResponse({"detail": "Request body must be a JSON object."}, status_code=422)
    try:
        preferences = UserPreferences.model_validate(payload)
    except ValidationError as exc:
        return JSONResponse({"detail": json.loads(exc.json())}, status_code=422)
    try:
        result = get_service().recommend(preferences)
    except (DatasetDownloadError, CacheReadError) as exc:
        return _cache_error(exc)
    return JSONResponse(result.model_dump(mode="json"))


class AllowedOriginCORS:
    """Allow GET, POST, and OPTIONS only for origins listed in ALLOWED_ORIGINS."""

    def __init__(self, app: Starlette) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        origin = _header(scope, b"origin")
        allowed = origin is not None and origin in allowed_origins()
        if scope["method"] == "OPTIONS" and _header(scope, b"access-control-request-method"):
            if not allowed:
                response = Response("Disallowed CORS origin", status_code=400)
                await response(scope, receive, send)
                return
            response = Response(status_code=204, headers=_cors_headers(origin))
            await response(scope, receive, send)
            return

        async def send_with_cors(message: dict) -> None:
            if allowed and message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for name, value in _cors_headers(origin).items():
                    headers.append((name.lower().encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cors)


def _header(scope: dict, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode()
    return None


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept",
        "Vary": "Origin",
    }


app = AllowedOriginCORS(
    Starlette(
        routes=[
            Route("/api/health", health, methods=["GET"]),
            Route("/api/locations", locations, methods=["GET"]),
            Route("/api/recommendations", recommendations, methods=["POST"]),
        ],
    )
)
