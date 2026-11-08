"""Golden set loader with Pydantic validation.

Covers FR-001, TM-05.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from regulated_eval.exceptions import ValidationError as EvalValidationError  # noqa: PLC0414
from regulated_eval.schemas import GoldenRecord  # noqa: PLC0414


def load_golden_set(
    path: str | Path,
    strict: bool = True,
) -> list[GoldenRecord]:
    """Load and validate a golden set from JSONL/JSON file.

    Args:
        path: Path to JSONL or JSON file.
        strict: If True, use Pydantic strict mode.

    Returns:
        List of validated GoldenRecord objects.

    Raises:
        EvalValidationError: If validation fails on any record.
        FileNotFoundError: If file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden set not found: {path}")

    ext = path.suffix.lower()
    if ext not in (".jsonl", ".json"):
        raise EvalValidationError(f"Unsupported file format: {ext}. Use .jsonl or .json")

    records: list[GoldenRecord] = []
    errors: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        content = f.read().strip()

    if ext == ".json":
        # Try JSON array first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                _parse_records(data, records, errors, strict)
            elif isinstance(data, dict):
                # Single record
                _parse_records([data], records, errors, strict)
            else:
                raise EvalValidationError("JSON file must contain an array or object")
        except json.JSONDecodeError as e:
            raise EvalValidationError(f"Invalid JSON: {e}")
    else:
        # JSONL: one JSON object per line
        for line_num, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                _parse_records([data], records, errors, strict, line_num)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: invalid JSON — {e}")

    if errors:
        raise EvalValidationError(f"Validation failed for {len(errors)} record(s):\n" + "\n".join(errors))

    return records


def _parse_records(
    data_list: list[dict[str, Any]],
    records: list[GoldenRecord],
    errors: list[str],
    strict: bool,
    line_num: int | None = None,
) -> None:
    """Parse and validate a list of record dicts."""
    prefix = f"Line {line_num}" if line_num is not None else "Record"

    for item in data_list:
        record_id = item.get("id", "unknown")
        try:
            record = GoldenRecord.model_validate(item, strict=strict)
            records.append(record)
        except ValidationError as e:
            error_fields = []
            for err in e.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                error_fields.append(f"{field}: {err['msg']}")
            errors.append(f"{prefix} '{record_id}': " + "; ".join(error_fields))


def validate_expert_validated_ratio(records: list[GoldenRecord], threshold: float = 0.8) -> bool:
    """Check if expert_validated ratio meets threshold.

    Args:
        records: List of validated golden records.
        threshold: Minimum ratio of expert-validated records.

    Returns:
        True if ratio >= threshold.
    """
    if not records:
        return False

    validated = sum(1 for r in records if r.expert_validated)
    ratio = validated / len(records)
    return ratio >= threshold


def get_record_stats(records: list[GoldenRecord]) -> dict[str, Any]:
    """Get statistics about loaded records.

    Returns:
        Dict with by_category, by_difficulty, expert_validated_ratio.
    """
    by_category: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    expert_validated = 0

    for r in records:
        cat = r.category.value
        by_category[cat] = by_category.get(cat, 0) + 1

        diff = r.difficulty.value
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

        if r.expert_validated:
            expert_validated += 1

    return {
        "by_category": by_category,
        "by_difficulty": by_difficulty,
        "expert_validated_ratio": expert_validated / len(records) if records else 0.0,
    }
