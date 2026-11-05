"""Run manifest with hash-chain integrity.

Covers FR-012, TM-10, ADR-005.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from regulated_eval.schemas import RunManifest


def create_manifest(
    run_id: str,
    dataset_version: str,
    dataset_content_hash: str,
    model_provider: str,
    model_name: str,
    judge_model: str,
    judge_prompt_version: str,
    seed: int,
    package_version: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    estimated_cost_rub: float | None = None,
    trace_id: str = "",
    prev_hash: str = "0" * 64,
    ack_source: str = "not_applicable",
) -> RunManifest:
    """Create a new run manifest with computed hash.

    Args:
        run_id: Unique run identifier.
        dataset_version: Golden set version.
        dataset_content_hash: SHA-256 of dataset content.
        model_provider: LLM provider name.
        model_name: Model name.
        judge_model: Judge model name.
        judge_prompt_version: Judge prompt version.
        seed: Random seed.
        package_version: Package version.
        tokens_input: Input tokens count.
        tokens_output: Output tokens count.
        estimated_cost_rub: Estimated cost in RUB.
        trace_id: W3C trace-id.
        prev_hash: Hash of previous manifest (genesis = 64 zeros).
        ack_source: How foreign provider was acknowledged.

    Returns:
        RunManifest with computed hash.
    """
    # Create manifest with empty hash first
    manifest = RunManifest(
        run_id=run_id,
        dataset_version=dataset_version,
        dataset_content_hash=dataset_content_hash,
        model_provider=model_provider,
        model_name=model_name,
        judge_model=judge_model,
        judge_prompt_version=judge_prompt_version,
        seed=seed,
        package_version=package_version,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        estimated_cost_rub=estimated_cost_rub,
        trace_id=trace_id,
        prev_hash=prev_hash,
        ack_source=ack_source,
    )
    # Compute and set hash (hash field allows empty string for intermediate construction)
    manifest.hash = manifest.compute_hash()
    return manifest


def save_manifest_file(
    manifest: RunManifest,
    output_dir: Path | str,
) -> Path:
    """Save manifest to JSON file.

    Args:
        manifest: RunManifest to save.
        output_dir: Output directory.

    Returns:
        Path to saved file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"run_{manifest.run_id}.json"
    manifest_path = output_dir / filename

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(default=str), f, indent=2, ensure_ascii=False, default=str)

    return manifest_path


def load_manifest_file(
    manifest_path: Path | str,
) -> RunManifest:
    """Load manifest from JSON file.

    Args:
        manifest_path: Path to manifest file.

    Returns:
        RunManifest object.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return RunManifest.model_validate(data)


def verify_manifest_chain(
    manifest: RunManifest,
    prev_manifest: RunManifest | None = None,
) -> bool:
    """Verify manifest hash chain integrity.

    Args:
        manifest: Manifest to verify.
        prev_manifest: Previous manifest (for chain verification).

    Returns:
        True if hash chain is valid.
    """
    # Verify current manifest hash
    if not manifest.verify_hash():
        return False

    # Verify chain if previous manifest exists
    if prev_manifest is not None:
        if manifest.prev_hash != prev_manifest.hash:
            return False

    return True


def get_latest_manifest(manifest_dir: Path | str) -> RunManifest | None:
    """Get the latest manifest from a directory.

    Args:
        manifest_dir: Directory containing manifests.

    Returns:
        Latest manifest by filename timestamp, or None.
    """
    manifest_dir = Path(manifest_dir)
    if not manifest_dir.exists():
        return None

    manifests = sorted(manifest_dir.glob("run_*.json"))
    if not manifests:
        return None

    # Load the last one (sorted alphabetically by run_id)
    return load_manifest_file(manifests[-1])
