"""Unit tests for Pydantic schemas.

Covers T-1101, FR-001, FR-004, FR-012, NFR-SEC-005.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regulated_eval.schemas import (
    AckSource,
    Annotation,
    AnnotationSource,
    CalibrationResult,
    Category,
    Difficulty,
    GoldenRecord,
    GoldenSetSummary,
    JudgeResult,
    MetricsBlock,
    RunManifest,
)


class TestGoldenRecord:
    """Tests for GoldenRecord schema."""

    def test_valid_record(self) -> None:
        """Test creation of a valid GoldenRecord."""
        record = GoldenRecord(
            id="test_001",
            question="What is USN tax rate?",
            reference_answer="6% of income or 1% of profits",
            citations=["НК РФ ст. 346.16"],
            category=Category.USN,
            difficulty=Difficulty.EASY,
            expert_validated=True,
        )
        assert record.id == "test_001"
        assert record.category == Category.USN
        assert record.expert_validated is True

    def test_content_hash_is_deterministic(self) -> None:
        """Test that content_hash is deterministic."""
        record1 = GoldenRecord(
            id="test_001",
            question="What is USN?",
            reference_answer="Simplified tax system",
            category=Category.USN,
            difficulty=Difficulty.EASY,
        )
        record2 = GoldenRecord(
            id="test_001",
            question="What is USN?",
            reference_answer="Simplified tax system",
            category=Category.USN,
            difficulty=Difficulty.EASY,
        )
        assert record1.content_hash == record2.content_hash

    def test_content_hash_changes_on_modification(self) -> None:
        """Test that content_hash changes when record changes."""
        record1 = GoldenRecord(
            id="test_001",
            question="What is USN?",
            reference_answer="Simplified tax system",
            category=Category.USN,
            difficulty=Difficulty.EASY,
        )
        record2 = GoldenRecord(
            id="test_001",
            question="What is VAT?",
            reference_answer="Value added tax",
            category=Category.VAT,
            difficulty=Difficulty.EASY,
        )
        assert record1.content_hash != record2.content_hash

    def test_empty_id_raises(self) -> None:
        """Test that empty ID raises validation error."""
        with pytest.raises(ValidationError):  # Pydantic ValidationError
            GoldenRecord(
                id="",
                question="Test",
                reference_answer="Answer",
                category=Category.USN,
                difficulty=Difficulty.EASY,
            )

    def test_citations_default_empty(self) -> None:
        """Test that citations defaults to empty list."""
        record = GoldenRecord(
            id="test_001",
            question="Test",
            reference_answer="Answer",
            category=Category.USN,
            difficulty=Difficulty.EASY,
        )
        assert record.citations == []


class TestJudgeResult:
    """Tests for JudgeResult schema."""

    def test_valid_judge_result(self) -> None:
        """Test creation of a valid JudgeResult."""
        result = JudgeResult(
            record_id="test_001",
            score=4,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            rationale="Good answer with correct citations",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            trace_id="abc123",
        )
        assert result.score == 4
        assert result.judge_status == "ok"

    def test_score_bounds(self) -> None:
        """Test score is within 1-5 bounds."""
        result = JudgeResult(
            record_id="test_001",
            score=1,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            rationale="Minimal",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            trace_id="abc123",
        )
        assert result.score == 1

    def test_parse_error_status(self) -> None:
        """Test parse_error status."""
        result = JudgeResult(
            record_id="test_001",
            score=0,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            rationale="Parse error",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            judge_status="parse_error",
            trace_id="abc123",
        )
        assert result.judge_status == "parse_error"


class TestRunManifest:
    """Tests for RunManifest schema."""

    def test_valid_manifest(self) -> None:
        """Test creation of a valid RunManifest."""
        manifest = RunManifest(
            run_id="run-001",
            dataset_version="1.0.0",
            dataset_content_hash="sha256:abc123",
            model_provider="yandexgpt",
            model_name="yandexgpt-lite",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            seed=42,
            package_version="0.1.0",
            tokens_input=1000,
            tokens_output=2000,
            trace_id="trace-001",
        )
        assert manifest.run_id == "run-001"
        assert manifest.estimated_cost_rub is None

    def test_hash_computation(self) -> None:
        """Test that hash is computed correctly."""
        manifest = RunManifest(
            run_id="run-001",
            dataset_version="1.0.0",
            dataset_content_hash="sha256:abc123",
            model_provider="yandexgpt",
            model_name="yandexgpt-lite",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            seed=42,
            package_version="0.1.0",
            tokens_input=1000,
            tokens_output=2000,
            trace_id="trace-001",
        )
        computed = manifest.compute_hash()
        assert len(computed) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in computed)

    def test_hash_verification(self) -> None:
        """Test hash verification."""
        manifest = RunManifest(
            run_id="run-001",
            dataset_version="1.0.0",
            dataset_content_hash="sha256:abc123",
            model_provider="yandexgpt",
            model_name="yandexgpt-lite",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            seed=42,
            package_version="0.1.0",
            tokens_input=1000,
            tokens_output=2000,
            trace_id="trace-001",
        )
        # Before setting hash, verification fails
        assert manifest.verify_hash() is False
        # After setting hash, verification passes
        manifest.hash = manifest.compute_hash()
        assert manifest.verify_hash() is True

    def test_ack_source_not_applicable(self) -> None:
        """Test default ack_source."""
        manifest = RunManifest(
            run_id="run-001",
            dataset_version="1.0.0",
            dataset_content_hash="sha256:abc123",
            model_provider="yandexgpt",
            model_name="yandexgpt-lite",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            seed=42,
            package_version="0.1.0",
            tokens_input=1000,
            tokens_output=2000,
            trace_id="trace-001",
        )
        assert manifest.ack_source == AckSource.NOT_APPLICABLE


class TestAnnotation:
    """Tests for Annotation schema with hash-chain integrity."""

    def test_valid_annotation(self) -> None:
        """Test creation of a valid Annotation."""
        annotation = Annotation(
            record_id="test_001",
            score=4,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
            hash="a" * 64,
            prev_hash="b" * 64,
            source=AnnotationSource.HUMAN,
        )
        assert annotation.annotator_id == "expert_01"
        assert annotation.source == AnnotationSource.HUMAN

    def test_hash_verification(self) -> None:
        """Test annotation hash verification."""

        ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        annotation = Annotation(
            record_id="test_001",
            score=4,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
            timestamp=ts,
            hash="",  # Will be computed
            prev_hash="b" * 64,
        )
        # Compute and set hash
        annotation.hash = annotation.compute_hash()
        assert annotation.verify_hash() is True

    def test_hash_tamper_detected(self) -> None:
        """Test that hash tampering is detected."""
        annotation = Annotation(
            record_id="test_001",
            score=4,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
            hash="a" * 64,
            prev_hash="b" * 64,
        )
        # Tamper with the score
        annotation.score = 1
        assert annotation.verify_hash() is False


class TestCalibrationResult:
    """Tests for CalibrationResult schema."""

    def test_pass_calibration(self) -> None:
        """Test PASS calibration result."""
        result = CalibrationResult(
            status="PASS",
            kappa=0.72,
            ci_low=0.58,
            ci_high=0.86,
            ci_level=0.95,
            agreement=0.85,
            threshold=0.6,
        )
        assert result.status == "PASS"
        assert result.kappa == 0.72

    def test_fail_calibration(self) -> None:
        """Test FAIL calibration result with recommendations."""
        result = CalibrationResult(
            status="FAIL",
            kappa=0.45,
            ci_low=0.30,
            ci_high=0.60,
            ci_level=0.95,
            agreement=0.65,
            threshold=0.6,
            recommendations=["Add few-shot examples", "Refine prompt"],
        )
        assert result.status == "FAIL"
        assert len(result.recommendations) == 2


class TestMetricsBlock:
    """Tests for MetricsBlock schema."""

    def test_valid_metrics(self) -> None:
        """Test creation of valid MetricsBlock."""
        block = MetricsBlock(
            hallucination_rate=0.15,
            citation_accuracy=0.85,
            refusal_correctness=0.90,
            factual_consistency=0.80,
        )
        assert block.hallucination_rate == 0.15

    def test_metrics_by_category(self) -> None:
        """Test metrics grouped by category."""
        block = MetricsBlock(
            hallucination_rate=0.15,
            citation_accuracy=0.85,
            refusal_correctness=0.90,
            factual_consistency=0.80,
            by_category={
                "УСН": {
                    "hallucination_rate": 0.10,
                    "citation_accuracy": 0.90,
                }
            },
        )
        assert "УСН" in block.by_category


class TestGoldenSetSummary:
    """Tests for GoldenSetSummary schema."""

    def test_valid_summary(self) -> None:
        """Test creation of valid GoldenSetSummary."""
        summary = GoldenSetSummary(
            version="1.0.0",
            content_hash="sha256:abc123",
            total_records=120,
            by_category={"УСН": 60, "НДС": 40, "взносы": 20},
            by_difficulty={"easy": 40, "medium": 50, "hard": 30},
            expert_validated_ratio=0.85,
        )
        assert summary.total_records == 120
        assert summary.expert_validated_ratio == 0.85
