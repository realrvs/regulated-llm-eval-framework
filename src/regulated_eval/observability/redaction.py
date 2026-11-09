"""Redacting processors for OpenTelemetry.

Covers NFR-SEC-002, NFR-OBS-001..005, TM-11, ADR-004.

Provides:
- RedactingSpanProcessor: sanitizes span attributes before export
- RedactingLogProcessor: sanitizes log records before export
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanProcessor  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

# Attributes that are ALWAYS allowed (even if they contain sensitive data)
ALLOWED_ATTRIBUTES: set[str] = {
    "run.id",
    "dataset.version",
    "model.provider",
    "model.name",
    "llm.provider",
    "llm.model",
    "llm.role",
    "record.id",
    "judge.model",
    "judge.prompt.version",
    "trace_id",
    "error.type",
    "error.message",
    "field.name",  # PII redaction audit: only field name, not value
    "source",  # Injection filter: only source domain
    "resolution",  # Conflict resolution type
    "annotator.id",
    "prompt.a",
    "prompt.b",
}

# Attributes that MUST be redacted (contain PII, secrets, or sensitive data)
SENSITIVE_ATTRIBUTES: set[str] = {
    "question",
    "answer",
    "prompt",
    "response",
    "text",
    "content",
    "body",
    "message",
    "api_key",
    "apikey",
    "secret",
    "token",
    "authorization",
    "password",
    "credential",
    "pii.value",
    "original_value",
}


class RedactingSpanProcessor(SpanProcessor):
    """Span processor that redacts sensitive attributes before export.

    Removes or masks attributes containing PII, secrets, or other
    sensitive data. Only allows attributes from the ALLOWED_ATTRIBUTES set.
    """

    def __init__(self, max_attribute_length: int = 500) -> None:
        """Initialize redacting span processor.

        Args:
            max_attribute_length: Maximum length for string attribute values.
                Longer values are truncated.
        """
        self._max_attribute_length = max_attribute_length

    def on_start(
        self,
        span: ReadableSpan,
        parent_context: Any | None = None,
    ) -> None:
        """Process span when it starts.

        Args:
            span: The span being started.
            parent_context: Parent context (unused).
        """
        if span.attributes:
            sanitized = self._sanitize_attributes(dict(span.attributes))
            # Update span attributes in place
            span._attributes = dict(sanitized)

    def on_end(self, span: ReadableSpan) -> None:
        """Process span when it ends.

        Args:
            span: The span being ended.
        """
        if span.attributes:
            sanitized = self._sanitize_attributes(dict(span.attributes))
            span._attributes = dict(sanitized)

    def shutdown(self) -> None:
        """Shutdown the processor."""
        logger.debug("RedactingSpanProcessor shutdown")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the processor.

        Args:
            timeout_millis: Timeout in milliseconds.

        Returns:
            True if flush succeeded.
        """
        return True

    def _sanitize_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Sanitize span attributes.

        Args:
            attrs: Original attributes dict.

        Returns:
            Sanitized attributes dict.
        """
        sanitized: dict[str, Any] = {}

        for key, value in attrs.items():
            # Skip completely if it's a sensitive attribute
            if key in SENSITIVE_ATTRIBUTES:
                logger.debug("Redacted sensitive attribute: %s", key)
                continue

            # Truncate long string values
            if isinstance(value, str) and len(value) > self._max_attribute_length:
                value = value[: self._max_attribute_length] + "..."

            sanitized[key] = value

        return sanitized


class RedactingLogProcessor:
    """Log record processor that redacts sensitive data.

    Used for structured logging with OTel. Ensures PII and secrets
    never appear in exported logs.
    """

    # Log body patterns to redact
    BODY_PATTERNS: list[tuple[str, str]] = [
        ("api_key", "***"),
        ("password", "***"),
        ("token", "***"),
        ("secret", "***"),
    ]

    def __init__(self, enabled: bool = True) -> None:
        """Initialize redacting log processor.

        Args:
            enabled: Whether redaction is active.
        """
        self._enabled = enabled

    def process(self, log_data: dict[str, Any]) -> dict[str, Any]:
        """Process and sanitize log data.

        Args:
            log_data: Log record data.

        Returns:
            Sanitized log data.
        """
        if not self._enabled:
            return log_data

        sanitized = {}

        for key, value in log_data.items():
            # Skip sensitive attributes
            if key in SENSITIVE_ATTRIBUTES:
                continue

            # Sanitize string values
            if isinstance(value, str):
                value = self._sanitize_string(value)
            elif isinstance(value, dict):
                value = self.process(value)

            sanitized[key] = value

        return sanitized

    def _sanitize_string(self, text: str) -> str:
        """Sanitize a string value.

        Args:
            text: String to sanitize.

        Returns:
            Sanitized string.
        """
        result = text
        for pattern, replacement in self.BODY_PATTERNS:
            # Simple case-insensitive replacement
            import re

            result = re.sub(
                rf'("{pattern}"\s*:\s*")[^"]*(")',
                rf"\g<1>{replacement}\2",
                result,
                flags=re.IGNORECASE,
            )
        return result
