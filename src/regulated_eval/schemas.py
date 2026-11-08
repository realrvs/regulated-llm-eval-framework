"""Pydantic schemas for Regulated LLM Eval Framework.

Covers:
- GoldenRecord (FR-001)
- JudgeResult (FR-004)
- RunManifest (FR-012)
- Annotation (NFR-SEC-005)
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ============================================================
# Enums
# ============================================================


class Category(StrEnum):
    """Golden set categories (tax/accounting/legal)."""

    USN = "УСН"
    VAT = "НДС"
    CONTRIBUTIONS = "взносы"
    NDFL = "НДФЛ"
    OTHER = "прочее"


class Difficulty(StrEnum):
    """Question difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnnotationSource(StrEnum):
    """Source of annotation."""

    HUMAN = "human"
    JUDGE_ESCALATED = "judge_escalated"


class AckSource(StrEnum):
    """How foreign provider was acknowledged."""

    CLI_FLAGS = "cli_flags"
    ENV = "env"
    INTERACTIVE = "interactive"
    NOT_APPLICABLE = "not_applicable"


# ============================================================
# Golden Record (FR-001)
# ============================================================


class GoldenRecord(BaseModel):
    """Single record in the golden set.

    Required fields: id, question, reference_answer, citations[], category, difficulty, expert_validated.
    """

    id: str = Field(..., min_length=1, description="Unique record identifier.")
    question: str = Field(..., min_length=1, description="Question text (may contain PII).")
    reference_answer: str = Field(..., min_length=1, description="Reference/ground-truth answer.")
    citations: list[str] = Field(default_factory=list, description="Citations (e.g. 'НК РФ ст. 346.16 п. 1').")
    category: Category = Field(..., description="Tax/accounting category.")
    difficulty: Difficulty = Field(..., description="Difficulty level.")
    expert_validated: bool = Field(default=False, description="Whether the record has been validated by an expert.")

    @field_validator("id")
    @classmethod
    def id_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id must not be empty")
        return v.strip()

    @property
    def content_hash(self) -> str:
        """SHA-256 hash of canonical JSON for this record."""
        canonical = json.dumps(
            {
                "id": self.id,
                "question": self.question,
                "reference_answer": self.reference_answer,
                "citations": self.citations,
                "category": self.category.value,
                "difficulty": self.difficulty.value,
                "expert_validated": self.expert_validated,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ============================================================
# Judge Result (FR-004)
# ============================================================


class JudgeResult(BaseModel):
    """Result from LLM-as-a-judge evaluation."""

    record_id: str = Field(..., description="Golden record ID.")
    score: int = Field(..., ge=0, le=5, description="Judge score (0=error, 1–5).")
    hallucination: bool = Field(..., description="Whether the answer contains hallucinations.")
    wrong_citation: bool = Field(..., description="Whether the citation is incorrect.")
    incorrect_refusal: bool = Field(..., description="Whether the refusal was incorrect.")
    rationale: str = Field(..., min_length=1, max_length=2000, description="Judge's reasoning.")
    judge_model: str = Field(..., description="Model used for judging.")
    judge_prompt_version: str = Field(..., description="Version of the judge prompt.")
    judge_status: Literal["ok", "parse_error", "rate_limited"] = Field(
        default="ok", description="Status of the judge call."
    )
    trace_id: str = Field(default="", description="W3C trace-id for correlation.")


# ============================================================
# Run Manifest (FR-012)
# ============================================================


class RunManifest(BaseModel):
    """Reproducible run manifest with hash-chain integrity."""

    run_id: str = Field(..., description="Unique run identifier (uuid4).")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dataset_version: str = Field(..., description="Golden set version (semver).")
    dataset_content_hash: str = Field(..., description="SHA-256 hash of golden set content.")
    model_provider: str = Field(..., description="LLM provider (yandexgpt, gigachat).")
    model_name: str = Field(..., description="Model name.")
    judge_model: str = Field(..., description="Judge model.")
    judge_prompt_version: str = Field(..., description="Judge prompt version.")
    seed: int = Field(..., description="Random seed.")
    package_version: str = Field(..., description="Package version.")
    tokens_input: int = Field(..., ge=0, description="Input tokens count.")
    tokens_output: int = Field(..., ge=0, description="Output tokens count.")
    estimated_cost_rub: float | None = Field(None, description="Estimated cost in RUB.")
    trace_id: str = Field(..., description="W3C trace-id.")
    hash: str = Field(default="", description="SHA-256 hash of this manifest (set after creation).")
    prev_hash: str = Field(default="", description="SHA-256 hash of previous manifest.")
    ack_source: AckSource = Field(
        default=AckSource.NOT_APPLICABLE,
        description="How foreign provider was acknowledged (ADR-002).",
    )

    @field_validator("hash", "prev_hash")
    @classmethod
    def hash_must_be_hex(cls, v: str) -> str:
        if not v:
            return v  # Allow empty for intermediate construction
        if len(v) != 64:
            raise ValueError("hash must be 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("hash must be valid hex")
        return v

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this manifest (excluding the hash field itself)."""
        data = self.model_dump(exclude={"hash"})
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verify the manifest hash matches computed hash."""
        if not self.hash:
            return False
        return self.hash == self.compute_hash()


# ============================================================
# Annotation (NFR-SEC-005)
# ============================================================


class Annotation(BaseModel):
    """Expert annotation with hash-chain integrity."""

    record_id: str = Field(..., description="Golden record ID.")
    score: int = Field(..., ge=1, le=5, description="Expert score (1–5).")
    hallucination: bool = Field(..., description="Expert's hallucination flag.")
    wrong_citation: bool = Field(..., description="Expert's wrong citation flag.")
    incorrect_refusal: bool = Field(..., description="Expert's incorrect refusal flag.")
    annotator_id: str = Field(..., min_length=1, description="Expert identifier.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hash: str = Field(..., description="SHA-256 hash for integrity.")
    prev_hash: str = Field(..., description="SHA-256 hash of previous annotation.")
    source: AnnotationSource = Field(default=AnnotationSource.HUMAN, description="Source of annotation.")

    @field_validator("hash", "prev_hash")
    @classmethod
    def hash_must_be_hex(cls, v: str) -> str:
        if not v:
            return v  # Allow empty for intermediate construction
        if len(v) != 64:
            raise ValueError("hash must be 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("hash must be valid hex")
        return v

    def compute_hash(self) -> str:
        """Compute SHA-256 hash for integrity verification."""
        data = self.model_dump(exclude={"hash"})
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verify annotation hash matches computed hash."""
        return self.hash == self.compute_hash()


# ============================================================
# Aggregated Results
# ============================================================


class MetricsBlock(BaseModel):
    """Aggregated metrics for a run."""

    hallucination_rate: float = Field(..., ge=0, le=1, description="Overall hallucination rate.")
    citation_accuracy: float = Field(..., ge=0, le=1, description="Overall citation accuracy.")
    refusal_correctness: float = Field(..., ge=0, le=1, description="Overall refusal correctness.")
    factual_consistency: float = Field(..., ge=0, le=1, description="Overall factual consistency.")
    by_category: dict[str, dict[str, float]] = Field(default_factory=dict, description="Metrics grouped by category.")
    by_difficulty: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Metrics grouped by difficulty."
    )


class CalibrationResult(BaseModel):
    """Result of judge calibration."""

    status: Literal["PASS", "FAIL"] = Field(..., description="Calibration status.")
    kappa: float = Field(..., ge=-1, le=1, description="Cohen's kappa.")
    ci_low: float = Field(..., description="Lower bound of confidence interval.")
    ci_high: float = Field(..., description="Upper bound of confidence interval.")
    ci_level: float = Field(..., ge=0, le=1, description="Confidence level used (e.g. 0.95).")
    agreement: float = Field(..., ge=0, le=1, description="Agreement rate.")
    threshold: float = Field(..., description="Threshold used for calibration.")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations if calibration failed.")


class GoldenSetSummary(BaseModel):
    """Summary returned after loading a golden set."""

    version: str = Field(..., description="Dataset version (semver).")
    content_hash: str = Field(..., description="SHA-256 hash of dataset content.")
    total_records: int = Field(..., ge=1, le=5000, description="Total records in dataset.")
    by_category: dict[str, int] = Field(default_factory=dict, description="Record count by category.")
    by_difficulty: dict[str, int] = Field(default_factory=dict, description="Record count by difficulty.")
    expert_validated_ratio: float = Field(..., ge=0, le=1, description="Ratio of expert-validated records.")
