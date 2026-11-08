"""Unit tests for LLM-as-a-judge evaluator.

Covers TC-007, TC-008.
"""

import json

from regulated_eval.adapters.base import LLMRequest, LLMResponse
from regulated_eval.config import Config
from regulated_eval.judges.judge import JUDGE_PROMPT_TEMPLATE, Judge
from regulated_eval.schemas import Category, Difficulty, GoldenRecord, JudgeResult


class MockJudgeAdapter:
    """Mock adapter for judge tests."""

    def __init__(self, response_text: str, error: str = None):
        self._response_text = response_text
        self._error = error

    def generate_sync(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=self._response_text,
            model="test-judge",
            tokens_input=100,
            tokens_output=50,
            error=self._error,
        )

    def provider(self) -> str:
        return "test"

    def model_name(self) -> str:
        return "test-judge"


def _make_record(record_id: str = "test-1") -> GoldenRecord:
    return GoldenRecord(
        id=record_id,
        question="What is USN?",
        reference_answer="Unified Simplified Tax",
        citations=["НК РФ Art. 346.11"],
        category=Category.USN,
        difficulty=Difficulty.EASY,
    )


class TestJudgePrompt:
    """Test judge prompt template."""

    def test_prompt_contains_all_sections(self):
        template = JUDGE_PROMPT_TEMPLATE
        assert "## Question" in template
        assert "## Reference Answer" in template
        assert "## Model Answer" in template
        assert "## Citations" in template
        assert "## Evaluation Criteria" in template

    def test_prompt_format(self):
        record = _make_record()
        judge = Judge(adapter=MockJudgeAdapter("{}"), config=Config())
        prompt = judge._build_prompt(record, "USN is a tax system")
        assert "What is USN?" in prompt
        assert "Unified Simplified Tax" in prompt
        assert "USN is a tax system" in prompt


class TestJudgeEvaluate:
    """Test judge evaluate method."""

    def test_parse_valid_json(self):
        adapter = MockJudgeAdapter(
            '{"score": 4, "hallucination": false, "wrong_citation": false, "incorrect_refusal": false, "rationale": "Good answer"}'
        )
        judge = Judge(adapter=adapter, config=Config())

        result = judge.evaluate(_make_record(), "Answer text", trace_id="trace-1")

        assert isinstance(result, JudgeResult)
        assert result.score == 4
        assert result.hallucination is False
        assert result.wrong_citation is False
        assert result.incorrect_refusal is False
        assert result.rationale == "Good answer"
        assert result.judge_status == "ok"
        assert result.trace_id == "trace-1"

    def test_parse_json_with_code_block(self):
        adapter = MockJudgeAdapter(
            '```json\n{"score": 3, "hallucination": true, "wrong_citation": false, "incorrect_refusal": false, "rationale": "Has hallucinations"}\n```'
        )
        judge = Judge(adapter=adapter, config=Config())

        result = judge.evaluate(_make_record(), "Bad answer", trace_id="trace-1")

        assert result.score == 3
        assert result.hallucination is True

    def test_parse_error_returns_error_result(self):
        adapter = MockJudgeAdapter("not valid json at all")
        judge = Judge(adapter=adapter, config=Config())

        result = judge.evaluate(_make_record(), "Answer", trace_id="trace-1")

        assert result.judge_status == "parse_error"
        assert result.score == 0
        assert "Parse error" in result.rationale

    def test_adapter_error_returns_error_result(self):
        adapter = MockJudgeAdapter("", error="Connection timeout")
        judge = Judge(adapter=adapter, config=Config())

        result = judge.evaluate(_make_record(), "Answer", trace_id="trace-1")

        assert result.judge_status == "parse_error"
        assert "Connection timeout" in result.rationale

    def test_score_range(self):
        """Score should be between 1 and 5."""
        for score in [1, 2, 3, 4, 5]:
            adapter = MockJudgeAdapter(
                json.dumps(
                    {
                        "score": score,
                        "hallucination": False,
                        "wrong_citation": False,
                        "incorrect_refusal": False,
                        "rationale": "test",
                    }
                )
            )
            judge = Judge(adapter=adapter, config=Config())

            result = judge.evaluate(_make_record(), "Answer", trace_id="trace-1")
            assert result.score == score

    def test_missing_fields_defaults(self):
        """Missing fields in JSON should use defaults."""
        adapter = MockJudgeAdapter('{"score": 4, "rationale": "default rationale"}')
        judge = Judge(adapter=adapter, config=Config())

        result = judge.evaluate(_make_record(), "Answer", trace_id="trace-1")

        assert result.score == 4
        assert result.hallucination is False  # default
        assert result.wrong_citation is False  # default
        assert result.incorrect_refusal is False  # default
