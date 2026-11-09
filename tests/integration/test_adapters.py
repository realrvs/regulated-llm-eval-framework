"""Integration tests for adapters and retry logic.

Covers T-1105, T-1106, FR-003, NFR-008.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from regulated_eval.adapters.base import LLMRequest
from regulated_eval.adapters.retry import (
    RateLimitError,
    RateLimitExhausted,
    check_rate_limit,
    retry_with_backoff,
)


class TestRetryLogic:
    """Integration tests for retry logic."""

    def test_check_rate_limit_no_error(self) -> None:
        """Test no rate limit error on 200."""
        response = MagicMock()
        response.status_code = 200
        # Should not raise
        check_rate_limit(response)

    def test_check_rate_limit_429_raises(self) -> None:
        """Test 429 raises RateLimitError."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "5"}

        with pytest.raises(RateLimitError, match="Retry-After"):
            check_rate_limit(response)

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self) -> None:
        """Test retry succeeds after transient failures."""
        call_count = 0

        async def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limited")
            return "success"

        result = await retry_with_backoff(
            flaky_func,
            max_retries=5,
            base_delay_ms=1,
            max_delay_ms=10,
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self) -> None:
        """Test RateLimitExhausted after max retries."""

        async def always_fail() -> str:
            raise RateLimitError("Always rate limited")

        with pytest.raises(RateLimitExhausted, match="All 3 retry attempts"):
            await retry_with_backoff(
                always_fail,
                max_retries=3,
                base_delay_ms=1,
                max_delay_ms=10,
            )


