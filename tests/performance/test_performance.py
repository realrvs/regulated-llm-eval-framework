"""Performance tests for key operations.

Covers TC-028, TC-030, TC-034, TC-040, TC-041.
"""

import time

from regulated_eval.adapters.base import BaseAdapter, LLMRequest, LLMResponse
from regulated_eval.datasets.loader import load_golden_set
from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.schemas import JudgeResult
from regulated_eval.security.injection_filter import InjectionFilter
from regulated_eval.security.pii_redactor import PIIRedactor


class MockFastAdapter(BaseAdapter):
    """Mock adapter that returns instantly."""

    def __init__(self, response_text: str = "Test answer"):
        self._response_text = response_text

    async def generate(self, request: LLMRequest) -> LLMResponse:
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


class TestPIIRedactionPerformance:
    """Test PII redaction performance (TC-034)."""

    def test_redact_single_field(self):
        redactor = PIIRedactor(enable_fio=True, enable_address=True)
        text = "Мой ИНН 7707083893 и телефон +7 (999) 123-45-67"

        start = time.monotonic()
        result = redactor.redact(text)
        duration = time.monotonic() - start

        assert result.redacted_text != text
        assert "ИНН" in result.redacted_text or "[INN]" in result.redacted_text
        assert duration < 0.1  # Should be very fast

    def test_redact_multiple_fields(self):
        redactor = PIIRedactor(enable_fio=True, enable_address=True)
        text = "ФИО: Иванов Иван Иванович, СНИЛС: 123-456-789 01, паспорт 45 12 123456"

        start = time.monotonic()
        redactor.redact(text)
        duration = time.monotonic() - start

        assert duration < 0.1

    def test_redact_large_text(self):
        """Redaction should handle large texts."""
        redactor = PIIRedactor(enable_fio=True, enable_address=True)
        text = "Вопрос: " + " ".join(["Какие документы нужны для УСН?"] * 100)

        start = time.monotonic()
        redactor.redact(text)
        duration = time.monotonic() - start

        assert duration < 0.5


class TestMetricsAggregationPerformance:
    """Test metrics aggregation performance (TC-040, TC-041)."""

    def _make_result(
        self, record_id: str, score: int, hallucination: bool = False, wrong_citation: bool = False
    ) -> JudgeResult:
        return JudgeResult(
            record_id=record_id,
            score=score,
            hallucination=hallucination,
            wrong_citation=wrong_citation,
            incorrect_refusal=False,
            rationale="test",
            judge_model="test",
            judge_prompt_version="v1",
            judge_status="ok",
            trace_id="test",
        )

    def test_aggregate_150_records(self):
        """Aggregate 150 records (typical eval run) within 1 second."""
        results = [
            self._make_result(f"rec-{i}", 4 if i % 3 != 0 else 2, hallucination=i % 5 == 0, wrong_citation=i % 7 == 0)
            for i in range(150)
        ]
        categories = {f"rec-{i}": ["tax", "accounting", "legal"][i % 3] for i in range(150)}
        difficulties = {f"rec-{i}": ["easy", "medium", "hard"][i % 3] for i in range(150)}

        start = time.monotonic()
        agg = MetricsAggregator()
        metrics = agg.aggregate(results, categories, difficulties)
        duration = time.monotonic() - start

        assert duration < 1.0
        assert metrics.hallucination_rate >= 0.0
        assert metrics.citation_accuracy >= 0.0

    def test_aggregate_1000_records(self):
        """Aggregate 1000 records within 5 seconds."""
        results = [self._make_result(f"rec-{i}", 4) for i in range(1000)]

        start = time.monotonic()
        agg = MetricsAggregator()
        agg.aggregate(results)
        duration = time.monotonic() - start

        assert duration < 5.0


class TestInjectionFilterPerformance:
    """Test injection filter performance (TC-028)."""

    def test_check_fast_text(self):
        filter_ = InjectionFilter(enabled=True)
        text = "Простой вопрос без ссылок"

        start = time.monotonic()
        result = filter_.check(text)
        duration = time.monotonic() - start

        assert result.allowed is True
        assert duration < 0.01

    def test_check_with_url(self):
        filter_ = InjectionFilter(enabled=True)
        text = "Смотри https://evil.com/inject.txt"

        result = filter_.check(text, source="https://evil.com/inject.txt")
        assert result.allowed is False  # Not in allowlist

    def test_check_with_allowed_url(self):
        filter_ = InjectionFilter(enabled=True, allowed_domains=["example.com"])
        text = "Смотри https://example.com/doc"

        result = filter_.check(text, source="https://example.com/doc")
        assert result.allowed is True


class TestGoldenSetLoadPerformance:
    """Test golden set loading performance (TC-030)."""

    def test_load_sample_dataset(self, sample_dataset_path):
        """Load sample dataset within 0.5 seconds."""
        start = time.monotonic()
        records = load_golden_set(sample_dataset_path, strict=False)
        duration = time.monotonic() - start

        assert duration < 0.5
        assert len(records) > 0
