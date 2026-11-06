"""Integration tests for metrics aggregation and calibration.

Covers T-1107, T-1108, FR-005, FR-006, TM-13.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from regulated_eval.judges.calibration import CalibrationEngine
from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.schemas import (
    Annotation,
    AnnotationSource,
    CalibrationResult,
    JudgeResult,
    MetricsBlock,
)


class TestMetricsAggregatorIntegration:
    """Integration tests for MetricsAggregator with realistic data."""

    def _create_judge_results(
        self,
        n: int = 10,
        hallucination_rate: float = 0.2,
        wrong_citation_rate: float = 0.1,
        incorrect_refusal_rate: float = 0.05,
        avg_score: float = 3.5,
    ) -> list[JudgeResult]:
        """Create a batch of judge results for testing."""
        results = []
        for i in range(n):
            has_hallucination = i < int(n * hallucination_rate)
            has_wrong_citation = (
                i >= int(n * hallucination_rate)
                and i < int(n * (hallucination_rate + wrong_citation_rate))
            )
            has_incorrect_refusal = (
                i >= int(n * (hallucination_rate + wrong_citation_rate))
                and i < int(n * (hallucination_rate + wrong_citation_rate + incorrect_refusal_rate))
            )

            score = max(1, min(5, int(avg_score + (i % 3) - 1)))

            results.append(JudgeResult(
                record_id=f"test_{i:03d}",
                score=score,
                hallucination=has_hallucination,
                wrong_citation=has_wrong_citation,
                incorrect_refusal=has_incorrect_refusal,
                rationale=f"Test rationale {i}",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
                trace_id="test-trace",
            ))
        return results

    def test_aggregate_basic(self) -> None:
        """Test basic metrics aggregation."""
        aggregator = MetricsAggregator()
        results = self._create_judge_results(n=10, hallucination_rate=0.3)

        metrics = aggregator.aggregate(results)

        assert isinstance(metrics, MetricsBlock)
        assert metrics.hallucination_rate == pytest.approx(0.3, abs=0.05)
        assert 0 <= metrics.citation_accuracy <= 1
        assert 0 <= metrics.refusal_correctness <= 1
        assert 0 <= metrics.factual_consistency <= 1

    def test_aggregate_by_category(self) -> None:
        """Test metrics grouped by category."""
        aggregator = MetricsAggregator()

        results = [
            JudgeResult(
                record_id="r1",
                score=5,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Good",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ),
            JudgeResult(
                record_id="r2",
                score=2,
                hallucination=True,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Bad",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ),
        ]

        categories = {"r1": "УСН", "r2": "НДС"}
        metrics = aggregator.aggregate(results, categories=categories)

        assert "УСН" in metrics.by_category
        assert "НДС" in metrics.by_category
        assert metrics.by_category["УСН"]["hallucination_rate"] == 0.0
        assert metrics.by_category["НДС"]["hallucination_rate"] == 1.0

    def test_aggregate_by_difficulty(self) -> None:
        """Test metrics grouped by difficulty."""
        aggregator = MetricsAggregator()

        results = [
            JudgeResult(
                record_id="r1",
                score=5,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Good",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ),
            JudgeResult(
                record_id="r2",
                score=1,
                hallucination=True,
                wrong_citation=True,
                incorrect_refusal=False,
                rationale="Bad",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ),
        ]

        difficulties = {"r1": "easy", "r2": "hard"}
        metrics = aggregator.aggregate(results, difficulties=difficulties)

        assert "easy" in metrics.by_difficulty
        assert "hard" in metrics.by_difficulty

    def test_aggregate_empty_results(self) -> None:
        """Test aggregation with empty results."""
        aggregator = MetricsAggregator()
        metrics = aggregator.aggregate([])

        assert metrics.hallucination_rate == 0.0
        assert metrics.citation_accuracy == 0.0

    def test_aggregate_parse_errors_filtered(self) -> None:
        """Test that parse errors are excluded from metrics."""
        aggregator = MetricsAggregator()

        results = [
            JudgeResult(
                record_id="r1",
                score=5,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Good",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
                judge_status="ok",
            ),
            JudgeResult(
                record_id="r2",
                score=0,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Parse error",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
                judge_status="parse_error",
            ),
        ]

        metrics = aggregator.aggregate(results)
        # Only r1 contributes (r2 is parse_error)
        assert metrics.hallucination_rate == 0.0
        assert metrics.citation_accuracy == 1.0

    def test_to_dataframe(self) -> None:
        """Test conversion to pandas DataFrame."""
        aggregator = MetricsAggregator()
        metrics = MetricsBlock(
            hallucination_rate=0.15,
            citation_accuracy=0.85,
            refusal_correctness=0.90,
            factual_consistency=0.80,
        )
        df = aggregator.to_dataframe(metrics)
        assert len(df) == 4
        assert "metric" in df.columns
        assert "value" in df.columns
        assert df.loc[0, "value"] == 0.15


class TestCalibrationEngineIntegration:
    """Integration tests for CalibrationEngine with realistic data."""

    def _create_judge_results_for_calibration(
        self,
        n: int = 10,
        agreement: float = 0.8,
    ) -> list[JudgeResult]:
        """Create judge results matching expert annotations."""
        results = []
        for i in range(n):
            # Ensure variety in scores to avoid NaN kappa
            if i < int(n * 0.3):
                score = 1
            elif i < int(n * 0.6):
                score = 3
            else:
                score = 5
            results.append(JudgeResult(
                record_id=f"cal_{i:03d}",
                score=score,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Calibration test",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ))
        return results

    def _create_annotations_for_calibration(
        self,
        n: int = 10,
        agreement: float = 0.8,
    ) -> list[Annotation]:
        """Create expert annotations matching judge results."""
        from datetime import datetime, timezone  # noqa: PLC0414

        annotations = []
        for i in range(n):
            # Ensure variety in scores to avoid NaN kappa
            if i < int(n * 0.3):
                score = 1
            elif i < int(n * 0.6):
                score = 3
            else:
                score = 5
            annotations.append(Annotation(
                record_id=f"cal_{i:03d}",
                score=score,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hash="a" * 64,
                prev_hash="b" * 64,
                source=AnnotationSource.HUMAN,
            ))
        return annotations

    def test_calibration_pass(self) -> None:
        """Test calibration passes with high agreement."""
        engine = CalibrationEngine()
        judge_results = self._create_judge_results_for_calibration(n=10, agreement=0.9)
        annotations = self._create_annotations_for_calibration(n=10, agreement=0.9)

        result = engine.compute_kappa(
            judge_results,
            annotations,
            threshold=0.6,
            n_bootstrap=100,  # Reduced for faster testing
        )

        assert result.status == "PASS"
        assert result.kappa >= 0.6
        assert result.agreement >= 0.8
        assert result.ci_level == 0.95

    def test_calibration_fail(self) -> None:
        """Test calibration fails with low agreement."""
        engine = CalibrationEngine()
        # Create very different distributions
        judge_results = [
            JudgeResult(
                record_id=f"cal_{i:03d}",
                score=5 if i < 5 else 1,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Calibration test",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            )
            for i in range(10)
        ]
        annotations = [
            Annotation(
                record_id=f"cal_{i:03d}",
                score=1 if i < 5 else 5,  # Inverse
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hash="a" * 64,
                prev_hash="b" * 64,
                source=AnnotationSource.HUMAN,
            )
            for i in range(10)
        ]

        from regulated_eval.exceptions import CalibrationFailed  # noqa: PLC0414

        with pytest.raises(CalibrationFailed):
            engine.compute_kappa(
                judge_results,
                annotations,
                threshold=0.6,
                n_bootstrap=100,
            )

    def test_calibration_no_matches(self) -> None:
        """Test calibration fails with no matched records."""
        engine = CalibrationEngine()
        judge_results = [
            JudgeResult(
                record_id="cal_001",
                score=5,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Test",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            ),
        ]
        annotations = [
            Annotation(
                record_id="cal_999",  # Different ID
                score=5,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hash="a" * 64,
                prev_hash="b" * 64,
                source=AnnotationSource.HUMAN,
            ),
        ]

        with pytest.raises(Exception):  # CalibrationFailed
            engine.compute_kappa(judge_results, annotations)

    def test_calibration_ci_bounds(self) -> None:
        """Test confidence interval bounds are valid."""
        engine = CalibrationEngine()
        judge_results = self._create_judge_results_for_calibration(n=20, agreement=0.85)
        annotations = self._create_annotations_for_calibration(n=20, agreement=0.85)

        result = engine.compute_kappa(
            judge_results,
            annotations,
            threshold=0.6,
            ci_level=0.95,
            n_bootstrap=100,
        )

        assert result.ci_low <= result.kappa <= result.ci_high
        assert 0 <= result.ci_low <= 1
        assert 0 <= result.ci_high <= 1

    def test_calibration_recommendations(self) -> None:
        """Test recommendations are generated on failure."""
        engine = CalibrationEngine()
        # Create very low agreement
        judge_results = [
            JudgeResult(
                record_id=f"cal_{i:03d}",
                score=5 - i,  # Inverse scores
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                rationale="Test",
                judge_model="yandexgpt",
                judge_prompt_version="v1",
            )
            for i in range(5)
        ]
        annotations = [
            Annotation(
                record_id=f"cal_{i:03d}",
                score=i + 1,  # Opposite scores
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                hash="a" * 64,
                prev_hash="b" * 64,
                source=AnnotationSource.HUMAN,
            )
            for i in range(5)
        ]

        with pytest.raises(Exception):
            engine.compute_kappa(
                judge_results,
                annotations,
                threshold=0.6,
                n_bootstrap=10,
            )
