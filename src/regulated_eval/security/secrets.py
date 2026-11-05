"""Secrets management for API keys.

Covers FR-013, NFR-SEC-004, TM-03.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Mask for API keys in logs
_API_KEY_MASK = "***"


def get_api_key(provider: str, env_prefix: str = "") -> str | None:
    """Get API key for a provider from environment.

    Keys are read from environment variables:
    - {env_prefix}{PROVIDER}_API_KEY
    - e.g., YANDEXGPT_API_KEY, GIGACHAT_API_KEY

    Args:
        provider: Provider name (yandexgpt, gigachat, openai_compat).
        env_prefix: Optional environment variable prefix.

    Returns:
        API key string or None if not set.
    """
    env_var = f"{env_prefix}{provider.upper()}_API_KEY"
    key = os.environ.get(env_var)

    if key:
        logger.debug("API key loaded for provider '%s' from env '%s'", provider, env_var)
    else:
        logger.debug("API key not found for provider '%s' (env: '%s')", provider, env_var)

    return key


def mask_api_key(key: str) -> str:
    """Mask an API key for safe logging.

    Args:
        key: API key to mask.

    Returns:
        Masked key (e.g., '***').
    """
    return _API_KEY_MASK


def log_adapter_init(provider: str, key: str | None, **extra: Any) -> None:
    """Log adapter initialization with masked key.

    Never logs the actual API key value.

    Args:
        provider: Provider name.
        key: API key (will be masked).
        **extra: Additional context to log.
    """
    masked = mask_api_key(key) if key else None
    context = {"provider": provider, "api_key": masked, **extra}
    logger.info("Adapter initialized: %s", context)


def validate_api_keys(config: dict[str, str | None]) -> list[str]:
    """Validate that required API keys are set.

    Args:
        config: Dict of provider -> api_key.

    Returns:
        List of missing provider names.
    """
    missing = []
    for provider, key in config.items():
        if not key:
            missing.append(provider)
            logger.warning("Missing API key for provider: %s", provider)
    return missing


def sanitize_for_logging(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a dict by masking API keys and secrets.

    Recursively masks values for known secret key names.

    Args:
        data: Dict to sanitize.

    Returns:
        Sanitized dict with masked secrets.
    """
    secret_keys = {"api_key", "apikey", "secret", "token", "authorization"}
    sanitized = {}

    for key, value in data.items():
        lower_key = key.lower()
        if any(sk in lower_key for sk in secret_keys):
            sanitized[key] = _API_KEY_MASK
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        else:
            sanitized[key] = value

    return sanitized
