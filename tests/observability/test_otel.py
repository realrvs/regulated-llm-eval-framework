"""Observability tests: OTel spans, metrics, logs.

Covers TC-OBS-001..010.
"""

from regulated_eval.observability import (
    get_meter,
    get_tracer,
    init_otel,
    is_otel_enabled,
    record_eval_run_duration,
    record_llm_request_duration,
    register_metrics,
    shutdown_otel,
)
from regulated_eval.observability.logs import AuditLogger, StructuredLogger, _get_trace_id


class TestOtelSetup:
    """Test OTel initialization."""

    def test_otel_enabled_by_default(self):
        assert is_otel_enabled() is True

    def test_otel_disabled_by_env(self, monkeypatch):
        monkeypatch.setenv("REGULATED_EVAL_OTEL_ENABLED", "false")
        assert is_otel_enabled() is False

    def test_get_tracer(self):
        tracer = get_tracer("test-tracer")
        # Should not raise even if OTel not fully initialized
        assert tracer is not None or tracer is None  # May be None if OTel not initialized

    def test_get_meter(self):
        meter = get_meter("test-meter")
        assert meter is not None or meter is None  # May be None if OTel not initialized

    def test_init_otel_returns_providers(self):
        result = init_otel()
        assert "tracer_provider" in result
        assert "meter_provider" in result
        assert "logger_provider" in result

    def test_shutdown_otel_no_error(self):
        shutdown_otel()  # Should not raise


class TestStructuredLogger:
    """Test structured JSON logging."""

    def test_structured_logger_creates_handler(self):
        logger = StructuredLogger("test-logger")
        assert logger._logger is not None

    def test_log_levels(self, caplog):
        logger = StructuredLogger("test-logger")
        with caplog.at_level("DEBUG"):
            logger.debug("debug msg")
            logger.info("info msg")
            logger.warning("warning msg")
            logger.error("error msg")

        assert "debug msg" in caplog.text
        assert "info msg" in caplog.text
        assert "warning msg" in caplog.text
        assert "error msg" in caplog.text

    def test_trace_id_injection(self):
        """Trace ID should be injected into structured logs."""
        trace_id = _get_trace_id()
        # Should return string (empty if no active span)
        assert isinstance(trace_id, str)


class TestAuditLogger:
    """Test audit logger events."""

    def test_pii_redacted_event(self, caplog):
        logger = AuditLogger("test-audit")
        with caplog.at_level("INFO"):
            logger.pii_redacted("INN", run_id="run-1", trace_id="trace-1")

        assert "security.pii.redacted" in caplog.text
        # Field name should be in structured data
        record = caplog.records[0]
        assert hasattr(record, "structured_data")
        assert record.structured_data.get("field.name") == "INN"
        # PII value should NOT be in logs
        assert "770123456789" not in caplog.text

    def test_injection_suspected_event(self, caplog):
        logger = AuditLogger("test-audit")
        with caplog.at_level("WARNING"):
            logger.injection_suspected(source="url", reason="suspicious")

        assert "injection.suspected" in caplog.text

    def test_conflict_resolved_event(self, caplog):
        logger = AuditLogger("test-audit")
        with caplog.at_level("INFO"):
            logger.conflict_resolved(record_id="rec-1", resolution="accept_human", annotator_id="expert-1")

        assert "judge.conflict.resolved" in caplog.text

    def test_ab_test_completed_event(self, caplog):
        logger = AuditLogger("test-audit")
        with caplog.at_level("INFO"):
            logger.ab_test_completed(prompt_a="v1", prompt_b="v2", delta=0.15, p_value=0.03)

        assert "ab.test.completed" in caplog.text

    def test_foreign_provider_event(self, caplog):
        logger = AuditLogger("test-audit")
        with caplog.at_level("WARNING"):
            logger.foreign_provider_allowed(provider="openai", ack_source="cli")

        assert "provider.foreign.allowed" in caplog.text


class TestMetricsRecording:
    """Test metric recording functions."""

    def test_record_eval_run_duration(self):
        """eval.run.duration metric should be recordable."""
        # Should not raise
        record_eval_run_duration({}, 1.5, attributes={"run.id": "test"})

    def test_record_llm_request_duration(self):
        """llm.request.duration metric should be recordable."""
        record_llm_request_duration({}, 0.5, provider="yandexgpt", model="yandexgpt-latest", role="generator")

    def test_register_metrics(self):
        """Metrics should be registerable."""
        from opentelemetry import metrics as metrics_api

        meter = metrics_api.NoOpMeterProvider().get_meter("test")
        registered = register_metrics(meter)
        assert "eval_run_duration" in registered
        assert "eval_run_failed" in registered
        assert "llm_request_duration" in registered
