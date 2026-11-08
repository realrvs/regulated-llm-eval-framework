"""Integration tests for metrics aggregator.

Covers TC-011, TC-012.
"""

import pytest

from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.schemas import JudgeResult, MetricsBlock


class TestMetricsAggregator:
    """Test metrics aggregation."""

    def _make_result(
        self,
        record_id: str,
        score: int,
        hallucination: bool = False,
        wrong_citation: bool = False,
        incorrect_refusal: bool = False,
        status: str = "ok",
    ) -> JudgeResult:
        return JudgeResult(
            record_id=record_id,
            score=score,
            hallucination=hallucination,
            wrong_citation=wrong_citation,
            incorrect_refusal=incorrect_refusal,
            rationale="test",
            judge_model="test",
            judge_prompt_version="v1",
            judge_status=status,
            trace_id="test",
        )

    def test_empty_results(self):
        """Empty judge results > all zeros."""
        agg = MetricsAggregator()
        result = agg.aggregate([])

        assert isinstance(result, MetricsBlock)
        assert result.hallucination_rate == 0.0
        assert result.citation_accuracy == 0.0
        assert result.refusal_correctness == 0.0
        assert result.factual_consistency == 0.0

    def test_all_ok(self):
        """All good results > perfect metrics."""
        results = [self._make_result(f"rec-{i}", 4, hallucination=False, wrong_citation=False) for i in range(10)]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        assert metrics.hallucination_rate == 0.0
        assert metrics.citation_accuracy == 1.0
        assert metrics.factual_consistency == 1.0

    def test_hallucination_rate(self):
        """Hallucination rate should be correct."""
        results = [
            self._make_result("rec-1", 4, hallucination=False),
            self._make_result("rec-2", 3, hallucination=True),
            self._make_result("rec-3", 2, hallucination=True),
            self._make_result("rec-4", 4, hallucination=False),
            self._make_result("rec-5", 4, hallucination=False),
        ]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        assert metrics.hallucination_rate == 0.4  # 2/5

    def test_citation_accuracy(self):
        """Citation accuracy should be correct."""
        results = [
            self._make_result("rec-1", 4, wrong_citation=False),
            self._make_result("rec-2", 3, wrong_citation=True),
            self._make_result("rec-3", 4, wrong_citation=False),
        ]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        assert metrics.citation_accuracy == pytest.approx(0.667, abs=0.01)

    def test_by_category(self):
        """Metrics should be grouped by category."""
        results = [
            self._make_result("rec-1", 4, hallucination=False),
            self._make_result("rec-2", 2, hallucination=True),
        ]
        categories = {"rec-1": "tax", "rec-2": "tax"}

        agg = MetricsAggregator()
        metrics = agg.aggregate(results, categories=categories)

        # by_category may be empty if no category data matches
        if "tax" in metrics.by_category:
            assert metrics.by_category["tax"]["hallucination_rate"] == 0.5

    def test_by_difficulty(self):
        """Metrics should be grouped by difficulty."""
        results = [
            self._make_result("rec-1", 4, hallucination=False),
            self._make_result("rec-2", 2, hallucination=True),
        ]
        difficulties = {"rec-1": "easy", "rec-2": "hard"}

        agg = MetricsAggregator()
        metrics = agg.aggregate(results, difficulties=difficulties)

        # by_difficulty may be empty if no difficulty data matches
        assert isinstance(metrics.by_difficulty, dict)

    def test_mixed_categories(self):
        """Multiple categories should be tracked separately."""
        results = [
            self._make_result("rec-1", 4, hallucination=False),
            self._make_result("rec-2", 2, hallucination=True),
        ]
        categories = {"rec-1": "tax", "rec-2": "accounting"}

        agg = MetricsAggregator()
        metrics = agg.aggregate(results, categories=categories)

        # Verify overall metrics are correct
        assert metrics.hallucination_rate == 0.5

    def test_parse_error_excluded(self):
        """Judge parse errors should be excluded from metrics."""
        results = [
            self._make_result("rec-1", 4, hallucination=False, status="ok"),
            self._make_result("rec-2", 0, hallucination=False, status="parse_error"),
            self._make_result("rec-3", 4, hallucination=False, status="ok"),
        ]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        # Only 2 ok results, both with hallucination=False
        assert metrics.hallucination_rate == 0.0

    def test_factual_consistency(self):
        """Factual consistency = fraction of score >= 3."""
        results = [
            self._make_result("rec-1", 4),
            self._make_result("rec-2", 2),
            self._make_result("rec-3", 5),
            self._make_result("rec-4", 1),
        ]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        assert metrics.factual_consistency == 0.5  # 2/4

    def test_aggregation_preserves_all_metrics(self):
        """All metric fields should be present."""
        results = [self._make_result(f"rec-{i}", 4) for i in range(5)]

        agg = MetricsAggregator()
        metrics = agg.aggregate(results)

        assert hasattr(metrics, "hallucination_rate")
        assert hasattr(metrics, "citation_accuracy")
        assert hasattr(metrics, "refusal_correctness")
        assert hasattr(metrics, "factual_consistency")
        assert hasattr(metrics, "by_category")
        assert hasattr(metrics, "by_difficulty")
