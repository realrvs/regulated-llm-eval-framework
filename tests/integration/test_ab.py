"""Integration tests for A/B testing.

Covers TC-015, TC-016.
"""

from regulated_eval.ab import ABTest


class TestABTestIntegration:
    """Test A/B test integration."""

    def test_significant_improvement(self):
        """Model B significantly better than A."""
        scores_a = [3.0, 3.5, 4.0, 3.0, 3.5] * 20  # mean ~3.4
        scores_b = [4.0, 4.5, 5.0, 4.0, 4.5] * 20  # mean ~4.4

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert result.significant
        assert result.delta > 0
        assert result.winner.lower() == "b"
        assert result.p_value < 0.05

    def test_no_significant_difference(self):
        """No significant difference between models."""
        scores_a = [3.5, 4.0, 3.5, 4.0, 3.5] * 20  # mean ~3.7
        scores_b = [3.5, 4.0, 3.5, 4.0, 3.5] * 20  # same as A

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert not result.significant
        assert result.winner.lower() == "none"
        assert "significant" in result.interpretation.lower()

    def test_model_a_better(self):
        """Model A is better than B."""
        scores_a = [4.5, 5.0, 4.5, 5.0] * 20  # mean ~4.75
        scores_b = [3.0, 3.5, 3.0, 3.5] * 20  # mean ~3.25

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert result.significant
        assert result.delta < 0  # B - A is negative
        assert result.winner.lower() == "a"

    def test_ci_bounds(self):
        """Confidence interval should contain delta."""
        scores_a = [3.0, 3.5, 4.0] * 30
        scores_b = [3.5, 4.0, 4.5] * 30

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert result.ci_low <= result.delta <= result.ci_high

    def test_cohens_d_calculation(self):
        """Cohen's d should be calculated."""
        scores_a = [2.5, 3.0, 3.5, 3.0] * 20
        scores_b = [4.5, 5.0, 4.5, 5.0] * 20

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert abs(result.cohens_d) > 0  # Should be large effect

    def test_small_sample(self):
        """Small sample sizes should still work."""
        scores_a = [3.0, 4.0]
        scores_b = [4.0, 5.0]

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert result.n_a == 2
        assert result.n_b == 2
        # With tiny samples, may not be significant
        assert result.winner in ("A", "B", "none")

    def test_identical_scores(self):
        """Identical scores → delta = 0, not significant."""
        scores_a = [4.0] * 10
        scores_b = [4.0] * 10

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert result.delta == 0.0
        assert not result.significant
        assert result.winner == "none"

    def test_interpretation_present(self):
        """Result should have interpretation text."""
        scores_a = [3.0] * 10
        scores_b = [4.0] * 10

        ab = ABTest()
        result = ab.run(scores_a, scores_b, "prompt_a", "prompt_b", "model_a", "model_b")

        assert isinstance(result.interpretation, str)
        assert len(result.interpretation) > 0
