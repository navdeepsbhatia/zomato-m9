"""ASGI entry point. Serves the Streamlit page and GET /api/health."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st
from starlette.responses import JSONResponse
from starlette.routing import Route

from recommender.health import health_response

_PAGE = Path(__file__).resolve().parent / "main.py"


async def health(_request: object) -> JSONResponse:
    """Report cache and LLM-key readiness. Does not call Hugging Face or the model."""
    status_code, body = health_response()
    return JSONResponse(
        body,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


app = st.App(
    _PAGE,
    routes=[Route("/api/health", health, methods=["GET"])],
)
