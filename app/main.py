"""Streamlit page for restaurant recommendations."""

from __future__ import annotations

import html
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st
from pydantic import ValidationError

from recommender.data.loader import CacheReadError, DatasetDownloadError
from recommender.models import RecommendationResult, UserPreferences
from recommender.service import RecommendationService

_CSS = (Path(__file__).resolve().parent / "theme.css").read_text(encoding="utf-8")


def _show_result(result: RecommendationResult, preferences: UserPreferences) -> None:
    parts = ['<section class="results">']
    if result.items and result.summary:
        parts.append(f'<p class="summary">{html.escape(result.summary)}</p>')
    if result.relaxed_filters:
        relaxed = ", ".join(result.relaxed_filters)
        parts.append(
            _notice(
                "warn",
                f"Relaxed filters: {relaxed}.",
                "The shortlist was widened so a recommendation could still be made.",
            )
        )
    if result.source == "fallback" and result.items:
        if not os.environ.get("LLM_API_KEY", "").strip():
            detail = (
                "These cards are a fallback ranking by rating and number of votes. "
                "Live explanations need an API key."
            )
        else:
            detail = (
                "These cards are a fallback ranking by rating and number of votes. "
                "The model response could not be used."
            )
        parts.append(_notice("info", "Offline ranking", detail))
    if not result.items:
        parts.append(_empty_notice(preferences))
    else:
        parts.extend(_card(item) for item in result.items)
    parts.append("</section>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _empty_notice(preferences: UserPreferences) -> str:
    if preferences.cuisine:
        cuisine_text = f"cuisine {preferences.cuisine}"
    else:
        cuisine_text = "any cuisine"
    detail = (
        "No restaurants to show for "
        f"location {preferences.location}, "
        f"{cuisine_text}, "
        f"budget {preferences.budget}, "
        f"and minimum rating {preferences.min_rating}."
    )
    return _notice("empty", "No exact dining matches", detail)


def _notice(kind: str, title: str, detail: str) -> str:
    return (
        f'<div class="notice notice-{kind}">'
        '<span class="notice-icon" aria-hidden="true">✦</span>'
        "<div>"
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(detail)}</p>"
        "</div></div>"
    )


def _card(item) -> str:
    cuisines = [part.strip() for part in item.cuisines.split(",") if part.strip()]
    if not cuisines:
        cuisines = ["Unavailable"]
    pills = "".join(f'<span class="pill">{html.escape(name)}</span>' for name in cuisines)
    rating = "unavailable" if item.rating is None else f"{item.rating:.1f}"
    if item.cost_for_two is None:
        cost = "Cost unavailable"
    else:
        cost = f"₹{item.cost_for_two:,} for two"
    explanation = item.explanation.strip()
    why = f'<p class="rec-why">{html.escape(explanation)}</p>' if explanation else ""
    link = _restaurant_link(item.url)
    return (
        '<article class="rec-card">'
        '<div class="rec-top">'
        '<div class="rec-name">'
        f'<span class="rec-rank">{item.rank}</span>'
        f"<h2>{html.escape(item.name)}</h2>"
        "</div>"
        '<div class="rec-meta">'
        f'<span class="rec-rating">★ {html.escape(rating)}</span>'
        '<span class="rec-dot">•</span>'
        f"<span>{html.escape(cost)}</span>"
        "</div></div>"
        f'<div class="pills">{pills}</div>'
        f"{why}{link}</article>"
    )


