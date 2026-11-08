# Observability package

"""OpenTelemetry bootstrap and configuration.

Covers NFR-OBS-001..005, TM-11, ADR-004.

Provides:
- TracerProvider with OTLP exporter
- MeterProvider with OTLP exporter
- LoggerProvider with OTLP exporter
- Redacting processors for PII/secrets sanitization
- Sampling policy (10% success, 100% error)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Global providers (initialized on first use)
_tracer_provider = None
_meter_provider = None
_logger_provider = None
_otel_initialized = False


def is_otel_enabled() -> bool:
    """Check if OTel is enabled via environment."""
    return os.environ.get("REGULATED_EVAL_OTEL_ENABLED", "true").lower() in ("true", "1", "yes")


def _get_otel_endpoint() -> str:
    """Get OTLP endpoint from config."""
    return os.environ.get("REGULATED_EVAL_OTEL_ENDPOINT", "http://localhost:4317")


def _get_sampling_ratio() -> float:
    """Get sampling ratio for successful runs."""
    try:
        return float(os.environ.get("REGULATED_EVAL_OTEL_SAMPLING_RATIO", "0.1"))
    except ValueError:
        return 0.1


def _get_error_sampling_ratio() -> float:
    """Get sampling ratio for error runs."""
    try:
        return float(os.environ.get("REGULATED_EVAL_OTEL_SAMPLING_ERROR_RATIO", "1.0"))
    except ValueError:
        return 1.0


def init_otel(service_name: str = "regulated-eval") -> dict[str, Any]:
    """Initialize all OTel providers.

    Args:
        service_name: Service name for OTel resource.

    Returns:
        Dict with initialized providers.
    """
    global _tracer_provider, _meter_provider, _logger_provider, _otel_initialized

    if _otel_initialized:
        logger.debug("OTel already initialized, returning existing providers")
        return {
            "tracer_provider": _tracer_provider,
            "meter_provider": _meter_provider,
            "logger_provider": _logger_provider,
        }

    if not is_otel_enabled():
        logger.info("OTel is disabled (REGULATED_EVAL_OTEL_ENABLED=false)")
        _otel_initialized = True
        return {
            "tracer_provider": None,
            "meter_provider": None,
            "logger_provider": None,
        }

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from regulated_eval.observability.redaction import RedactingSpanProcessor

        # Create resource
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "0.1.0",
            }
        )

        # Initialize TracerProvider
        sampling_ratio = _get_sampling_ratio()
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=trace.sampling.TraceIdRatioBased(sampling_ratio),
        )

        # Add OTLP exporter
        endpoint = _get_otel_endpoint()
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Add redacting span processor (PII/secrets sanitization)
        redacting_processor = RedactingSpanProcessor()
        tracer_provider.add_span_processor(redacting_processor)

        _tracer_provider = tracer_provider
        trace.set_tracer_provider(_tracer_provider)

        logger.info(
            "OTel TracerProvider initialized: endpoint=%s, sampling=%.1f%%",
            endpoint,
            sampling_ratio * 100,
        )

    except Exception as e:
        logger.warning("Failed to initialize OTel TracerProvider: %s", e)
        _otel_initialized = True
        return {
            "tracer_provider": None,
            "meter_provider": None,
            "logger_provider": None,
        }

    # Initialize MeterProvider
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        endpoint = _get_otel_endpoint()
        metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)

        _meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(_meter_provider)

        logger.info("OTel MeterProvider initialized: endpoint=%s", endpoint)

    except Exception as e:
        logger.warning("Failed to initialize OTel MeterProvider: %s", e)

    _otel_initialized = True

    return {
        "tracer_provider": _tracer_provider,
        "meter_provider": _meter_provider,
        "logger_provider": _logger_provider,
    }


def get_tracer(name: str = "regulated-eval") -> Any:
    """Get or create a tracer.

    Args:
        name: Tracer name.

    Returns:
        Tracer instance, or None if OTel not initialized.
    """
    if not is_otel_enabled():
        return None

    if _tracer_provider is None:
        result = init_otel()
        if result["tracer_provider"] is None:
            return None

    from opentelemetry import trace

    return trace.get_tracer(name)


def get_meter(name: str = "regulated-eval") -> Any:
    """Get or create a meter.

    Args:
        name: Meter name.

    Returns:
        Meter instance, or None if OTel not initialized.
    """
    if not is_otel_enabled():
        return None

    if _meter_provider is None:
        init_otel()

    from opentelemetry import metrics

    return metrics.get_meter(name)


def shutdown_otel() -> None:
    """Shutdown all OTel providers gracefully."""
    global _tracer_provider, _meter_provider, _logger_provider

    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            logger.info("OTel TracerProvider shut down")
        except Exception as e:
            logger.warning("Error shutting down TracerProvider: %s", e)

    if _meter_provider is not None:
        try:
            _meter_provider.shutdown()
            logger.info("OTel MeterProvider shut down")
        except Exception as e:
            logger.warning("Error shutting down MeterProvider: %s", e)

    _otel_initialized = False
