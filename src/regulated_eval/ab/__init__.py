"""A/B testing with statistical significance.

Covers FR-008, TM-04.

Provides:
- Bootstrap confidence intervals
- Wilcoxon signed-rank test
- Cohen's d effect size
- Result interpretation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class ABResult:
    """Result of A/B test."""

    prompt_a: str = ""
    prompt_b: str = ""
    model_a: str = ""
    model_b: str = ""
    metric_a: float = 0.0
    metric_b: float = 0.0
    delta: float = 0.0
    p_value: float = 1.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    cohens_d: float = 0.0
    n_a: int = 0
    n_b: int = 0
    significant: bool = False
    winner: str = ""  # "a", "b", or "none"
    interpretation: str = ""


class ABTest:
    """A/B test with statistical significance testing.

    Uses:
    - Bootstrap CI (1000 iterations) for metric differences
    - Wilcoxon signed-rank test for p-value
    - Cohen's d for effect size
    """

    def __init__(
        self,
        n_bootstrap: int = 1000,
        alpha: float = 0.05,
        random_seed: int = 42,
    ) -> None:
        """Initialize A/B test.

        Args:
            n_bootstrap: Number of bootstrap iterations.
            alpha: Significance level (default 0.05).
            random_seed: Random seed for reproducibility.
        """
        self._n_bootstrap = n_bootstrap
        self._alpha = alpha
        self._rng = np.random.RandomState(random_seed)

    def run(
        self,
        scores_a: list[float],
        scores_b: list[float],
        prompt_a: str = "",
        prompt_b: str = "",
        model_a: str = "",
        model_b: str = "",
        higher_is_better: bool = True,
    ) -> ABResult:
        """Run A/B test between two sets of scores.

        Args:
            scores_a: Scores for variant A.
            scores_b: Scores for variant B.
            prompt_a: Prompt A identifier.
            prompt_b: Prompt B identifier.
            model_a: Model A name.
            model_b: Model B name.
            higher_is_better: Whether higher scores are better.

        Returns:
            ABResult with statistical analysis.
        """
        result = ABResult(
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            model_a=model_a,
            model_b=model_b,
            n_a=len(scores_a),
            n_b=len(scores_b),
        )

        if not scores_a or not scores_b:
            result.interpretation = "Insufficient data for A/B test"
            return result

        # Compute mean metrics
        result.metric_a = float(np.mean(scores_a))
        result.metric_b = float(np.mean(scores_b))
        result.delta = result.metric_b - result.metric_a

        # Bootstrap CI for delta
        ci_low, ci_high = self._bootstrap_ci(
            scores_a, scores_b, higher_is_better
        )
        result.ci_low = ci_low
        result.ci_high = ci_high

        # Wilcoxon signed-rank test
        # Pad shorter list with mean values for paired test
        min_len = min(len(scores_a), len(scores_b))
        if min_len >= 2:
            a_sample = scores_a[:min_len]
            b_sample = scores_b[:min_len]
            _, result.p_value = stats.wilcoxon(a_sample, b_sample)
        else:
            result.p_value = 1.0

        # Cohen's d effect size
        result.cohens_d = self._cohens_d(scores_a, scores_b)

        # Determine significance
        result.significant = result.p_value < self._alpha

        # Determine winner
        if result.significant:
            if higher_is_better:
                result.winner = "b" if result.delta > 0 else "a"
            else:
                result.winner = "b" if result.delta < 0 else "a"
        else:
            result.winner = "none"

        # Generate interpretation
        result.interpretation = self._interpret_result(result, higher_is_better)

        logger.info(
            "A/B test: delta=%.4f, p=%.4f, d=%.4f, significant=%s, winner=%s",
            result.delta,
            result.p_value,
            result.cohens_d,
            result.significant,
            result.winner,
        )

        return result

    def _bootstrap_ci(
        self,
        scores_a: list[float],
        scores_b: list[float],
        higher_is_better: bool,
    ) -> tuple[float, float]:
        """Compute bootstrap confidence interval for delta.

        Args:
            scores_a: Scores for variant A.
            scores_b: Scores for variant B.
            higher_is_better: Whether higher scores are better.

        Returns:
            Tuple of (ci_low, ci_high).
        """
        deltas = []
        min_len = min(len(scores_a), len(scores_b))

        for _ in range(self._n_bootstrap):
            indices = self._rng.randint(0, min_len, size=min_len)
            a_sample = [scores_a[i] for i in indices]
            b_sample = [scores_b[i] for i in indices]

            delta_a = np.mean(a_sample)
            delta_b = np.mean(b_sample)
            deltas.append(delta_b - delta_a)

        alpha = self._alpha
        ci_low = np.percentile(deltas, 100 * alpha / 2)
        ci_high = np.percentile(deltas, 100 * (1 - alpha / 2))

        return float(ci_low), float(ci_high)

    @staticmethod
    def _cohens_d(scores_a: list[float], scores_b: list[float]) -> float:
        """Compute Cohen's d effect size.

        Args:
            scores_a: Scores for variant A.
            scores_b: Scores for variant B.

        Returns:
            Cohen's d value.
        """
        n_a = len(scores_a)
        n_b = len(scores_b)

        if n_a < 2 or n_b < 2:
            return 0.0

        mean_a = np.mean(scores_a)
        mean_b = np.mean(scores_b)
        std_a = np.std(scores_a, ddof=1)
        std_b = np.std(scores_b, ddof=1)

        # Pooled standard deviation
        pooled_std = np.sqrt(
            ((n_a - 1) * std_a**2 + (n_b - 1) * std_b**2) / (n_a + n_b - 2)
        )

        if pooled_std == 0:
            return 0.0

        return float((mean_b - mean_a) / pooled_std)

    def _interpret_result(
        self,
        result: ABResult,
        higher_is_better: bool,
    ) -> str:
        """Interpret A/B test results.

        Args:
            result: ABResult to interpret.
            higher_is_better: Whether higher scores are better.

        Returns:
            Interpretation string.
        """
        if not result.significant:
            return (
                f"No statistically significant difference (p={result.p_value:.4f} >= 0.05). "
                f"Delta: {result.delta:+.4f} [{result.ci_low:.4f}, {result.ci_high:.4f}]. "
                f"Consider increasing dataset size."
            )

        direction = "higher" if higher_is_better else "lower"
        winner_name = "A" if result.winner == "a" else "B" if result.winner == "b" else "none"

        effect_size = abs(result.cohens_d)
        if effect_size < 0.2:
            effect_label = "negligible"
        elif effect_size < 0.5:
            effect_label = "small"
        elif effect_size < 0.8:
            effect_label = "medium"
        else:
            effect_label = "large"

        return (
            f"Statistically significant difference found (p={result.p_value:.4f} < 0.05). "
            f"Winner: {winner_name}. Delta: {result.delta:+.4f}. "
            f"Effect size: {effect_label} (d={result.cohens_d:+.4f})."
        )

    @property
    def n_bootstrap(self) -> int:
        """Number of bootstrap iterations."""
        return self._n_bootstrap

    @n_bootstrap.setter
    def n_bootstrap(self, value: int) -> None:
        """Set number of bootstrap iterations."""
        self._n_bootstrap = value