class TestYandexGPTAdapterIntegration:
    """Integration tests for YandexGPT adapter with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        """Test successful generation with mocked HTTP response."""
        from regulated_eval.adapters.yandexgpt import YandexGPTAdapter  # noqa: PLC0414

        adapter = YandexGPTAdapter(model="yandexgpt-lite")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "text": "Ответ на вопрос",
                "tokens": {"tokensCount": 100, "completionTokens": 50},
            }
        }

        mock_session = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.aclose = AsyncMock()

        with patch("httpx.AsyncClient", create=True) as mock_client_cls:
            mock_client_cls.return_value = mock_session

            request = LLMRequest(
                prompt="Тестовый вопрос",
                model="yandexgpt-lite",
                temperature=0.0,
                max_tokens=100,
            )

            # Mock get_api_key to avoid missing credentials
            with patch.object(adapter, "_get_api_key", return_value="test_key"):
                response = await adapter.generate(request)

        assert response.text == "Ответ на вопрос"
        assert response.tokens_input == 100
        assert response.tokens_output == 50
        assert response.model == "yandexgpt-lite"
        assert response.error is None

    @pytest.mark.asyncio
    async def test_generate_error_response(self) -> None:
        """Test handling of API error response."""
        from regulated_eval.adapters.yandexgpt import YandexGPTAdapter  # noqa: PLC0414

        adapter = YandexGPTAdapter(model="yandexgpt-lite")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_session = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.aclose = AsyncMock()

        with patch("httpx.AsyncClient", create=True) as mock_client_cls:
            mock_client_cls.return_value = mock_session

            request = LLMRequest(
                prompt="Тестовый вопрос",
                model="yandexgpt-lite",
            )

            with patch.object(adapter, "_get_api_key", return_value="test_key"):
                response = await adapter.generate(request)

        assert response.text == ""
        assert response.error is not None
        assert "500" in response.error

    def test_estimate_cost(self) -> None:
        """Test cost estimation for YandexGPT."""
        from regulated_eval.adapters.yandexgpt import YandexGPTAdapter  # noqa: PLC0414

        adapter = YandexGPTAdapter(model="yandexgpt-lite")
        cost = adapter.estimate_cost(1000, 500)
        # yandexgpt-lite: input=300, output=360 per 1M tokens
        expected = (1000 * 300 + 500 * 360) / 1_000_000
        assert cost == round(expected, 4)

    def test_is_foreign(self) -> None:
        """Test YandexGPT is not foreign."""
        from regulated_eval.adapters.yandexgpt import YandexGPTAdapter  # noqa: PLC0414

        adapter = YandexGPTAdapter()
        assert adapter.is_foreign is False
        assert adapter.provider() == "yandexgpt"


class TestGigaChatAdapterIntegration:
    """Integration tests for GigaChat adapter with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        """Test successful GigaChat generation."""
        from regulated_eval.adapters.gigachat import GigaChatAdapter  # noqa: PLC0414

        adapter = GigaChatAdapter(model="gigachat")

        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {"access_token": "mock_token"}

        mock_chat_response = MagicMock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {
            "choices": [{"message": {"content": "GigaChat ответ"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 25},
        }

        mock_session = MagicMock()
        mock_session.post = AsyncMock(side_effect=[mock_token_response, mock_chat_response])
        mock_session.aclose = AsyncMock()

        with patch("httpx.AsyncClient", create=True) as mock_client_cls:
            mock_client_cls.return_value = mock_session

            request = LLMRequest(
                prompt="Тестовый вопрос",
                model="gigachat",
            )

            with patch.object(adapter, "_get_api_key", return_value="test_key"):
                response = await adapter.generate(request)

        assert response.text == "GigaChat ответ"
        assert response.tokens_input == 50
        assert response.tokens_output == 25

    def test_is_foreign(self) -> None:
        """Test GigaChat is not foreign."""
        from regulated_eval.adapters.gigachat import GigaChatAdapter  # noqa: PLC0414

        adapter = GigaChatAdapter()
        assert adapter.is_foreign is False
        assert adapter.provider() == "gigachat"


class TestOpenAICompatibleAdapterIntegration:
    """Integration tests for OpenAI-compatible adapter."""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        """Test successful OpenAI-compatible generation."""
        from regulated_eval.adapters.openai_compat import OpenAICompatibleAdapter  # noqa: PLC0414

        adapter = OpenAICompatibleAdapter(
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenAI ответ"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        mock_session = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.aclose = AsyncMock()

        with patch("httpx.AsyncClient", create=True) as mock_client_cls:
            mock_client_cls.return_value = mock_session

            request = LLMRequest(
                prompt="Test question",
                model="gpt-4o-mini",
            )

            with patch.object(adapter, "_get_api_key", return_value="test_key"):
                response = await adapter.generate(request)

        assert response.text == "OpenAI ответ"
        assert response.model == "gpt-4o-mini"

    def test_is_foreign(self) -> None:
        """Test OpenAI-compatible is foreign."""
        from regulated_eval.adapters.openai_compat import OpenAICompatibleAdapter  # noqa: PLC0414

        adapter = OpenAICompatibleAdapter()
        assert adapter.is_foreign is True
        assert adapter.provider() == "openai_compat"

    def test_estimate_cost(self) -> None:
        """Test cost estimation for OpenAI-compatible."""
        from regulated_eval.adapters.openai_compat import OpenAICompatibleAdapter  # noqa: PLC0414

        adapter = OpenAICompatibleAdapter(model="gpt-4o-mini")
        cost = adapter.estimate_cost(1000, 500)
        # gpt-4o-mini: input=300, output=600 per 1M tokens
        expected = (1000 * 300 + 500 * 600) / 1_000_000
        assert cost == round(expected, 4)


class TestAdapterFactoryIntegration:
    """Integration tests for adapter factory."""

    def test_create_yandexgpt(self) -> None:
        """Test YandexGPT adapter creation."""
        from regulated_eval.adapters import create_adapter  # noqa: PLC0414
        from regulated_eval.config import Config  # noqa: PLC0414

        adapter = create_adapter("yandexgpt", config=Config())
        assert adapter.provider() == "yandexgpt"
        assert adapter.is_foreign is False

    def test_create_gigachat(self) -> None:
        """Test GigaChat adapter creation."""
        from regulated_eval.adapters import create_adapter  # noqa: PLC0414
        from regulated_eval.config import Config  # noqa: PLC0414

        adapter = create_adapter("gigachat", config=Config())
        assert adapter.provider() == "gigachat"
        assert adapter.is_foreign is False

    def test_create_openai_compat(self) -> None:
        """Test OpenAI-compatible adapter creation."""
        from regulated_eval.adapters import create_adapter  # noqa: PLC0414
        from regulated_eval.config import Config  # noqa: PLC0414

        adapter = create_adapter("openai_compat", config=Config())
        assert adapter.provider() == "openai_compat"
        assert adapter.is_foreign is True

    def test_create_unknown_raises(self) -> None:
        """Test unknown provider raises ValueError."""
        from regulated_eval.adapters import create_adapter  # noqa: PLC0414
        from regulated_eval.config import Config  # noqa: PLC0414

        with pytest.raises(ValueError, match="Unsupported provider"):
            create_adapter("unknown_provider", config=Config())
