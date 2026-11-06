"""Observability package.

Covers NFR-OBS-001..005, TM-11, ADR-004.

Submodules:
- otel_setup: TracerProvider, MeterProvider, LoggerProvider initialization
- redaction: RedactingSpanProcessor, RedactingLogProcessor for PII/secrets sanitization
- metrics: OTel metric registration and recording helpers
- logs: Structured JSON logging with trace correlation + AuditLogger
"""

from __future__ import annotations

from regulated_eval.observability.logs import AuditLogger, StructuredLogger
from regulated_eval.observability.metrics import (
    CITATION_ACCURACY_NAME,
    EVAL_RUN_DURATION_NAME,
    EVAL_RUN_FAILED_NAME,
    HALLUCINATION_RATE_NAME,
    JUDGE_CALIBRATION_KAPPA_NAME,
    LLM_REQUEST_DURATION_NAME,
    record_citation_accuracy,
    record_eval_run_duration,
    record_eval_run_failed,
    record_hallucination_rate,
    record_judge_calibration_kappa,
    record_llm_request_duration,
    register_metrics,
)
from regulated_eval.observability.otel_setup import (
    get_meter,
    get_tracer,
    init_otel,
    is_otel_enabled,
    shutdown_otel,
)
from regulated_eval.observability.redaction import RedactingLogProcessor, RedactingSpanProcessor

__all__ = [
    # OTel setup
    "init_otel",
    "get_tracer",
    "get_meter",
    "shutdown_otel",
    "is_otel_enabled",
    # Metrics
    "register_metrics",
    "record_eval_run_duration",
    "record_eval_run_failed",
    "record_llm_request_duration",
    "record_judge_calibration_kappa",
    "record_hallucination_rate",
    "record_citation_accuracy",
    "EVAL_RUN_DURATION_NAME",
    "EVAL_RUN_FAILED_NAME",
    "LLM_REQUEST_DURATION_NAME",
    "JUDGE_CALIBRATION_KAPPA_NAME",
    "HALLUCINATION_RATE_NAME",
    "CITATION_ACCURACY_NAME",
    # Logging
    "StructuredLogger",
    "AuditLogger",
    # Redaction
    "RedactingSpanProcessor",
    "RedactingLogProcessor",
]
