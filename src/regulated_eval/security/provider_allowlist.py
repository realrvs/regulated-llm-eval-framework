"""Provider allowlist for 152-FZ compliance.

Covers NFR-SEC-001, TM-02, TM-06, TM-08, TM-14, ADR-002.

Provides:
- ProviderAllowlist: manages allowed foreign providers
- Double opt-in mechanism (CLI flags + env + interactive)
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ProviderType(StrEnum):
    """Classification of LLM providers."""

    RUSSIAN = "russian"  # Data residency in Russia, 152-FZ compliant
    FOREIGN = "foreign"  # Requires opt-in


# Russian providers (data residency in Russia)
RUSSIAN_PROVIDERS: dict[str, dict[str, Any]] = {
    "yandexgpt": {
        "type": ProviderType.RUSSIAN,
        "display_name": "YandexGPT",
        "allowed": True,
    },
    "gigachat": {
        "type": ProviderType.RUSSIAN,
        "display_name": "GigaChat",
        "allowed": True,
    },
}

# Foreign providers (require explicit opt-in)
FOREIGN_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai_compat": {
        "type": ProviderType.FOREIGN,
        "display_name": "OpenAI-compatible",
        "allowed": False,  # Requires opt-in
        "requires_ack_152fz": True,
    },
}

ALL_PROVIDERS: dict[str, dict[str, Any]] = {**RUSSIAN_PROVIDERS, **FOREIGN_PROVIDERS}


class ProviderAllowlist:
    """Manages allowed LLM providers with 152-FZ compliance.

    Provides double opt-in for foreign providers:
    1. Environment flag (REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER)
    2. 152-FZ acknowledgment (REGULATED_EVAL_ACK_152FZ)
    """

    def __init__(
        self,
        allow_foreign: bool = False,
        acknowledge_152fz: bool = False,
        custom_allowlist: list[str] | None = None,
    ) -> None:
        """Initialize provider allowlist.

        Args:
            allow_foreign: Whether foreign providers are allowed.
            acknowledge_152fz: Whether 152-FZ implications are acknowledged.
            custom_allowlist: Additional custom providers to allow.
        """
        self._allow_foreign = allow_foreign
        self._acknowledge_152fz = acknowledge_152fz
        self._custom_allowlist = custom_allowlist or []
        self._allowed_providers: set[str] = set(RUSSIAN_PROVIDERS.keys())

        # Add custom providers
        for provider in self._custom_allowlist:
            if provider not in ALL_PROVIDERS:
                logger.warning("Unknown custom provider: %s", provider)

    def is_provider_allowed(self, provider: str) -> bool:
        """Check if a provider is allowed for use.

        Args:
            provider: Provider name (e.g. 'yandexgpt', 'openai_compat').

        Returns:
            True if the provider is allowed.
        """
        # Russian providers are always allowed
        if provider in RUSSIAN_PROVIDERS:
            return True

        # Foreign providers require double opt-in
        if provider in FOREIGN_PROVIDERS:
            return self._allow_foreign and self._acknowledge_152fz

        # Custom providers
        return provider in self._custom_allowlist

    def get_provider_info(self, provider: str) -> dict[str, Any] | None:
        """Get information about a provider.

        Args:
            provider: Provider name.

        Returns:
            Provider info dict, or None if not found.
        """
        if provider in ALL_PROVIDERS:
            info = dict(ALL_PROVIDERS[provider])
            info["allowed"] = self.is_provider_allowed(provider)
            return info

        if provider in self._custom_allowlist:
            return {
                "type": ProviderType.FOREIGN,
                "display_name": provider,
                "allowed": True,
            }

        return None

    def validate_provider(self, provider: str) -> tuple[bool, str]:
        """Validate a provider for use.

        Args:
            provider: Provider name.

        Returns:
            Tuple of (allowed, error_message).
        """
        if provider not in ALL_PROVIDERS and provider not in self._custom_allowlist:
            supported = ", ".join(ALL_PROVIDERS.keys())
            return False, f"Unknown provider: {provider}. Supported: {supported}"

        if not self.is_provider_allowed(provider):
            provider_info = FOREIGN_PROVIDERS.get(provider, {})
            if provider_info.get("requires_ack_152fz"):
                return False, (
                    f"Foreign provider '{provider}' requires: "
                    "--allow-foreign-provider + --i-understand-152fz flags, "
                    "or env vars REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER=true and "
                    "REGULATED_EVAL_ACK_152FZ=true"
                )
            return False, f"Provider '{provider}' is not allowed"

        return True, ""

    @property
    def allow_foreign(self) -> bool:
        """Whether foreign providers are allowed."""
        return self._allow_foreign

    @allow_foreign.setter
    def allow_foreign(self, value: bool) -> None:
        """Set foreign provider allowance.

        Args:
            value: Whether to allow foreign providers.
        """
        self._allow_foreign = value
        logger.info("Foreign provider allowance set to: %s", value)

    @property
    def acknowledge_152fz(self) -> bool:
        """Whether 152-FZ is acknowledged."""
        return self._acknowledge_152fz

    @acknowledge_152fz.setter
    def acknowledge_152fz(self, value: bool) -> None:
        """Set 152-FZ acknowledgment.

        Args:
            value: Whether to acknowledge 152-FZ.
        """
        self._acknowledge_152fz = value
        logger.info("152-FZ acknowledgment set to: %s", value)

    @property
    def allowed_providers(self) -> list[str]:
        """List of currently allowed providers."""
        allowed = list(RUSSIAN_PROVIDERS.keys())
        if self._allow_foreign and self._acknowledge_152fz:
            allowed.extend(FOREIGN_PROVIDERS.keys())
        allowed.extend(self._custom_allowlist)
        return allowed

    def list_providers(self) -> list[dict[str, Any]]:
        """List all known providers with their status.

        Returns:
            List of provider info dicts.
        """
        providers = []
        for name, info in ALL_PROVIDERS.items():
            providers.append(
                {
                    "name": name,
                    "display_name": info["display_name"],
                    "type": info["type"].value,
                    "allowed": self.is_provider_allowed(name),
                }
            )
        return providers
