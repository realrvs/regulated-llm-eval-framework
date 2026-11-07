"""Integration tests for judge calibration.

Covers TC-009, TC-010.
"""

import hashlib

import pytest

from regulated_eval.exceptions import CalibrationFailed
from regulated_eval.judges.calibration import CalibrationEngine
from regulated_eval.schemas import Annotation, AnnotationSource, JudgeResult


def _make_annotation(record_id: str, score: int) -> Annotation:
    hash_input = f"{record_id}:{score}:expert-1"
    h = hashlib.sha256(hash_input.encode()).hexdigest()
    return Annotation(
        record_id=record_id, score=score, hallucination=False,
        wrong_citation=False, incorrect_refusal=False,
        annotator_id="expert-1", hash=h, prev_hash="",
        source=AnnotationSource.HUMAN,
    )


def _make_judge_result(record_id: str, score: int) -> JudgeResult:
    return JudgeResult(
        record_id=record_id, score=score, hallucination=False,
        wrong_citation=False, incorrect_refusal=False,
        rationale="test", judge_model="test-judge",
        judge_prompt_version="v1", judge_status="ok", trace_id="test",
    )


class TestCalibrationEngine:
    """Test calibration engine."""

    def test_perfect_agreement(self):
        """Perfect agreement → PASS."""
        jr = [_make_judge_result(f"rec-{i}", 4) for i in range(10)]
        ann = [_make_annotation(f"rec-{i}", 4) for i in range(10)]
        engine = CalibrationEngine()
        result = engine.compute_kappa(jr, ann, threshold=0.6)
        assert result.status == "PASS"

    def test_empty_raises(self):
        """Empty results should raise CalibrationFailed."""
        engine = CalibrationEngine()
        with pytest.raises(CalibrationFailed):
            engine.compute_kappa([], [], threshold=0.6)
