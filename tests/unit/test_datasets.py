"""Unit tests for golden set loader.

Covers T-1102, FR-001, TM-05.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from regulated_eval.datasets.loader import (
    get_record_stats,
    load_golden_set,
    validate_expert_validated_ratio,
)
from regulated_eval.exceptions import ValidationError


class TestLoadGoldenSet:
    """Tests for load_golden_set function."""

    def test_load_jsonl_file(self, tmp_path: Path) -> None:
        """Test loading a valid JSONL file."""
        from regulated_eval.schemas import Category, Difficulty  # noqa: PLC0414

        data = [
            {
                "id": "test_001",
                "question": "What is USN?",
                "reference_answer": "Simplified tax system",
                "category": Category.USN.value,
                "difficulty": Difficulty.EASY.value,
                "expert_validated": True,
            },
            {
                "id": "test_002",
                "question": "What is VAT?",
                "reference_answer": "Value added tax",
                "category": Category.VAT.value,
                "difficulty": Difficulty.MEDIUM.value,
                "expert_validated": False,
            },
        ]
        file_path = tmp_path / "test.jsonl"
        file_path.write_text("\n".join(json.dumps(record) for record in data), encoding="utf-8")

        records = load_golden_set(file_path, strict=False)
        assert len(records) == 2
        assert records[0].id == "test_001"
        assert records[1].category.value == "НДС"

    def test_load_json_array(self, tmp_path: Path) -> None:
        """Test loading a valid JSON array file."""
        from regulated_eval.schemas import Category, Difficulty  # noqa: PLC0414

        data = [
            {
                "id": "test_001",
                "question": "What is USN?",
                "reference_answer": "Simplified tax system",
                "category": Category.USN.value,
                "difficulty": Difficulty.EASY.value,
                "expert_validated": True,
            },
        ]
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        records = load_golden_set(file_path, strict=False)
        assert len(records) == 1

    def test_load_json_single_record(self, tmp_path: Path) -> None:
        """Test loading a single JSON object."""
        from regulated_eval.schemas import Category, Difficulty  # noqa: PLC0414

        data = {
            "id": "test_001",
            "question": "What is USN?",
            "reference_answer": "Simplified tax system",
            "category": Category.USN.value,
            "difficulty": Difficulty.EASY.value,
            "expert_validated": True,
        }
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        records = load_golden_set(file_path, strict=False)
        assert len(records) == 1

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_golden_set(tmp_path / "nonexistent.jsonl")

    def test_invalid_format_raises(self, tmp_path: Path) -> None:
        """Test that unsupported format raises ValidationError."""
        file_path = tmp_path / "test.csv"
        file_path.write_text("id,question\n1,test", encoding="utf-8")

        with pytest.raises(ValidationError, match="Unsupported file format"):
            load_golden_set(file_path)

    def test_invalid_record_raises(self, tmp_path: Path) -> None:
        """Test that invalid record raises ValidationError."""
        data = [
            {
                "id": "test_001",
                "question": "What is USN?",
                # Missing reference_answer
                "category": "УСН",
                "difficulty": "easy",
                "expert_validated": True,
            },
        ]
        file_path = tmp_path / "test.jsonl"
        file_path.write_text(json.dumps(data[0]), encoding="utf-8")

        with pytest.raises(ValidationError):
            load_golden_set(file_path)

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        """Test that empty lines in JSONL are skipped."""
        from regulated_eval.schemas import Category, Difficulty  # noqa: PLC0414

        data = [
            {
                "id": "test_001",
                "question": "What is USN?",
                "reference_answer": "Answer",
                "category": Category.USN.value,
                "difficulty": Difficulty.EASY.value,
                "expert_validated": True,
            },
        ]
        file_path = tmp_path / "test.jsonl"
        file_path.write_text(
            "\n".join([json.dumps(data[0]), "", "", json.dumps(data[0])]),
            encoding="utf-8",
        )

        records = load_golden_set(file_path, strict=False)
        assert len(records) == 2


class TestValidateExpertValidatedRatio:
    """Tests for validate_expert_validated_ratio function."""

    def test_ratio_above_threshold(self) -> None:
        """Test ratio above 0.8 threshold."""
        records = [
            pytest.importorskip("regulated_eval.schemas").GoldenRecord(
                id=f"test_{i:03d}",
                question="Test",
                reference_answer="Answer",
                category="УСН",
                difficulty="easy",
                expert_validated=True,
            )
            for i in range(10)
        ]
        assert validate_expert_validated_ratio(records, threshold=0.8) is True

    def test_ratio_below_threshold(self) -> None:
        """Test ratio below 0.8 threshold."""
        from regulated_eval.schemas import Category, Difficulty, GoldenRecord

        records = [
            GoldenRecord(
                id=f"test_{i:03d}",
                question="Test",
                reference_answer="Answer",
                category=Category.USN,
                difficulty=Difficulty.EASY,
                expert_validated=False,
            )
            for i in range(10)
        ]
        assert validate_expert_validated_ratio(records, threshold=0.8) is False

    def test_empty_records(self) -> None:
        """Test with empty records list."""
        assert validate_expert_validated_ratio([], threshold=0.8) is False


class TestGetRecordStats:
    """Tests for get_record_stats function."""

    def test_get_stats(self) -> None:
        """Test getting record statistics."""
        from regulated_eval.schemas import Category, Difficulty, GoldenRecord

        records = [
            GoldenRecord(
                id="test_001",
                question="Test",
                reference_answer="Answer",
                category=Category.USN,
                difficulty=Difficulty.EASY,
                expert_validated=True,
            ),
            GoldenRecord(
                id="test_002",
                question="Test",
                reference_answer="Answer",
                category=Category.VAT,
                difficulty=Difficulty.MEDIUM,
                expert_validated=True,
            ),
            GoldenRecord(
                id="test_003",
                question="Test",
                reference_answer="Answer",
                category=Category.USN,
                difficulty=Difficulty.EASY,
                expert_validated=False,
            ),
        ]

        stats = get_record_stats(records)
        assert stats["by_category"]["УСН"] == 2
        assert stats["by_category"]["НДС"] == 1
        assert stats["by_difficulty"]["easy"] == 2
        assert stats["expert_validated_ratio"] == 2 / 3
