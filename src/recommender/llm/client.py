"""Groq chat completion through the OpenAI SDK."""

from __future__ import annotations

from openai import OpenAI

from recommender.config import Settings, load_settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
_MAX_COMPLETION_TOKENS = 700


def completion_token_budget(top_n: int) -> int:
    """Cap one reply so a request stays inside the free token budget.

    The cap covers a one-sentence summary, one sentence per result, and a
    small allowance for the model's low reasoning setting.
    """
    count = top_n if top_n > 0 else 1
    return min(_MAX_COMPLETION_TOKENS, 90 * count + 180)


class LLMClient:
    """One JSON chat completion. The caller parses the returned string."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = load_settings() if settings is None else settings

    def complete(self, messages: list[dict[str, str]], *, max_tokens: int | None = None) -> str:
        """Send messages to Groq and return the message content.

        Timeouts and HTTP errors from the provider propagate.
        ``max_tokens`` limits the completion. Reasoning effort stays low so
        hidden reasoning does not consume the free token budget.
        """
        settings = self._settings
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or GROQ_BASE_URL,
            timeout=settings.llm_timeout_seconds,
        )
        response = client.chat.completions.create(
            model=settings.llm_model or GROQ_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=completion_token_budget(5) if max_tokens is None else max_tokens,
            response_format={"type": "json_object"},
            extra_body={"reasoning_effort": "low"},
        )
        content = response.choices[0].message.content
        return "" if content is None else content
