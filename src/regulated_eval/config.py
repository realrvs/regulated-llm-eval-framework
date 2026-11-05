"""Configuration for Regulated LLM Eval Framework.

Uses pydantic-settings for env-based config with defaults.
Covers FR-013, NFR-SEC-001.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Global configuration loaded from environment variables.

    Priority: env > defaults. Secrets are never logged.
    """

    model_config = SettingsConfigDict(
        env_prefix="REGULATED_EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Provider settings ----
    yandexgpt_api_key: str = ""
    gigachat_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    allow_foreign_provider: bool = False
    acknowledge_152fz: bool = False

    # ---- Observability ----
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    otel_sampling_ratio: float = 0.1
    otel_sampling_error_ratio: float = 1.0

    # ---- PII redaction ----
    pii_redaction_enabled: bool = True
    use_presidio: bool = False  # False = regex-only (MVP)

    # ---- Injection filter ----
    injection_filter_enabled: bool = True

    # ---- Annotation chain ----
    annotation_chain_enabled: bool = True

    # ---- Pipeline ----
    default_parallelism: int = 8
    default_seed: int = 42
    max_parallelism: int = 32
    min_parallelism: int = 1

    # ---- Judge ----
    default_judge_model: str = "yandexgpt"
    default_calibration_threshold: float = 0.6
    default_ci_level: float = 0.95

    # ---- Rate limiting ----
    max_retries: int = 5
    retry_base_delay_ms: int = 1000
    retry_max_delay_ms: int = 30000

    # ---- Logging ----
    log_level: str = "info"

    @property
    def is_foreign_provider_allowed(self) -> bool:
        """Check if foreign provider is allowed (env flag + 152-FZ ack)."""
        return self.allow_foreign_provider and self.acknowledge_152fz

    @property
    def is_pii_redaction_enabled(self) -> bool:
        """Check if PII redaction is enabled (cannot be disabled in production)."""
        return self.pii_redaction_enabled

    @property
    def is_injection_filter_enabled(self) -> bool:
        """Check if injection filter is enabled."""
        return self.injection_filter_enabled

    def get_api_key(self, provider: str) -> str:
        """Get API key for a provider.

        Raises ValueError if key is not set.
        Keys are never logged.
        """
        keys = {
            "yandexgpt": self.yandexgpt_api_key,
            "gigachat": self.gigachat_api_key,
            "openai_compat": self.openai_api_key,
        }
        key = keys.get(provider)
        if not key:
            env_var = f"{provider.upper()}_API_KEY"
            raise ValueError(f"API key not set for provider '{provider}'. Set env variable '{env_var}'.")
        return key

    def validate_foreign_provider(self) -> None:
        """Validate foreign provider usage.

        Raises ForeignProviderNotAllowed if not properly acknowledged.
        """
        if not self.is_foreign_provider_allowed:
            from regulated_eval.exceptions import ForeignProviderNotAllowed  # noqa: PLC0414

            raise ForeignProviderNotAllowed(
                "Foreign provider requires --allow-foreign-provider and --i-understand-152fz flags. "
                "See docs/152fz.md for 152-FZ implications."
            )
