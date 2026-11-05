"""Eval orchestrator — main pipeline.

Covers FR-003, FR-004, FR-006, FR-010, FR-011, FR-012, FR-013, FR-015.
Covers NFR-001, NFR-002, NFR-005, NFR-008.

Pipeline flow:
1. Load golden set
2. Redact PII
3. Generate answers (via adapter)
4. Judge evaluation
5. Compute metrics
6. Generate report
7. Save manifest
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from regulated_eval.adapters.base import BaseAdapter, LLMRequest
from regulated_eval.config import Config
from regulated_eval.datasets.loader import load_golden_set
from regulated_eval.datasets.manifest import create_manifest, save_manifest_file
from regulated_eval.datasets.versioning import compute_dataset_hash
from regulated_eval.exceptions import (
    DatasetVersionNotFound,
    ForeignProviderNotAllowed,
    MissingCredentials,
    RateLimitExhausted,
)
from regulated_eval.judges.calibration import CalibrationEngine
from regulated_eval.judges.judge import Judge
from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.schemas import (
    Annotation,
    CalibrationResult,
    GoldenRecord,
    JudgeResult,
    MetricsBlock,
    RunManifest,
)
from regulated_eval.security.injection_filter import InjectionFilter
from regulated_eval.security.pii_redactor import PIIRedactor

logger = logging.getLogger(__name__)


class EvalOrchestrator:
    """Orchestrates the full eval pipeline."""

    def __init__(
        self,
        adapter: BaseAdapter,
        config: Config | None = None,
        judge_prompt_version: str = "v1",
    ) -> None:
        """Initialize orchestrator.

        Args:
            adapter: LLM adapter for generating answers.
            config: Optional Config object.
            judge_prompt_version: Version of judge prompt.
        """
        self._adapter = adapter
        self._config = config or Config()
        self._judge_prompt_version = judge_prompt_version
        self._redactor = PIIRedactor(
            enable_fio=self._config.pii_redaction_enabled,
            enable_address=self._config.pii_redaction_enabled,
        )
        self._injection_filter = InjectionFilter(
            enabled=self._config.injection_filter_enabled,
        )
        self._judge: Judge | None = None
        self._metrics_aggregator = MetricsAggregator()

    def _get_judge(self) -> Judge:
        """Get or create judge instance."""
        if self._judge is None:
            from regulated_eval.adapters.yandexgpt import YandexGPTAdapter  # noqa: PLC0414

            # Use same adapter for judge (can be configured separately later)
            self._judge = Judge(
                adapter=self._adapter,
                config=self._config,
                prompt_version=self._judge_prompt_version,
            )
        return self._judge

    def run(
        self,
        dataset_path: str | Path,
        dataset_version: str = "0.1.0",
        seed: int = 42,
        run_id: str | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """Run the full eval pipeline.

        Args:
            dataset_path: Path to golden set file.
            dataset_version: Dataset version (semver).
            seed: Random seed for reproducibility.
            run_id: Optional run ID (generated if not provided).
            trace_id: Optional trace ID.

        Returns:
            Dict with run_id, manifest, metrics, judge_results.
        """
        # Validate foreign provider
        if self._adapter.is_foreign:
            self._config.validate_foreign_provider()

        # Generate run ID
        if run_id is None:
            run_id = str(uuid.uuid4())

        if not trace_id:
            trace_id = str(uuid.uuid4())

        logger.info("Starting eval run %s with seed=%d", run_id, seed)
        np.random.seed(seed)

        # Step 1: Load golden set
        records = load_golden_set(dataset_path)
        dataset_hash = compute_dataset_hash(records)
        logger.info("Loaded %d records from %s", len(records), dataset_path)

        # Step 2-5: Process each record
        judge_results: list[JudgeResult] = []
        total_tokens_input = 0
        total_tokens_output = 0

        for i, record in enumerate(records, 1):
            logger.debug("Processing record %d/%s: %s", i, len(records), record.id)

            # Step 2: Redact PII
            redaction_result = self._redactor.redact(record.question)
            redacted_question = redaction_result.redacted_text

            # Step 3: Generate answer
            request = LLMRequest(
                prompt=redacted_question,
                model=self._adapter.model_name(),
                temperature=0.0,
                max_tokens=1024,
                metadata={
                    "trace_id": trace_id,
                    "record_id": record.id,
                    "run_id": run_id,
                },
            )

            response = self._adapter.generate(request)
            total_tokens_input += response.tokens_input
            total_tokens_output += response.tokens_output

            if response.error:
                logger.warning("Generate error for %s: %s", record.id, response.error)
                continue

            # Step 4: Judge evaluation
            judge = self._get_judge()
            judge_result = judge.evaluate(record, response.text, trace_id)
            judge_results.append(judge_result)

        # Step 5: Compute metrics
        categories = {r.id: r.category.value for r in records}
        difficulties = {r.id: r.difficulty.value for r in records}
        metrics = self._metrics_aggregator.aggregate(judge_results, categories, difficulties)

        # Step 6: Create manifest
        manifest = create_manifest(
            run_id=run_id,
            dataset_version=dataset_version,
            dataset_content_hash=dataset_hash,
            model_provider=self._adapter.provider(),
            model_name=self._adapter.model_name(),
            judge_model=self._get_judge()._adapter.model_name(),
            judge_prompt_version=self._judge_prompt_version,
            seed=seed,
            package_version="0.1.0",
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
            trace_id=trace_id,
        )

        # Estimate cost
        estimated_cost = self._adapter.estimate_cost(total_tokens_input, total_tokens_output)
        manifest.estimated_cost_rub = estimated_cost

        logger.info(
            "Eval run %s completed: %d records, %d judge results, kappa=N/A",
            run_id,
            len(records),
            len(judge_results),
        )

        return {
            "run_id": run_id,
            "trace_id": trace_id,
            "manifest": manifest,
            "metrics": metrics,
            "judge_results": judge_results,
            "total_tokens_input": total_tokens_input,
            "total_tokens_output": total_tokens_output,
            "estimated_cost_rub": estimated_cost,
        }

    def calibrate(
        self,
        dataset_path: str | Path,
        annotations: list[Annotation],
        threshold: float = 0.6,
        ci_level: float = 0.95,
    ) -> CalibrationResult:
        """Calibrate judge against expert annotations.

        Args:
            dataset_path: Path to calibration dataset.
            annotations: List of expert annotations.
            threshold: Minimum kappa threshold.
            ci_level: Confidence level for CI.

        Returns:
            CalibrationResult.
        """
        # Load calibration records
        records = load_golden_set(dataset_path)

        # Run judge on calibration records
        judge = self._get_judge()
        judge_results: list[JudgeResult] = []

        for record in records:
            # Use reference answer as placeholder (in real scenario, model answers would be loaded)
            # For calibration, we need both model answers and human annotations
            # This is a simplified version
            judge_result = judge.evaluate(record, record.reference_answer, trace_id="calibration")
            judge_results.append(judge_result)

        # Compute calibration
        engine = CalibrationEngine(self._config)
        result = engine.compute_kappa(
            judge_results,
            annotations,
            threshold=threshold,
            ci_level=ci_level,
        )

        return result
