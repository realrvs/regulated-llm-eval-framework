"""Integration tests for A/B testing and CLI.

Covers T-1115, T-1116, FR-008, FR-014.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from regulated_eval.ab import ABTest
from regulated_eval.schemas import Category, Difficulty


class TestABTestIntegration:
    """Integration tests for A/B testing with statistical analysis."""

    def test_ab_test_with_clear_winner(self) -> None:
        """Test A/B test with significant difference."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        # Variant A: mean ~3.0
        scores_a = [3.0 + (i % 3) - 1 for i in range(50)]
        # Variant B: mean ~4.0
        scores_b = [4.0 + (i % 3) - 1 for i in range(50)]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
            prompt_a="prompt_v1",
            prompt_b="prompt_v2",
            model_a="yandexgpt-lite",
            model_b="yandexgpt-lite",
            higher_is_better=True,
        )

        assert result.prompt_a == "prompt_v1"
        assert result.prompt_b == "prompt_v2"
        assert result.metric_a == pytest.approx(3.0, abs=0.1)
        assert result.metric_b == pytest.approx(4.0, abs=0.1)
        assert result.delta > 0
        assert result.significant
        assert result.winner == "b"
        assert "significant" in result.interpretation.lower()

    def test_ab_test_no_significant_difference(self) -> None:
        """Test A/B test with no significant difference."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        # Similar distributions
        scores_a = [3.5 + (i % 3) - 1 for i in range(100)]
        scores_b = [3.5 + (i % 3) - 1 for i in range(100)]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
            higher_is_better=True,
        )

        assert result.metric_a == pytest.approx(3.5, abs=0.1)
        assert result.metric_b == pytest.approx(3.5, abs=0.1)
        assert result.delta == pytest.approx(0.0, abs=0.1)
        assert not result.significant
        assert result.winner == "none"

    def test_ab_test_lower_is_better(self) -> None:
        """Test A/B test with lower-is-better metric."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        # Variant A: higher hallucination rate
        scores_a = [0.3 + (i % 5) * 0.02 for i in range(50)]
        # Variant B: lower hallucination rate
        scores_b = [0.1 + (i % 5) * 0.02 for i in range(50)]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
            higher_is_better=False,  # Lower hallucination is better
        )

        assert result.delta < 0  # B is lower
        assert result.significant
        assert result.winner == "b"  # B has lower hallucination

    def test_ab_test_effect_size(self) -> None:
        """Test Cohen's d effect size calculation."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        # Large effect: very different means with some variance
        scores_a = [1.0 + (i % 5) * 0.1 for i in range(50)]
        scores_b = [5.0 + (i % 5) * 0.1 for i in range(50)]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
        )

        # Large effect size
        assert abs(result.cohens_d) > 1.0

    def test_ab_test_small_sample(self) -> None:
        """Test A/B test with small sample size."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        scores_a = [3.0, 4.0, 5.0]
        scores_b = [2.0, 3.0, 4.0]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
        )

        # Should still work, but may not be significant
        assert result.n_a == 3
        assert result.n_b == 3
        assert result.metric_a == pytest.approx(4.0, abs=0.1)
        assert result.metric_b == pytest.approx(3.0, abs=0.1)

    def test_ab_test_empty_data(self) -> None:
        """Test A/B test with empty data."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        result = ab_test.run(
            scores_a=[],
            scores_b=[3.0, 4.0, 5.0],
        )

        assert result.interpretation == "Insufficient data for A/B test"
        assert result.winner == ""

    def test_ab_test_ci_bounds(self) -> None:
        """Test confidence interval bounds are valid."""
        ab_test = ABTest(n_bootstrap=100, random_seed=42)

        scores_a = [3.0 + (i % 3) - 1 for i in range(100)]
        scores_b = [3.5 + (i % 3) - 1 for i in range(100)]

        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
        )

        assert result.ci_low <= result.delta <= result.ci_high


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def _create_sample_dataset(self, tmp_path: Path) -> Path:
        """Create a sample golden set for CLI testing."""
        import json  # noqa: PLC0414

        records = [
            {
                "id": "cli_001",
                "question": "Какая ставка УСН?",
                "reference_answer": "6%",
                "category": Category.USN.value,
                "difficulty": Difficulty.EASY.value,
                "expert_validated": True,
            },
            {
                "id": "cli_002",
                "question": "Какая ставка НДС?",
                "reference_answer": "20%",
                "category": Category.VAT.value,
                "difficulty": Difficulty.MEDIUM.value,
                "expert_validated": True,
            },
        ]

        file_path = tmp_path / "cli_test.jsonl"
        file_path.write_text(
            "\n".join(json.dumps(r) for r in records),
            encoding="utf-8",
        )
        return file_path

    def test_dataset_load_command(self, tmp_path: Path) -> None:
        """Test dataset load CLI command."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414

        runner = CliRunner()
        dataset_path = self._create_sample_dataset(tmp_path)

        result = runner.invoke(
            app,
            ["dataset-load", "-p", str(dataset_path)],
        )

        assert result.exit_code == 0
        assert "Dataset loaded" in result.stdout
        assert "2 records" in result.stdout
        assert "Version:" in result.stdout

    def test_dataset_load_invalid_file(self, tmp_path: Path) -> None:
        """Test dataset load with invalid file."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["dataset-load", "--path", str(tmp_path / "nonexistent.jsonl")],
        )

        assert result.exit_code == 2
        assert "Error" in result.stdout or result.exit_code != 0

    def test_dataset_list_command(self, tmp_path: Path) -> None:
        """Test dataset list CLI command."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414

        runner = CliRunner()

        # Create a dataset directory with files
        dataset_dir = tmp_path / "datasets"
        dataset_dir.mkdir()

        import json  # noqa: PLC0414

        from regulated_eval.schemas import Category, Difficulty  # noqa: PLC0414

        records = [
            {
                "id": "list_001",
                "question": "Test",
                "reference_answer": "Answer",
                "category": Category.USN.value,
                "difficulty": Difficulty.EASY.value,
                "expert_validated": True,
            },
        ]

        (dataset_dir / "test.jsonl").write_text(
            json.dumps(records[0]),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["dataset-list", "--dir", str(dataset_dir)],
        )

        assert result.exit_code == 0
        assert "Available datasets" in result.stdout

    def test_annotations_verify_command(self, tmp_path: Path) -> None:
        """Test annotations verify CLI command."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414
        from regulated_eval.human_loop.annotation_store import AnnotationStore  # noqa: PLC0414

        runner = CliRunner()

        # Create valid annotation store
        store = AnnotationStore(storage_path=tmp_path / "annotations")
        prev_hash = ""
        for i in range(3):
            annotation = store.create_annotation(
                record_id=f"verify_{i:03d}",
                score=5 - i,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                prev_hash=prev_hash,
            )
            store.save_annotation(annotation)
            prev_hash = annotation.hash

        result = runner.invoke(
            app,
            ["annotations-verify", "--path", str(tmp_path / "annotations")],
        )

        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_version_flag(self) -> None:
        """Test --version flag."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414

        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "1.0.0" in result.stdout

    def test_run_command_requires_model(self) -> None:
        """Test run command requires --model flag."""
        from typer.testing import CliRunner  # noqa: PLC0414

        from regulated_eval.cli import app  # noqa: PLC0414

        runner = CliRunner()
        result = runner.invoke(app, ["run"])

        # Should fail due to missing required --model argument
        assert result.exit_code != 0
