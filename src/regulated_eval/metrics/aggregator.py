"""Metrics computation for LLM evaluation.

Covers FR-006.

Metrics:
- hallucination_rate: fraction of answers with hallucinations
- citation_accuracy: fraction of correct citations
- refusal_correctness: fraction of correct refusals
- factual_consistency: overall factual consistency score
"""

from __future__ import annotations

import logging

import pandas as pd

from regulated_eval.schemas import JudgeResult, MetricsBlock

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates judge results into summary metrics.

    Computes:
    - Overall metrics (hallucination_rate, citation_accuracy, etc.)
    - Metrics by category
    - Metrics by difficulty
    """

    def aggregate(
        self,
        judge_results: list[JudgeResult],
        categories: dict[str, str] | None = None,
        difficulties: dict[str, str] | None = None,
    ) -> MetricsBlock:
        """Aggregate judge results into metrics block.

        Args:
            judge_results: List of judge results to aggregate.
            categories: Optional mapping of record_id -> category.
            difficulties: Optional mapping of record_id -> difficulty.

        Returns:
            MetricsBlock with overall and grouped metrics.
        """
        if not judge_results:
            return MetricsBlock(
                hallucination_rate=0.0,
                citation_accuracy=0.0,
                refusal_correctness=0.0,
                factual_consistency=0.0,
            )

        # Filter out parse errors (they don't contribute to metrics)
        valid_results = [r for r in judge_results if r.judge_status == "ok"]

        if not valid_results:
            return MetricsBlock(
                hallucination_rate=0.0,
                citation_accuracy=0.0,
                refusal_correctness=0.0,
                factual_consistency=0.0,
            )

        # Compute overall metrics
        n = len(valid_results)
        hallucination_rate = sum(1 for r in valid_results if r.hallucination) / n
        citation_accuracy = sum(1 for r in valid_results if not r.wrong_citation) / n
        refusal_correctness = sum(1 for r in valid_results if not r.incorrect_refusal) / n

        # Factual consistency: score >= 3 and no hallucination
        factual_consistency = sum(1 for r in valid_results if r.score >= 3 and not r.hallucination) / n

        # Compute by category
        by_category: dict[str, dict[str, float]] = {}
        if categories:
            by_category = self._compute_grouped_metrics(valid_results, categories, "category")

        # Compute by difficulty
        by_difficulty: dict[str, dict[str, float]] = {}
        if difficulties:
            by_difficulty = self._compute_grouped_metrics(valid_results, difficulties, "difficulty")

        return MetricsBlock(
            hallucination_rate=round(hallucination_rate, 4),
            citation_accuracy=round(citation_accuracy, 4),
            refusal_correctness=round(refusal_correctness, 4),
            factual_consistency=round(factual_consistency, 4),
            by_category=by_category,
            by_difficulty=by_difficulty,
        )

    def _compute_grouped_metrics(
        self,
        results: list[JudgeResult],
        group_map: dict[str, str],
        group_name: str,
    ) -> dict[str, dict[str, float]]:
        """Compute metrics grouped by a dimension (category/difficulty)."""
        # Group results
        groups: dict[str, list[JudgeResult]] = {}
        for r in results:
            group = group_map.get(r.record_id, "unknown")
            if group not in groups:
                groups[group] = []
            groups[group].append(r)

        # Compute metrics per group
        result: dict[str, dict[str, float]] = {}
        for group_name_val, group_results in groups.items():
            n = len(group_results)
            if n == 0:
                continue
            result[group_name_val] = {
                "hallucination_rate": round(sum(1 for r in group_results if r.hallucination) / n, 4),
                "citation_accuracy": round(sum(1 for r in group_results if not r.wrong_citation) / n, 4),
                "refusal_correctness": round(sum(1 for r in group_results if not r.incorrect_refusal) / n, 4),
                "factual_consistency": round(
                    sum(1 for r in group_results if r.score >= 3 and not r.hallucination) / n,
                    4,
                ),
            }

        return result

    def to_dataframe(self, metrics: MetricsBlock) -> pd.DataFrame:
        """Convert metrics block to pandas DataFrame for reporting."""
        data = {
            "metric": [
                "hallucination_rate",
                "citation_accuracy",
                "refusal_correctness",
                "factual_consistency",
            ],
            "value": [
                metrics.hallucination_rate,
                metrics.citation_accuracy,
                metrics.refusal_correctness,
                metrics.factual_consistency,
            ],
        }
        df = pd.DataFrame(data)
        return df
