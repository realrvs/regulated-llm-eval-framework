# Security package

"""Security package for Regulated LLM Eval Framework.

Covers FR-010, FR-011, FR-013, NFR-SEC-001..005, TM-01..TM-03, TM-09..TM-11, TM-14.

Submodules:
- pii_redactor: PII detection and redaction (regex + Presidio v2)
- injection_filter: Prompt injection detection for retrieved documents
- secrets: API key management and masking
- provider_allowlist: Provider allowlist with 152-FZ compliance
"""

from __future__ import annotations

from regulated_eval.security.injection_filter import InjectionCheckResult, InjectionFilter
from regulated_eval.security.pii_redactor import PIIRedactor, RedactionResult
from regulated_eval.security.provider_allowlist import (
    FOREIGN_PROVIDERS,
    RUSSIAN_PROVIDERS,
    ProviderAllowlist,
    ProviderType,
)
from regulated_eval.security.secrets import (
    get_api_key,
    log_adapter_init,
    mask_api_key,
    sanitize_for_logging,
    validate_api_keys,
)

__all__ = [
    # PII
    "PIIRedactor",
    "RedactionResult",
    # Injection
    "InjectionFilter",
    "InjectionCheckResult",
    # Secrets
    "get_api_key",
    "mask_api_key",
    "log_adapter_init",
    "sanitize_for_logging",
    "validate_api_keys",
    # Provider allowlist
    "ProviderAllowlist",
    "ProviderType",
    "RUSSIAN_PROVIDERS",
    "FOREIGN_PROVIDERS",
]
