"""Audit logging for security events.

Covers NFR-SEC-002, NFR-SEC-003, TM-01, TM-02, TM-11, ADR-001.

Provides structured audit logging for:
- PII redaction events (field names only, never values)
- Prompt injection detection events
- Data residency compliance events
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


class AuditLogger:
    """Security audit logger.

    Logs security-relevant events with structured JSON format.
    Never logs PII values — only field names and metadata.
    """

    # Event types
    EVENT_PII_REDACTED = "security.pii.redacted"
    EVENT_INJECTION_SUSPECTED = "injection.suspected"
    EVENT_PROVIDER_FOREIGN = "provider.foreign.allowed"
    EVENT_ANNOTATION_TAMPER = "annotation.tamper"

    def __init__(
        self,
        log_dir: str | Path = "audit_logs/",
        enabled: bool = True,
    ) -> None:
        """Initialize audit logger.

        Args:
            log_dir: Directory for audit log files.
            enabled: Whether audit logging is active.
        """
        self._enabled = enabled
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("regulated-eval.audit")
        self._logger.setLevel(logging.INFO)

        if not self._logger.handlers:
            # File handler for audit logs
            file_handler = logging.FileHandler(
                self._log_dir / "audit.log",
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(file_handler)

            # Console handler for structured output
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(AuditFormatter())
            self._logger.addHandler(console_handler)

    def log_pii_redacted(
        self,
        field_name: str,
        run_id: str = "",
        trace_id: str = "",
        record_id: str = "",
    ) -> None:
        """Log PII redaction event.

        Args:
            field_name: Name of the PII field (e.g. "INN", "PHONE").
            run_id: Run identifier.
            trace_id: Trace identifier.
            record_id: Golden record ID.
        """
        if not self._enabled:
            return

        event = {
            "event": self.EVENT_PII_REDACTED,
            "field.name": field_name,
            "run.id": run_id,
            "trace_id": trace_id,
            "record.id": record_id,
            "pii_redacted": True,
        }
        self._logger.info(json.dumps(event, ensure_ascii=False, default=str))

    def log_injection_suspected(
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
        if not self._enabled:
            return

        event = {
            "event": self.EVENT_INJECTION_SUSPECTED,
            "source": source,
            "run.id": run_id,
            "trace_id": trace_id,
            "reason": reason,
            "injection_blocked": True,
        }
        self._logger.warning(json.dumps(event, ensure_ascii=False, default=str))

    def log_provider_foreign(
        self,
        provider: str = "",
        ack_source: str = "",
        run_id: str = "",
        trace_id: str = "",
    ) -> None:
        """Log foreign provider usage event.

        Args:
            provider: Provider name.
            ack_source: How 152-FZ was acknowledged.
            run_id: Run identifier.
            trace_id: Trace identifier.
        """
        if not self._enabled:
            return

        event = {
            "event": self.EVENT_PROVIDER_FOREIGN,
            "provider": provider,
            "ack.source": ack_source,
            "run.id": run_id,
            "trace_id": trace_id,
        }
        self._logger.warning(json.dumps(event, ensure_ascii=False, default=str))

    def log_annotation_tamper(
        self,
        record_id: str = "",
        annotator_id: str = "",
        run_id: str = "",
        trace_id: str = "",
    ) -> None:
        """Log annotation tampering attempt.

        Args:
            record_id: Golden record ID.
            annotator_id: Annotator ID.
            run_id: Run identifier.
            trace_id: Trace identifier.
        """
        if not self._enabled:
            return

        event = {
            "event": self.EVENT_ANNOTATION_TAMPER,
            "record.id": record_id,
            "annotator.id": annotator_id,
            "run.id": run_id,
            "trace_id": trace_id,
            "tamper_detected": True,
        }
        self._logger.critical(json.dumps(event, ensure_ascii=False, default=str))

    @property
    def enabled(self) -> bool:
        """Whether audit logging is enabled."""
        return self._enabled


class AuditFormatter(logging.Formatter):
    """JSON formatter for audit logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format.

        Returns:
            JSON string.
        """
        if hasattr(record, "msg") and record.msg:
            try:
                return json.dumps(
                    json.loads(record.msg),
                    ensure_ascii=False,
                    default=str,
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return str(record.getMessage())
