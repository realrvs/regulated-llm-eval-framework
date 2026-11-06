"""OTel metrics for Regulated LLM Eval Framework.

Covers NFR-OBS-001..005, TM-11, ADR-004.

Metrics:
- eval.run.duration (histogram) — eval run latency
- eval.run.failed (counter) — failed eval runs
- llm.request.duration (histogram) — LLM request latency
- judge.calibration.kappa (gauge) — calibration kappa score
- hallucination.rate (gauge) — hallucination rate
- citation_accuracy (gauge) — citation accuracy
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Metric names
EVAL_RUN_DURATION_NAME = "eval.run.duration"
EVAL_RUN_FAILED_NAME = "eval.run.failed"
LLM_REQUEST_DURATION_NAME = "llm.request.duration"
JUDGE_CALIBRATION_KAPPA_NAME = "judge.calibration.kappa"
HALLUCINATION_RATE_NAME = "hallucination.rate"
CITATION_ACCURACY_NAME = "citation_accuracy"


def register_metrics(meter: Any) -> dict[str, Any]:
    """Register all OTel metrics with the meter.

    Args:
        meter: OTel Meter instance.

    Returns:
        Dict of registered metric objects.
    """
    metrics: dict[str, Any] = {}

    try:
        # Histogram for eval run duration (seconds)
        metrics["eval_run_duration"] = meter.create_histogram(
            name=EVAL_RUN_DURATION_NAME,
            unit="s",
            description="Duration of eval run",
        )

        # Counter for failed eval runs
        metrics["eval_run_failed"] = meter.create_counter(
            name=EVAL_RUN_FAILED_NAME,
            unit="1",
            description="Number of failed eval runs",
        )

        # Histogram for LLM request duration (seconds)
        metrics["llm_request_duration"] = meter.create_histogram(
            name=LLM_REQUEST_DURATION_NAME,
            unit="s",
            description="Duration of LLM request",
        )

        # Gauge for judge calibration kappa
        metrics["judge_calibration_kappa"] = meter.create_gauge(
            name=JUDGE_CALIBRATION_KAPPA_NAME,
            unit="1",
            description="Cohen's kappa for judge calibration",
        )

        # Gauge for hallucination rate
        metrics["hallucination_rate"] = meter.create_gauge(
            name=HALLUCINATION_RATE_NAME,
            unit="1",
            description="Hallucination rate",
        )

        # Gauge for citation accuracy
        metrics["citation_accuracy"] = meter.create_gauge(
            name=CITATION_ACCURACY_NAME,
            unit="1",
            description="Citation accuracy",
        )

        logger.info("All OTel metrics registered successfully")

    except Exception as e:
        logger.warning("Failed to register some OTel metrics: %s", e)

    return metrics


def record_eval_run_duration(
    metrics: dict[str, Any],
    duration: float,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Record eval run duration.

    Args:
        metrics: Registered metrics dict.
        duration: Duration in seconds.
        attributes: Optional attributes (dataset.version, model.provider, etc.).
    """
    if "eval_run_duration" not in metrics:
        return

    try:
        metrics["eval_run_duration"].record(duration, attributes)
    except Exception as e:
        logger.debug("Failed to record eval.run.duration: %s", e)


def record_eval_run_failed(
    metrics: dict[str, Any],
    error_reason: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Record failed eval run.

    Args:
        metrics: Registered metrics dict.
        error_reason: Reason for failure.
        attributes: Optional additional attributes.
    """
    if "eval_run_failed" not in metrics:
        return

    attrs = {"error.reason": error_reason}
    if attributes:
        attrs.update(attributes)

    try:
        metrics["eval_run_failed"].add(1, attrs)
    except Exception as e:
        logger.debug("Failed to record eval.run.failed: %s", e)


def record_llm_request_duration(
    metrics: dict[str, Any],
    duration: float,
    provider: str = "",
    model: str = "",
    role: str = "generator",
) -> None:
    """Record LLM request duration.

    Args:
        metrics: Registered metrics dict.
        duration: Duration in seconds.
        provider: LLM provider name.
        model: Model name.
        role: Role (judge/generator).
    """
    if "llm_request_duration" not in metrics:
        return

    attributes = {
        "llm.provider": provider,
        "llm.model": model,
        "llm.role": role,
    }

    try:
        metrics["llm_request_duration"].record(duration, attributes)
    except Exception as e:
        logger.debug("Failed to record llm.request.duration: %s", e)


def record_judge_calibration_kappa(
    metrics: dict[str, Any],
    kappa: float,
    dataset_version: str = "",
    judge_model: str = "",
) -> None:
    """Record judge calibration kappa.

    Args:
        metrics: Registered metrics dict.
        kappa: Cohen's kappa value.
        dataset_version: Dataset version.
        judge_model: Judge model name.
    """
    if "judge_calibration_kappa" not in metrics:
        return

    attributes = {
        "dataset.version": dataset_version,
        "judge.model": judge_model,
    }

    try:
        metrics["judge_calibration_kappa"].set(kappa, attributes)
    except Exception as e:
        logger.debug("Failed to record judge.calibration.kappa: %s", e)


def record_hallucination_rate(
    metrics: dict[str, Any],
    rate: float,
    dataset_version: str = "",
    model_name: str = "",
    category: str = "",
) -> None:
    """Record hallucination rate.

    Args:
        metrics: Registered metrics dict.
        rate: Hallucination rate (0..1).
        dataset_version: Dataset version.
        model_name: Model name.
        category: Category name.
    """
    if "hallucination_rate" not in metrics:
        return

    attributes = {
        "dataset.version": dataset_version,
        "model.name": model_name,
        "category": category,
    }

    try:
        metrics["hallucination_rate"].set(rate, attributes)
    except Exception as e:
        logger.debug("Failed to record hallucination.rate: %s", e)


def record_citation_accuracy(
    metrics: dict[str, Any],
    accuracy: float,
    dataset_version: str = "",
    model_name: str = "",
) -> None:
    """Record citation accuracy.

    Args:
        metrics: Registered metrics dict.
        accuracy: Citation accuracy (0..1).
        dataset_version: Dataset version.
        model_name: Model name.
    """
    if "citation_accuracy" not in metrics:
        return

    attributes = {
        "dataset.version": dataset_version,
        "model.name": model_name,
    }

    try:
        metrics["citation_accuracy"].set(accuracy, attributes)
    except Exception as e:
        logger.debug("Failed to record citation_accuracy: %s", e)
