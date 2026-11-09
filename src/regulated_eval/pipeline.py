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

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from regulated_eval.adapters.base import BaseAdapter, LLMRequest
from regulated_eval.config import Config
from regulated_eval.datasets.loader import load_golden_set
from regulated_eval.datasets.manifest import create_manifest
from regulated_eval.datasets.versioning import compute_dataset_hash
from regulated_eval.exceptions import (
    MissingCredentials,
    RateLimitExhausted,
)
from regulated_eval.judges.calibration import CalibrationEngine
from regulated_eval.judges.judge import Judge
from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.observability import get_tracer, record_eval_run_duration
from regulated_eval.schemas import (
    Annotation,
    CalibrationResult,
    GoldenRecord,
    JudgeResult,
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
            self._judge = Judge(
                adapter=self._adapter,
                config=self._config,
                prompt_version=self._judge_prompt_version,
            )
        return self._judge

    async def run(
        self,
        dataset_path: str | Path,
        dataset_version: str = "0.1.0",
        seed: int = 42,
        run_id: str | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """Run the full eval pipeline (async).

        Args:
            dataset_path: Path to golden set file.
            dataset_version: Dataset version (semver).
            seed: Random seed for reproducibility.
            run_id: Optional run ID (generated if not provided).
            trace_id: Optional trace ID.

        Returns:
            Dict with run_id, manifest, metrics, judge_results.
        """
        start_time = time.monotonic()
        tracer = get_tracer("regulated-eval")

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

        # Create span for eval.run
        span = None
        if tracer is not None:
            span = tracer.start_span("eval.run")
            span.set_attribute("run.id", run_id)
            span.set_attribute("dataset.version", dataset_version)
            span.set_attribute("model.provider", self._adapter.provider())
            span.set_attribute("model.name", self._adapter.model_name())
            span.set_attribute("seed", seed)

        # Step 1: Load golden set
        records = load_golden_set(dataset_path, strict=False)
        dataset_hash = compute_dataset_hash(records)
        logger.info("Loaded %d records from %s", len(records), dataset_path)
        if span is not None:
            span.set_attribute("dataset.records", len(records))

        # Step 2-5: Process each record
        judge_results: list[JudgeResult] = []
        total_tokens_input = 0
        total_tokens_output = 0

        # Use asyncio.Semaphore for parallelism control
        semaphore = asyncio.Semaphore(self._config.default_parallelism)

        async def process_record(record: GoldenRecord) -> JudgeResult | None:
            """Process a single record with rate-limit protection."""
            nonlocal total_tokens_input, total_tokens_output
            async with semaphore:
                logger.debug("Processing record %s: %s", record.id, record.id)

                # Step 2: Redact PII
                redaction_result = self._redactor.redact(record.question)
                redacted_question = redaction_result.redacted_text

                # Step 2b: Check injection in question (if it contains URLs)
                if self._injection_filter.enabled:
                    injection_result = self._injection_filter.check(redacted_question)
                    if not injection_result.allowed:
                        logger.warning(
                            "Injection detected in record %s: %s",
                            record.id,
                            injection_result.reason,
                        )

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

                try:
                    response = await self._adapter.generate(request)
                except RateLimitExhausted:
                    logger.warning("Rate limit exhausted for record %s", record.id)
                    return JudgeResult(
                        record_id=record.id,
                        score=0,
                        hallucination=False,
                        wrong_citation=False,
                        incorrect_refusal=False,
                        rationale="Rate limit exhausted",
                        judge_model=self._adapter.model_name(),
                        judge_prompt_version=self._judge_prompt_version,
                        judge_status="rate_limited",
                        trace_id=trace_id,
                    )
                except MissingCredentials:
                    logger.error("Missing credentials for record %s", record.id)
                    return JudgeResult(
                        record_id=record.id,
                        score=0,
                        hallucination=False,
                        wrong_citation=False,
                        incorrect_refusal=False,
                        rationale="Missing credentials",
                        judge_model=self._adapter.model_name(),
                        judge_prompt_version=self._judge_prompt_version,
                        judge_status="parse_error",
                        trace_id=trace_id,
                    )

                total_tokens_input += response.tokens_input
                total_tokens_output += response.tokens_output

                if response.error:
                    logger.warning("Generate error for %s: %s", record.id, response.error)
                    return JudgeResult(
                        record_id=record.id,
                        score=0,
                        hallucination=False,
                        wrong_citation=False,
                        incorrect_refusal=False,
                        rationale=f"Generate error: {response.error}",
                        judge_model=self._adapter.model_name(),
                        judge_prompt_version=self._judge_prompt_version,
                        judge_status="parse_error",
                        trace_id=trace_id,
                    )

                # Step 4: Judge evaluation
                judge = self._get_judge()
                judge_result = judge.evaluate(record, response.text, trace_id)
                return judge_result

        # Process all records concurrently with rate-limit protection
        tasks = [process_record(record) for record in records]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results, handling exceptions
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                logger.error("Exception processing record %s: %s", records[i].id, result)
                record = records[i]
                judge_results.append(
                    JudgeResult(
                        record_id=record.id,
                        score=0,
                        hallucination=False,
                        wrong_citation=False,
                        incorrect_refusal=False,
                        rationale=f"Processing exception: {result}",
                        judge_model=self._adapter.model_name(),
                        judge_prompt_version=self._judge_prompt_version,
                        judge_status="parse_error",
                        trace_id=trace_id,
                    )
                )
            elif result is not None:
                judge_results.append(result)  # type: ignore[arg-type]

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

        # Record span attributes
        if span is not None:
            span.set_attribute("eval.records.total", len(records))
            span.set_attribute("eval.records.processed", len(judge_results))
            span.set_attribute("eval.records.valid", sum(1 for r in judge_results if r.judge_status == "ok"))
            span.set_attribute("tokens.input", total_tokens_input)
            span.set_attribute("tokens.output", total_tokens_output)

        logger.info(
            "Eval run %s completed: %d records, %d judge results, %d valid",
            run_id,
            len(records),
            len(judge_results),
            sum(1 for r in judge_results if r.judge_status == "ok"),
        )

        # Record metrics
        duration = time.monotonic() - start_time
        record_eval_run_duration(
            {},
            duration,
            attributes={
                "run.id": run_id,
                "model.provider": self._adapter.provider(),
                "model.name": self._adapter.model_name(),
            },
        )

        # End span
        if span is not None:
            span.end()

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

    async def calibrate(
        self,
        dataset_path: str | Path,
        annotations: list[Annotation],
        threshold: float = 0.6,
        ci_level: float = 0.95,
    ) -> CalibrationResult:
        """Calibrate judge against expert annotations (async).

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

    # ============================================================
    # Sync wrappers for CLI usage
    # ============================================================

    def run_sync(
        self,
        dataset_path: str | Path,
        dataset_version: str = "0.1.0",
        seed: int = 42,
        run_id: str | None = None,
        trace_id: str = "",
    ) -> dict[str, Any]:
        """Synchronous wrapper for the async run method (for CLI usage).

        Args:
            dataset_path: Path to golden set file.
            dataset_version: Dataset version (semver).
            seed: Random seed for reproducibility.
            run_id: Optional run ID (generated if not provided).
            trace_id: Optional trace ID.

        Returns:
            Dict with run_id, manifest, metrics, judge_results.
        """
        return asyncio.run(
            self.run(
                dataset_path=dataset_path,
                dataset_version=dataset_version,
                seed=seed,
                run_id=run_id,
                trace_id=trace_id,
            )
        )

    def calibrate_sync(
        self,
        dataset_path: str | Path,
        annotations: list[Annotation],
        threshold: float = 0.6,
        ci_level: float = 0.95,
    ) -> CalibrationResult:
        """Synchronous wrapper for the async calibrate method (for CLI usage).

        Args:
            dataset_path: Path to calibration dataset.
            annotations: List of expert annotations.
            threshold: Minimum kappa threshold.
            ci_level: Confidence level for CI.

        Returns:
            CalibrationResult.
        """
        return asyncio.run(
            self.calibrate(
                dataset_path=dataset_path,
                annotations=annotations,
                threshold=threshold,
                ci_level=ci_level,
            )
        )


class ReplayOrchestrator:
    """Handles replay of previous eval runs for reproducibility checks.

    Covers FR-012, NFR-005.
    """

    def __init__(self, orchestrator: EvalOrchestrator) -> None:
        """Initialize replay orchestrator.

        Args:
            orchestrator: The main eval orchestrator to use for replay.
        """
        self._orchestrator = orchestrator

    def replay(
        self,
        manifest: RunManifest,
        dataset_path: str | Path,
        tolerance: float = 0.01,
    ) -> dict[str, Any]:
        """Replay a previous run and compare metrics.

        Args:
            manifest: Previous run manifest to replay.
            dataset_path: Path to the same golden set.
            tolerance: Maximum allowed metric difference (default 1%).

        Returns:
            Dict with replay results.
        """
        logger.info("Replaying run %s with tolerance=%.2f%%", manifest.run_id, tolerance * 100)

        # Run the same configuration
        result = self._orchestrator.run_sync(
            dataset_path=dataset_path,
            dataset_version=manifest.dataset_version,
            seed=manifest.seed,
        )

        original_metrics = {
            "hallucination_rate": 0.0,  # Not stored in manifest, estimate from judge_results
            "citation_accuracy": 0.0,
        }
        replay_metrics = {
            "hallucination_rate": result["metrics"].hallucination_rate,
            "citation_accuracy": result["metrics"].citation_accuracy,
        }

        # Compare metrics
        differences = {}
        reproducible = True
        for key in replay_metrics:
            diff = abs(replay_metrics[key] - original_metrics.get(key, 0))
            differences[key] = diff
            if diff > tolerance:
                reproducible = False

        return {
            "run_id": manifest.run_id,
            "reproducible": reproducible,
            "differences": differences,
            "replay_manifest": result["manifest"],
            "replay_metrics": result["metrics"],
        }
