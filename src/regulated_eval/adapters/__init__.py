# Adapters package

"""LLM provider adapters for Regulated LLM Eval Framework.

Covers FR-003, NFR-008.

Adapters:
- YandexGPT: Russian LLM (not foreign)
- GigaChat: Russian LLM (not foreign)
- OpenAICompatible: OpenAI-compatible API (foreign, requires opt-in)
"""

from __future__ import annotations

from regulated_eval.adapters.base import BaseAdapter, LLMRequest, LLMResponse
from regulated_eval.adapters.gigachat import GigaChatAdapter
from regulated_eval.adapters.openai_compat import OpenAICompatibleAdapter
from regulated_eval.adapters.retry import RateLimitError, RateLimitExhausted, check_rate_limit
from regulated_eval.adapters.yandexgpt import YandexGPTAdapter
from regulated_eval.config import Config

__all__ = [
    "BaseAdapter",
    "LLMRequest",
    "LLMResponse",
    "YandexGPTAdapter",
    "GigaChatAdapter",
    "OpenAICompatibleAdapter",
    "RateLimitError",
    "RateLimitExhausted",
    "check_rate_limit",
]


def create_adapter(
    provider: str,
    model: str = "",
    config: Config | None = None,
    base_url: str | None = None,
) -> BaseAdapter:
    """Create an adapter by provider name.

    Args:
        provider: Provider name (yandexgpt, gigachat, openai_compat).
        model: Model name (uses default if empty).
        config: Optional Config object.
        base_url: Optional base URL for openai_compat.

    Returns:
        Configured BaseAdapter instance.

    Raises:
        ValueError: If provider is not supported.
    """
    from regulated_eval.config import Config  # noqa: PLC0414

    cfg = config or Config()

    if provider == "yandexgpt":
        model_name = model or "yandexgpt-lite"
        return YandexGPTAdapter(model=model_name, config=cfg)

    elif provider == "gigachat":
        model_name = model or "gigachat"
        return GigaChatAdapter(model=model_name, config=cfg)

    elif provider == "openai_compat":
        model_name = model or "gpt-4o-mini"
        url = base_url or cfg.openai_base_url
        return OpenAICompatibleAdapter(model=model_name, base_url=url, config=cfg)

    else:
        supported = ", ".join(["yandexgpt", "gigachat", "openai_compat"])
        raise ValueError(f"Unsupported provider: {provider}. Supported: {supported}")