def _restaurant_link(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    href = html.escape(cleaned, quote=True)
    return (
        f'<a class="rec-link" href="{href}" target="_blank" rel="noopener noreferrer" '
        'style="color:#ffc665;text-decoration:none;font-weight:600;font-size:13px;">'
        "Open restaurant →</a>"
    )


def _validation_message(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"]) or "form"
        lines.append(f"{field}: {error['msg']}")
    return "\n".join(lines)


def _field(label: str, note: str, *, required: bool = False) -> None:
    note_class = "field-note required" if required else "field-note"
    st.markdown(
        '<div class="field-head">'
        f"<span>{html.escape(label)}</span>"
        f'<span class="{note_class}">{html.escape(note)}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _budget_label(value: str) -> str:
    labels = {"low": "Low  ₹", "medium": "Medium  ₹₹", "high": "High  ₹₹₹"}
    return labels.get(value, value)


service = RecommendationService()

st.set_page_config(page_title="Restaurant recommendations", layout="centered")
st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
st.markdown(
    """
    <header class="table-top">
      <div class="table-brand">
        <span class="table-mark" aria-hidden="true">✦</span>
        <span class="table-word">Table</span>
      </div>
      <nav class="table-nav" aria-label="Table">
        <span class="nav-current">Concierge</span>
        <span class="nav-muted">Journal</span>
        <span class="nav-avatar" aria-hidden="true">☺</span>
      </nav>
    </header>
    <section class="hero">
      <div class="eyebrow">Curated gastronomy</div>
      <h1>Restaurant recommendations</h1>
      <p>Choose a neighborhood, budget, and minimum rating. Cuisine is optional.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

try:
    locations = service.location_choices()
except (DatasetDownloadError, CacheReadError) as exc:
    st.markdown(
        _notice("error", "The restaurant cache could not be read.", str(exc)),
        unsafe_allow_html=True,
    )
    st.stop()

if not locations:
    st.markdown(
        _notice("error", "The restaurant cache has no locations to choose from.", ""),
        unsafe_allow_html=True,
    )
    st.stop()

with st.form("preferences"):
    _field("Neighborhood", "Required", required=True)
    default_location = locations.index("Banashankari") if "Banashankari" in locations else 0
    location = st.selectbox(
        "Location",
        locations,
        index=default_location,
        label_visibility="collapsed",
    )
    _field("Budget tier", "")
    budget = st.segmented_control(
        "Budget",
        ["low", "medium", "high"],
        default="medium",
        required=True,
        format_func=_budget_label,
        label_visibility="collapsed",
        width="stretch",
    )
    _field("Cuisine preference", "Optional")
    cuisine = st.text_input(
        "Cuisine",
        placeholder="Italian",
        help="Leave this blank to include every cuisine.",
        label_visibility="collapsed",
    )
    st.caption("Leave blank to include every cuisine.")
    _field("Minimum rating", "★")
    min_rating = st.slider(
        "Minimum rating",
        min_value=0.0,
        max_value=5.0,
        value=3.5,
        step=0.1,
        format="%.1f",
        label_visibility="collapsed",
    )
    _field("Specific desires or atmosphere", "Optional")
    additional_preferences = st.text_area(
        "Additional preferences",
        placeholder="family-friendly, quick service",
        label_visibility="collapsed",
        height=110,
    )
    submitted = st.form_submit_button(
        "Find restaurants",
        type="primary",
        icon=":material/arrow_forward:",
        icon_position="right",
    )
    st.markdown(
        '<div class="ready-line"><span class="ready-dot"></span>'
        "<span>Concierge ready · Live Bangalore directory</span></div>",
        unsafe_allow_html=True,
    )

if submitted:
    if budget not in {"low", "medium", "high"}:
        st.markdown(
            _notice("error", "Choose a budget tier.", "Budget must be low, medium, or high."),
            unsafe_allow_html=True,
        )
    else:
        try:
            preferences = UserPreferences(
                location=location,
                budget=budget,
                cuisine=cuisine,
                min_rating=float(min_rating),
                additional_preferences=additional_preferences,
            )
        except ValidationError as exc:
            st.markdown(
                _notice("error", "Check the form.", _validation_message(exc)),
                unsafe_allow_html=True,
            )
        else:
            try:
                with st.spinner("Finding restaurants…"):
                    result = service.recommend(preferences)
            except (DatasetDownloadError, CacheReadError) as exc:
                st.markdown(
                    _notice("error", "The restaurant cache could not be read.", str(exc)),
                    unsafe_allow_html=True,
                )
            else:
                _show_result(result, preferences)
else:
    st.markdown(
        """
        <aside class="protocol">
          <div class="protocol-copy">
            <span class="protocol-icon" aria-hidden="true">✦</span>
            <div>
              <strong>Private Gastronomic Protocol</strong>
              <p>Recommendations are weighted by ambiance density, acoustic balance, and provenance.</p>
            </div>
          </div>
          <span class="protocol-lock">Unsponsored</span>
        </aside>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <footer class="table-footer">
      <span>Table AI · Gastronomy &amp; Dining Concierge</span>
      <span>© Curated Discretion</span>
    </footer>
    """,
    unsafe_allow_html=True,
)
