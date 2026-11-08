"""Structured JSON logging with OTel trace correlation.

Covers NFR-OBS-001..005, TM-11, ADR-004.

Provides:
- StructuredLogger: JSON logging with trace_id injection
- Audit logger for security events (pii.redacted, injection.suspected, etc.)
"""

from __future__ import annotations

import json
import logging
from typing import Any


def _get_trace_id() -> str:
    """Get current trace_id from OTel context.

    Returns:
        Current trace_id string, or empty if not available.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            context = span.get_span_context()
            if context.trace_id:
                return format(context.trace_id, "032x")
    except Exception:
        pass
    return ""


class StructuredFormatter(logging.Formatter):
    """JSON formatter that adds trace_id and structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON string with log data.
        """
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": _get_trace_id(),
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add custom fields from record
        if hasattr(record, "structured_data"):
            log_data.update(record.structured_data)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class StructuredLogger:
    """Structured logger with trace correlation.

    Wraps standard Python logging with JSON formatting and
    automatic trace_id injection.
    """

    def __init__(self, name: str = "regulated-eval") -> None:
        """Initialize structured logger.

        Args:
            name: Logger name.
        """
        self._logger = logging.getLogger(name)
        self._setup_formatter()

    def _setup_formatter(self) -> None:
        """Set up JSON formatter for the logger."""
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            self._logger.addHandler(handler)

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Log a message with structured data.

        Args:
            level: Log level.
            message: Log message.
            **kwargs: Additional structured fields.
        """
        # Create log record with structured data
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            message,
            (),
            None,
        )
        record.structured_data = kwargs
        self._logger.handle(record)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)


class AuditLogger:
    """Security audit logger.

    Logs security-relevant events with structured data.
    Never logs PII values, only field names.

    Event types:
    - security.pii.redacted: PII was redacted
    - injection.suspected: Prompt injection detected
    - judge.conflict.resolved: Judge-human conflict resolved
    - ab.test.completed: A/B test completed
    - provider.foreign.allowed: Foreign provider used
    """

    def __init__(self, logger_name: str = "regulated-eval.audit") -> None:
        """Initialize audit logger.

        Args:
            logger_name: Logger name for audit events.
        """
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.INFO)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            self._logger.addHandler(handler)

    def pii_redacted(
        self,
        field_name: str,
        run_id: str = "",
        trace_id: str = "",
    ) -> None:
        """Log PII redaction event.

        Args:
            field_name: Name of the PII field (e.g. "INN", "PHONE").
            run_id: Run identifier.
            trace_id: Trace identifier.
        """
        self._logger.info(
            "security.pii.redacted",
            extra={
                "structured_data": {
                    "field.name": field_name,
                    "run.id": run_id,
                    "trace_id": trace_id or _get_trace_id(),
                    "pii_redacted": True,
                }
            },
        )

    def injection_suspected(
        self,
        source: str = "",
        run_id: str = "",
        trace_id: str = "",
        reason: str = "",
    ) -> None:
        """Log suspected prompt injection event.

        Args:
            source: Source of the document.
            run_id: Run identifier.
            trace_id: Trace identifier.
            reason: Reason for suspicion.
        """
        self._logger.warning(
            "injection.suspected",
            extra={
                "structured_data": {
                    "source": source,
                    "run.id": run_id,
                    "trace_id": trace_id or _get_trace_id(),
                    "reason": reason,
                    "injection_blocked": True,
                }
            },
        )

    def conflict_resolved(
        self,
        record_id: str = "",
        resolution: str = "",
        annotator_id: str = "",
        trace_id: str = "",
    ) -> None:
        """Log judge-human conflict resolution event.

        Args:
            record_id: Golden record ID.
            resolution: Resolution type (accept_human, accept_judge, escalate).
            annotator_id: Expert annotator ID.
            trace_id: Trace identifier.
        """
        self._logger.info(
            "judge.conflict.resolved",
            extra={
                "structured_data": {
                    "record.id": record_id,
                    "resolution": resolution,
                    "annotator.id": annotator_id,
                    "trace_id": trace_id or _get_trace_id(),
                }
            },
        )

    def ab_test_completed(
        self,
        prompt_a: str = "",
        prompt_b: str = "",
        delta: float = 0.0,
        p_value: float = 1.0,
        trace_id: str = "",
    ) -> None:
        """Log A/B test completion event.

        Args:
            prompt_a: Prompt A identifier.
            prompt_b: Prompt B identifier.
            delta: Metric delta between A and B.
            p_value: Statistical p-value.
            trace_id: Trace identifier.
        """
        self._logger.info(
            "ab.test.completed",
            extra={
                "structured_data": {
                    "prompt.a": prompt_a,
                    "prompt.b": prompt_b,
                    "delta": delta,
                    "p_value": p_value,
                    "trace_id": trace_id or _get_trace_id(),
                }
            },
        )

    def foreign_provider_allowed(
        self,
        provider: str = "",
        ack_source: str = "",
        trace_id: str = "",
    ) -> None:
        """Log foreign provider usage event.

        Args:
            provider: Provider name.
            ack_source: How 152-FZ was acknowledged.
            trace_id: Trace identifier.
        """
        self._logger.warning(
            "provider.foreign.allowed",
            extra={
                "structured_data": {
                    "provider": provider,
                    "ack.source": ack_source,
                    "trace_id": trace_id or _get_trace_id(),
                }
            },
        )

    def annotation_tamper(
        self,
        record_id: str = "",
        annotator_id: str = "",
        trace_id: str = "",
    ) -> None:
        """Log annotation tampering attempt.

        Args:
            record_id: Golden record ID.
            annotator_id: Annotator ID.
            trace_id: Trace identifier.
        """
        self._logger.critical(
            "annotation.tamper",
            extra={
                "structured_data": {
                    "record.id": record_id,
                    "annotator.id": annotator_id,
                    "trace_id": trace_id or _get_trace_id(),
                    "tamper_detected": True,
                }
            },
        )
