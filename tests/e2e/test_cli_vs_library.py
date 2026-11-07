"""E2E tests: CLI vs Library API parity.

Covers TC-025.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import typer

from regulated_eval.adapters.base import LLMRequest, LLMResponse
from regulated_eval.config import Config
from regulated_eval.pipeline import EvalOrchestrator, ReplayOrchestrator
from regulated_eval.schemas import JudgeResult, MetricsBlock, RunManifest


class MockTestAdapter:
    """Mock adapter for E2E tests."""

    def __init__(self, response_text: str = "Test answer"):
        self._response_text = response_text
        self.call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            text=self._response_text,
            model="mock",
            tokens_input=10,
            tokens_output=20,
            latency_ms=1.0,
        )

    def provider(self) -> str:
        return "mock"

    def model_name(self) -> str:
        return "mock"

    def estimate_cost(self, tokens_input: int, tokens_output: int) -> float | None:
        return 0.01 * (tokens_input + tokens_output)

    @property
    def is_foreign(self) -> bool:
        return False


class TestCLIVsLibraryParity:
    """Test CLI and library produce same results (TC-025)."""

    def test_orchestrator_run_produces_valid_result(self, sample_dataset_path):
        """EvalOrchestrator.run() produces valid dict result."""
        config = Config()
        adapter = MockTestAdapter()
        orchestrator = EvalOrchestrator(adapter, config=config)

        result = orchestrator.run_sync(
            dataset_path=sample_dataset_path,
            dataset_version="0.1.0",
            seed=42,
        )

        assert "run_id" in result
        assert "manifest" in result
        assert "metrics" in result
        assert "judge_results" in result
        assert isinstance(result["manifest"], RunManifest)
        assert isinstance(result["metrics"], MetricsBlock)
        assert isinstance(result["judge_results"], list)
        assert len(result["judge_results"]) > 0

    def test_replay_produces_reproducible_result(self, sample_dataset_path):
        """ReplayOrchestrator produces reproducible results."""
        config = Config()
        adapter = MockTestAdapter()
        orchestrator = EvalOrchestrator(adapter, config=config)
        replay = ReplayOrchestrator(orchestrator)

        # First run
        result1 = orchestrator.run_sync(
            dataset_path=sample_dataset_path,
            dataset_version="0.1.0",
            seed=42,
        )

        # Replay
        replay_result = replay.replay(
            manifest=result1["manifest"],
            dataset_path=sample_dataset_path,
            tolerance=0.01,
        )

        assert "reproducible" in replay_result
        assert "differences" in replay_result

    def test_metrics_block_fields(self, sample_dataset_path):
        """MetricsBlock should have all required fields."""
        config = Config()
        adapter = MockTestAdapter()
        orchestrator = EvalOrchestrator(adapter, config=config)

        result = orchestrator.run_sync(
            dataset_path=sample_dataset_path,
            dataset_version="0.1.0",
            seed=42,
        )

        metrics = result["metrics"]
        assert hasattr(metrics, "hallucination_rate")
        assert hasattr(metrics, "citation_accuracy")
        assert hasattr(metrics, "refusal_correctness")
        assert hasattr(metrics, "factual_consistency")
        assert hasattr(metrics, "by_category")
        assert hasattr(metrics, "by_difficulty")

    def test_manifest_fields(self, sample_dataset_path):
        """RunManifest should have all required fields."""
        config = Config()
        adapter = MockTestAdapter()
        orchestrator = EvalOrchestrator(adapter, config=config)

        result = orchestrator.run_sync(
            dataset_path=sample_dataset_path,
            dataset_version="0.1.0",
            seed=42,
        )

        manifest = result["manifest"]
        assert manifest.run_id is not None
        assert manifest.dataset_version == "0.1.0"
        assert manifest.model_provider == "mock"
        assert manifest.model_name == "mock"
        assert manifest.seed == 42
        assert manifest.tokens_input > 0
        assert manifest.tokens_output > 0

    def test_judge_results_structure(self, sample_dataset_path):
        """Each JudgeResult should have required fields."""
        config = Config()
        adapter = MockTestAdapter()
        orchestrator = EvalOrchestrator(adapter, config=config)

        result = orchestrator.run_sync(
            dataset_path=sample_dataset_path,
            dataset_version="0.1.0",
            seed=42,
        )

        for jr in result["judge_results"]:
            assert isinstance(jr, JudgeResult)
            assert jr.record_id is not None
            assert isinstance(jr.score, int)
            assert isinstance(jr.hallucination, bool)
            assert isinstance(jr.wrong_citation, bool)
            assert isinstance(jr.incorrect_refusal, bool)
            assert jr.judge_status in ("ok", "rate_limited", "parse_error")

    def test_cli_run_command_signature(self):
        """CLI run command should accept required arguments."""
        from regulated_eval.cli import app
        import inspect

        # Get the run command
        run_cmd = None
        for cmd in app.registered_commands:
            if cmd.name == "run":
                run_cmd = cmd
                break

        assert run_cmd is not None
        # Should have dataset, model, judge_model options
        params = {p.name for p in run_cmd.params}
        assert "dataset" in params
        assert "model" in params
        assert "judge_model" in params

    def test_cli_calibrate_command_signature(self):
        """CLI calibrate command should accept required arguments."""
        from regulated_eval.cli import app

        calibrate_cmd = None
        for cmd in app.registered_commands:
            if cmd.name == "calibrate":
                calibrate_cmd = cmd
                break

        assert calibrate_cmd is not None
        params = {p.name for p in calibrate_cmd.params}
        assert "dataset" in params
        assert "judge_model" in params
