"""Prompt injection filter for retrieved documents.

Covers FR-011, NFR-SEC-003, TM-01, ADR-001.

MVP: allowlist domains + regex heuristics.
v2: LLM-based checking for ambiguous cases.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InjectionCheckResult:
    """Result of prompt injection check."""

    allowed: bool = True
    reason: str = "ok"
    source: str = ""
    trace_id: str = ""


class InjectionFilter:
    """Filter for prompt injection in retrieved documents.

    Uses:
    1. Domain allowlist (trusted sources)
    2. Regex heuristics (suspicious patterns)
    3. LLM-based checking (v2, not in MVP)
    """

    # Trusted domains (configurable)
    DEFAULT_ALLOWLIST: list[str] = [
        "minfin.gov.ru",
        "nalog.gov.ru",
        "pravo.gov.ru",
        "consultant.ru",
        "garant.ru",
        "csn.ru",
        "sbrf.ru",
        "yandex.ru",
        "gigachat.ru",
    ]

    # Suspicious patterns for prompt injection
    INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        # Direct instruction overrides
        (
            "IGNORE_PREVIOUS",
            re.compile(
                r"(?:ignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts|commands|system\s+prompt)|"
                r"disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts|commands))",
                re.IGNORECASE,
            ),
        ),
        # Role override
        (
            "ROLE_OVERRIDE",
            re.compile(
                r"(?:you\s+are\s+now(?:\s+allowed)?\s+(?:to\s+)?|"
                r"you\s+must\s+(?:now\s+)?|"
                r"from\s+now\s+on\s+(?:you\s+)?|"
                r"change\s+your\s+role\s+to)",
                re.IGNORECASE,
            ),
        ),
        # System prompt extraction
        (
            "SYSTEM_PROMPT",
            re.compile(
                r"(?:reveal\s+(?:your\s+)?(?:system\s+prompt|instructions|internal\s+rules|initial\s+prompt)|"
                r"show\s+(?:me\s+)?(?:your\s+)?(?:system\s+prompt|instructions|internal\s+rules)|"
                r"print\s+(?:out\s+)?(?:your\s+)?(?:system\s+prompt|instructions))",
                re.IGNORECASE,
            ),
        ),
        # Data exfiltration
        (
            "DATA_EXFIL",
            re.compile(
                r"(?:send\s+(?:this\s+)?(?:data|information|text|content)\s+to\s+(?:http|https|ftp)|"
                r"export\s+(?:your\s+)?(?:knowledge|context|instructions)\s+to)",
                re.IGNORECASE,
            ),
        ),
        # Base64 encoded payloads (potential injection)
        (
            "BASE64_PAYLOAD",
            re.compile(r"[A-Za-z0-9+/]{100,}={0,2}"),
        ),
        # Markdown/HTML injection
        (
            "MARKDOWN_INJECT",
            re.compile(
                r"(?:<!--\s*(?:ignore|skip|disregard)\s*-->|<script[^>]*>|"
                r"javascript:|on\w+\s*=)",
                re.IGNORECASE,
            ),
        ),
    ]

    def __init__(
        self,
        allowlist: list[str] | None = None,
        enabled: bool = True,
        allowed_domains: list[str] | None = None,
    ) -> None:
        """Initialize injection filter.

        Args:
            allowlist: List of trusted domain suffixes.
            enabled: Whether the filter is active.
            allowed_domains: Alias for allowlist (for backwards compatibility).
        """
        self._enabled = enabled
        self._allowlist = allowlist or allowed_domains or self.DEFAULT_ALLOWLIST

    def check(self, content: str, source: str = "") -> InjectionCheckResult:
        """Check if content contains prompt injection.

        Args:
            content: Document content to check.
            source: Source URL or domain of the document.

        Returns:
            InjectionCheckResult with allowed status and reason.
        """
        if not self._enabled:
            return InjectionCheckResult(allowed=True, reason="filter_disabled")

        result = InjectionCheckResult(
            allowed=True,
            reason="ok",
            source=source,
        )

        # Check 1: Domain allowlist
        if source:
            domain = source.split("://")[-1].split("/")[0].split(":")[0].lower()
            if not self._is_domain_allowed(domain):
                result.allowed = False
                result.reason = "domain_not_in_allowlist"
                logger.warning(
                    "Injection blocked: domain not in allowlist, source=%s",
                    source,
                )
                return result

        # Check 2: Regex heuristics
        for pattern_name, pattern in self.INJECTION_PATTERNS:
            if pattern.search(content):
                result.allowed = False
                result.reason = f"injection_pattern:{pattern_name}"
                logger.warning(
                    "Injection blocked: pattern=%s, source=%s",
                    pattern_name,
                    source,
                )
                return result

        return result

    def _is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is in the allowlist."""
        return any(allowed in domain for allowed in self._allowlist)

    def add_domain(self, domain: str) -> None:
        """Add a domain to the allowlist."""
        if domain not in self._allowlist:
            self._allowlist.append(domain)
            logger.info("Added domain to allowlist: %s", domain)

    @property
    def enabled(self) -> bool:
        """Return whether the filter is active."""
        return self._enabled

    @property
    def allowlist(self) -> list[str]:
        """Return the current allowlist."""
        return list(self._allowlist)
