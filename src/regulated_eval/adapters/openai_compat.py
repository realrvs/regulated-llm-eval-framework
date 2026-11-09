"""OpenAI-compatible adapter with opt-in for 152-FZ compliance.

Covers FR-003, NFR-SEC-001, TM-02, TM-06, TM-08, TM-14, ADR-002.

This adapter is marked as foreign (is_foreign=True) and requires
explicit opt-in via --allow-foreign-provider flag or
REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER env var.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx  # type: ignore[import-untyped]

from regulated_eval.adapters.base import BaseAdapter, LLMRequest, LLMResponse
from regulated_eval.adapters.retry import (
    RateLimitError,
    check_rate_limit,
    get_retry_decorator,
)
from regulated_eval.config import Config
from regulated_eval.exceptions import MissingCredentials

logger = logging.getLogger(__name__)

# OpenAI-compatible pricing (per 1M tokens, RUB) — approximate
_OPENAI_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2500, "output": 3500},
    "gpt-4o-mini": {"input": 300, "output": 600},
    "gpt-4-turbo": {"input": 1500, "output": 3000},
    "claude-3-opus": {"input": 3000, "output": 15000},
    "claude-3-sonnet": {"input": 600, "output": 3000},
}


class OpenAICompatibleAdapter(BaseAdapter):
    """Adapter for OpenAI-compatible APIs.

    Supports any provider that implements the OpenAI chat completions API:
    - OpenAI (gpt-4, gpt-3.5-turbo)
    - Claude (via proxy)
    - Local models (Ollama, vLLM)
    - Any other OpenAI-compatible endpoint

    This adapter is marked as FOREIGN and requires explicit opt-in
    for 152-FZ compliance.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        config: Config | None = None,
    ) -> None:
        """Initialize OpenAI-compatible adapter.

        Args:
            model: Model name.
            base_url: API base URL.
            config: Optional Config object.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._config = config or Config()
        self._api_key: str | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_api_key(self) -> str:
        """Get API key from config."""
        if self._api_key is None:
            try:
                self._api_key = self._config.get_api_key("openai_compat")
            except ValueError as e:
                raise MissingCredentials(str(e))
        return self._api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to the OpenAI-compatible API.

        Args:
            request: LLM request with prompt, model, etc.

        Returns:
            LLMResponse with text, tokens, latency, etc.

        Raises:
            MissingCredentials: If API key is not set.
            RateLimitExhausted: If all retry attempts are exhausted.
        """
        api_key = self._get_api_key()
        client = self._get_client()

        model = request.model or self._model

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": request.prompt,
                }
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        @get_retry_decorator(
            max_retries=self._config.max_retries,
            base_delay_ms=self._config.retry_base_delay_ms,
            max_delay_ms=self._config.retry_max_delay_ms,
        )
        async def _call_api() -> httpx.Response:
            response = await client.post(
                "/chat/completions",
                json=payload,
                headers=headers,
            )
            check_rate_limit(response)
            return response

        try:
            response = await _call_api()
        except RateLimitError as e:
            raise RateLimitError(str(e))

        if response.status_code != 200:
            logger.error(
                "OpenAI-compatible error (%s): %d - %s",
                self._base_url,
                response.status_code,
                response.text,
            )
            return LLMResponse(
                text="",
                model=model,
                error=f"HTTP {response.status_code}: {response.text}",
            )

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            text=text,
            model=model,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
        )

    def provider(self) -> str:
        """Return the provider name."""
        return "openai_compat"

    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def estimate_cost(self, tokens_input: int, tokens_output: int) -> float | None:
        """Estimate cost in RUB."""
        pricing = _OPENAI_PRICING.get(self._model)
        if pricing is None:
            return None
        cost = (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000
        return round(cost, 4)

    @property
    def is_foreign(self) -> bool:
        """OpenAI-compatible adapters are considered foreign for 152-FZ."""
        return True

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
