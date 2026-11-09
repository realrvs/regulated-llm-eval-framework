"""Judge calibration with Cohen's kappa.

Covers FR-005, TM-13, ADR-003.

Calibrates the LLM-as-a-judge against human expert annotations
by computing Cohen's kappa with bootstrap confidence intervals.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from sklearn.metrics import accuracy_score, cohen_kappa_score  # type: ignore[import-untyped]

from regulated_eval.config import Config
from regulated_eval.exceptions import CalibrationFailed
from regulated_eval.schemas import (
    Annotation,
    CalibrationResult,
    JudgeResult,
)

logger = logging.getLogger(__name__)


class CalibrationEngine:
    """Engine for calibrating LLM judge against human annotations.

    Computes Cohen's kappa score with bootstrap confidence intervals.
    """

    def __init__(self, config: Config | None = None) -> None:
        """Initialize calibration engine.

        Args:
            config: Optional Config object.
        """
        self._config = config or Config()

    def compute_kappa(
        self,
        judge_results: list[JudgeResult],
        annotations: list[Annotation],
        threshold: float = 0.6,
        ci_level: float = 0.95,
        n_bootstrap: int = 1000,
        random_seed: int = 42,
    ) -> CalibrationResult:
        """Compute Cohen's kappa between judge and human annotations.

        Args:
            judge_results: Judge results to calibrate.
            annotations: Human expert annotations.
            threshold: Minimum kappa threshold for PASS.
            ci_level: Confidence level for bootstrap CI.
            n_bootstrap: Number of bootstrap iterations.
            random_seed: Random seed for reproducibility.

        Returns:
            CalibrationResult with status, kappa, CI, and recommendations.

        Raises:
            CalibrationFailed: If kappa is below threshold.
        """
        # Match judge results with annotations by record_id
        matched = self._match_results(judge_results, annotations)

        if not matched:
            raise CalibrationFailed("No matched judge results and annotations for calibration")

        judge_scores = [m["judge_score"] for m in matched]
        human_scores = [m["human_score"] for m in matched]

        # Compute Cohen's kappa
        # If all scores are the same, kappa is 1.0 (perfect agreement)
        if len(set(judge_scores)) == 1 and len(set(human_scores)) == 1:
            kappa = 1.0
        else:
            kappa = cohen_kappa_score(human_scores, judge_scores, weights="linear")
            if kappa != kappa:  # Handle NaN
                kappa = 0.0

        # Compute bootstrap confidence interval
        ci_low, ci_high = self._bootstrap_ci(judge_scores, human_scores, n_bootstrap, ci_level, random_seed)

        # Compute agreement rate
        agreement = accuracy_score(human_scores, judge_scores)

        # Determine status
        status: Literal["PASS", "FAIL"] = "PASS" if kappa >= threshold else "FAIL"

        # Generate recommendations
        recommendations = self._generate_recommendations(kappa, threshold, status)

        result = CalibrationResult(
            status=status,
            kappa=float(kappa),
            ci_low=float(ci_low),
            ci_high=float(ci_high),
            ci_level=ci_level,
            agreement=float(agreement),
            threshold=threshold,
            recommendations=recommendations,
        )

        logger.info(
            "Calibration: kappa=%.2f [%s CI %.2f-%.2f], agreement=%.2f, status=%s",
            kappa,
            int(ci_level * 100),
            ci_low,
            ci_high,
            agreement,
            status,
        )

        if status == "FAIL":
            raise CalibrationFailed(
                f"Judge calibration failed: kappa={kappa:.2f} < threshold={threshold}. "
                f"Recommendations: {'; '.join(recommendations)}"
            )

        return result

    def _match_results(
        self,
        judge_results: list[JudgeResult],
        annotations: list[Annotation],
    ) -> list[dict[str, int | str]]:
        """Match judge results with annotations by record_id."""
        annotation_map = {a.record_id: a for a in annotations}
        matched = []

        for jr in judge_results:
            if jr.record_id in annotation_map:
                ann = annotation_map[jr.record_id]
                matched.append(
                    {
                        "judge_score": jr.score,
                        "human_score": ann.score,
                        "record_id": jr.record_id,
                    }
                )

        return matched

    def _bootstrap_ci(
        self,
        judge_scores: list[int],
        human_scores: list[int],
        n_bootstrap: int,
        ci_level: float,
        seed: int,
    ) -> tuple[float, float]:
        """Compute bootstrap confidence interval for Cohen's kappa."""
        rng = np.random.RandomState(seed)
        n = len(judge_scores)
        if n == 0:
            return (0.0, 0.0)

        kappa_values = []

        for _ in range(n_bootstrap):
            # Bootstrap sample
            indices = rng.randint(0, n, size=n)
            j_sample = [judge_scores[i] for i in indices]
            h_sample = [human_scores[i] for i in indices]

            # Compute kappa for this sample
            if len(set(j_sample)) < 2 or len(set(h_sample)) < 2:
                continue

            kappa = cohen_kappa_score(h_sample, j_sample, weights="linear")
            kappa_values.append(kappa)

        if not kappa_values:
            return (0.0, 0.0)

        alpha = 1 - ci_level
        ci_low = np.percentile(kappa_values, 100 * alpha / 2)
        ci_high = np.percentile(kappa_values, 100 * (1 - alpha / 2))

        return (float(ci_low), float(ci_high))

    def _generate_recommendations(
        self,
        kappa: float,
        threshold: float,
        status: str,
    ) -> list[str]:
        """Generate recommendations for improving calibration."""
        if status == "PASS":
            return []

        recommendations = []

        if kappa < 0.4:
            recommendations.extend(
                [
                    "Add few-shot examples to judge prompt",
                    "Use chain-of-thought reasoning in judge prompt",
                    "Split evaluation into sub-tasks (accuracy, citation, hallucination)",
                ]
            )
        elif kappa < threshold:
            recommendations.extend(
                [
                    "Add more few-shot examples to judge prompt",
                    "Refine judge prompt with clearer criteria",
                    "Consider using a stronger judge model",
                ]
            )

        return recommendations
