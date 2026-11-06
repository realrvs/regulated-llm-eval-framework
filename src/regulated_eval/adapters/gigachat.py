"""GigaChat adapter.

Covers FR-003, TM-08, ADR-002.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from regulated_eval.adapters.base import BaseAdapter, LLMRequest, LLMResponse
from regulated_eval.adapters.retry import (
    RateLimitError,
    check_rate_limit,
    get_retry_decorator,
)
from regulated_eval.config import Config
from regulated_eval.exceptions import MissingCredentials

logger = logging.getLogger(__name__)

# GigaChat pricing (per 1M tokens, RUB) — subject to change
_GIGACHAT_PRICING = {
    "gigachat": {"input": 300, "output": 360},
    "gigachat-pro": {"input": 600, "output": 720},
    "gigachat-max": {"input": 900, "output": 1080},
}


class GigaChatAdapter(BaseAdapter):
    """Adapter for GigaChat API.

    Uses httpx for HTTP requests with retry and exponential backoff.
    Authenticates via OAuth token from GigaChat API.
    """

    BASE_URL = "https://gigachat.devices.sber.ru/api/v1/chat/completions"
    TOKEN_URL = "https://gigachat.devices.sber.ru/api/v2/oauth"

    def __init__(
        self,
        model: str = "gigachat",
        config: Config | None = None,
        scope: str = "GIGACHAT_API_PERS",
    ) -> None:
        """Initialize GigaChat adapter.

        Args:
            model: Model name (gigachat, gigachat-pro, gigachat-max).
            config: Optional Config object.
            scope: OAuth scope for authentication.
        """
        self._model = model
        self._config = config or Config()
        self._scope = scope
        self._api_key: str | None = None
        self._access_token: str | None = None
        self._client: httpx.AsyncClient | None = None

    def _get_api_key(self) -> str:
        """Get GigaChat API key from config."""
        if self._api_key is None:
            try:
                self._api_key = self._config.get_api_key("gigachat")
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

    async def _get_access_token(self) -> str:
        """Get or refresh GigaChat OAuth access token.

        Returns:
            OAuth access token string.
        """
        if self._access_token is not None:
            return self._access_token

        api_key = self._get_api_key()
        client = self._get_client()

        try:
            response = await client.post(
                self.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {api_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "RqUID": self._generate_request_id(),
                },
                data={"scope": self._scope},
            )

            if response.status_code != 200:
                logger.error(
                    "GigaChat token error: %d - %s",
                    response.status_code,
                    response.text,
                )
                raise MissingCredentials(
                    f"GigaChat token request failed: {response.status_code}"
                )

            data = response.json()
            self._access_token = data.get("access_token", "")
            return self._access_token

        except httpx.HTTPError as e:
            raise MissingCredentials(f"GigaChat token request failed: {e}")

    @staticmethod
    def _generate_request_id() -> str:
        """Generate a unique request ID for GigaChat API."""
        import uuid

        return str(uuid.uuid4())

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a prompt to GigaChat and return the response.

        Args:
            request: LLM request with prompt, model, etc.

        Returns:
            LLMResponse with text, tokens, latency, etc.

        Raises:
            MissingCredentials: If API key is not set.
            RateLimitExhausted: If all retry attempts are exhausted.
        """
        access_token = await self._get_access_token()
        client = self._get_client()

        model = request.model or self._model

        payload = {
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

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "RqUID": self._generate_request_id(),
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
            logger.error("GigaChat error: %d - %s", response.status_code, response.text)
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
        return "gigachat"

    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    def estimate_cost(self, tokens_input: int, tokens_output: int) -> float | None:
        """Estimate cost in RUB."""
        pricing = _GIGACHAT_PRICING.get(self._model)
        if pricing is None:
            return None
        cost = (tokens_input * pricing["input"] + tokens_output * pricing["output"]) / 1_000_000
        return round(cost, 4)

    @property
    def is_foreign(self) -> bool:
        """GigaChat is a Russian provider — not foreign."""
        return False

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
