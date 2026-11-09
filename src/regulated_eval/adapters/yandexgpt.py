"""YandexGPT adapter.

Covers FR-003, TM-08, ADR-002.
"""

from __future__ import annotations

import logging

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

# YandexGPT pricing (per 1M tokens, RUB) — subject to change
_YANDEXGPT_PRICING = {
    "yandexgpt-lite": {"input": 300, "output": 360},
    "yandexgpt-pro": {"input": 600, "output": 720},
}


class YandexGPTAdapter(BaseAdapter):
    """Adapter for YandexGPT API.

    Uses httpx for HTTP requests with retry and exponential backoff.
    """

    BASE_URL = "https://llm.api.cloud.yandex.net/llm/v2/completions"

    def __init__(
        self,
        model: str = "yandexgpt-lite",
        config: Config | None = None,
    ) -> None:
        """Initialize YandexGPT adapter.

        Args:
            model: Model name (yandexgpt-lite, yandexgpt-pro).
            config: Optional Config object.
        """
        self._model = model
        self._config = config or Config()
        self._api_key: str | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_api_key(self) -> str:
        """Get YandexGPT API key from config."""
        if self._api_key is None:
            try:
                self._api_key = self._config.get_api_key("yandexgpt")
            except ValueError as e:
                raise MissingCredentials(str(e))
        return self._api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to YandexGPT and return the response.

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

        payload = {
            "model": model,
            "completionOptions": {
                "stream": False,
                "temperature": request.temperature,
                "maxTokens": request.max_tokens,
            },
            "message": [
                {
                    "role": "user",
                    "text": request.prompt,
                }
            ],
        }

        headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
            "X-Batch-Id": request.metadata.get("batch_id", ""),
            "X-Correlation-Id": request.metadata.get("correlation_id", ""),
        }

        @get_retry_decorator(
            max_retries=self._config.max_retries,
            base_delay_ms=self._config.retry_base_delay_ms,
            max_delay_ms=self._config.retry_max_delay_ms,
        )
        async def _call_api() -> httpx.Response:
            response = await client.post(
                self.BASE_URL,
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
            logger.error("YandexGPT error: %d - %s", response.status_code, response.text)
            return LLMResponse(
                text="",
                model=model,
                error=f"HTTP {response.status_code}: {response.text}",
            )

        data = response.json()
        result = data.get("result", {})
        text = result.get("text", "")
        tokens_input = result.get("tokens", {}).get("tokensCount", 0)
        tokens_output = result.get("tokens", {}).get("completionTokens", 0)

        return LLMResponse(
            text=text,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            finish_reason=result.get("status", ""),
        )

    def provider(self) -> str:
        """Return the provider name."""
        return "yandexgpt"

    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def estimate_cost(self, tokens_input: int, tokens_output: int) -> float | None:
        """Estimate cost in RUB."""
        pricing = _YANDEXGPT_PRICING.get(self._model)
        if pricing is None:
            return None
        cost = (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000
        return round(cost, 4)

    @property
    def is_foreign(self) -> bool:
        """YandexGPT is a Russian provider — not foreign."""
        return False

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
