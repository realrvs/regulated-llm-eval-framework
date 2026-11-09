"""Golden set versioning with semver + content hash.

Covers FR-002, TM-05.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from regulated_eval.schemas import GoldenRecord, GoldenSetSummary


def compute_dataset_hash(records: list[GoldenRecord]) -> str:
    """Compute SHA-256 hash of the entire dataset content.

    Hash is computed from sorted record IDs + their content hashes.
    This ensures any change in records (order, content, count) changes the hash.

    Returns:
        Hash string prefixed with 'sha256:'.
    """
    # Sort by record ID for deterministic ordering
    sorted_records = sorted(records, key=lambda r: r.id)
    parts = [r.content_hash for r in sorted_records]
    content = "|".join(parts)
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semver string into tuple.

    Args:
        version_str: Version string like '1.2.0'.

    Returns:
        Tuple of (major, minor, patch).

    Raises:
        ValueError: If version string is invalid.
    """
    try:
        parts = version_str.strip().split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semver: {version_str}")
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid semver '{version_str}': {e}")


def version_to_string(major: int, minor: int, patch: int) -> str:
    """Convert version tuple to string."""
    return f"{major}.{minor}.{patch}"


def next_version(version_str: str, bump: str = "patch") -> str:
    """Generate next version string.

    Args:
        version_str: Current version.
        bump: Which part to bump — 'major', 'minor', or 'patch'.

    Returns:
        Next version string.
    """
    major, minor, patch = parse_version(version_str)
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump}")
    return version_to_string(major, minor, patch)


def create_golden_set_summary(
    records: list[GoldenRecord],
    version: str,
    content_hash: str,
) -> GoldenSetSummary:
    """Create a summary of the golden set.

    Args:
        records: List of validated records.
        version: Dataset version (semver).
        content_hash: SHA-256 hash of dataset content.

    Returns:
        GoldenSetSummary with statistics.
    """
    from regulated_eval.datasets.loader import get_record_stats  # noqa: PLC0414

    stats = get_record_stats(records)
    return GoldenSetSummary(
        version=version,
        content_hash=content_hash,
        total_records=len(records),
        by_category=stats["by_category"],
        by_difficulty=stats["by_difficulty"],
        expert_validated_ratio=stats["expert_validated_ratio"],
    )


def save_manifest(
    manifest_data: dict[str, Any],
    output_dir: Path | str,
    dataset_name: str,
    version: str,
) -> Path:
    """Save manifest to disk.

    Args:
        manifest_data: Manifest data to serialize.
        output_dir: Directory to save manifest.
        dataset_name: Name of the dataset.
        version: Dataset version.

    Returns:
        Path to saved manifest file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{dataset_name}_v{version}.json"
    manifest_path = output_dir / filename

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False, default=str)

    return manifest_path


def load_manifest(
    manifest_dir: Path | str,
    dataset_name: str,
    version: str,
) -> dict[str, Any] | None:
    """Load manifest from disk.

    Args:
        manifest_dir: Directory containing manifests.
        dataset_name: Name of the dataset.
        version: Dataset version.

    Returns:
        Manifest data or None if not found.
    """
    manifest_dir = Path(manifest_dir)
    filename = f"{dataset_name}_v{version}.json"
    manifest_path = manifest_dir / filename

    if not manifest_path.exists():
        return None

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[return-value]
