"""Annotation hash-chain store with integrity verification.

Covers NFR-SEC-005, TM-09, TM-10, ADR-005.

Provides:
- AnnotationStore: persistent storage with hash-chain integrity
- Hash chain verification for tamper detection
- Migration utility for existing annotations without hashes
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from regulated_eval.schemas import Annotation, AnnotationSource

logger = logging.getLogger(__name__)


class AnnotationStore:
    """Persistent storage for expert annotations with hash-chain integrity.

    Each annotation includes:
    - hash: SHA-256 of the annotation data
    - prev_hash: SHA-256 of the previous annotation's hash
    - This creates an immutable chain that detects tampering
    """

    def __init__(self, storage_path: str | Path = "annotations/") -> None:
        """Initialize annotation store.

        Args:
            storage_path: Directory to store annotation files.
        """
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._annotations: dict[str, Annotation] = {}
        self._chain: list[str] = []  # Ordered record_ids

    def save_annotation(self, annotation: Annotation) -> bool:
        """Save an annotation with hash verification.

        Args:
            annotation: Annotation to save.

        Returns:
            True if saved successfully, False if hash verification failed.
        """
        # Verify hash before saving
        if not annotation.verify_hash():
            logger.error(
                "Annotation hash verification failed for record %s",
                annotation.record_id,
            )
            return False

        # Get previous hash from chain
        prev_hash = ""
        if self._chain:
            last_record_id = self._chain[-1]
            if last_record_id in self._annotations:
                prev_hash = self._annotations[last_record_id].hash

        # Update prev_hash if needed
        if prev_hash and annotation.prev_hash != prev_hash:
            logger.warning(
                "Chain break detected for record %s, updating prev_hash",
                annotation.record_id,
            )

        # Store annotation
        self._annotations[annotation.record_id] = annotation
        if annotation.record_id not in self._chain:
            self._chain.append(annotation.record_id)

        # Save to disk
        self._save_to_disk()
        logger.info(
            "Annotation saved for record %s (hash: %s...)",
            annotation.record_id,
            annotation.hash[:16],
        )
        return True

    def load_annotation(self, record_id: str) -> Annotation | None:
        """Load an annotation by record ID.

        Args:
            record_id: Record identifier.

        Returns:
            Annotation if found, None otherwise.
        """
        if record_id in self._annotations:
            return self._annotations[record_id]

        # Try loading from disk
        self._load_from_disk()
        return self._annotations.get(record_id)

    def load_all_annotations(self) -> list[Annotation]:
        """Load all annotations from storage.

        Returns:
            List of all annotations.
        """
        self._load_from_disk()
        return list(self._annotations.values())

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Verify the entire hash chain for integrity.

        Returns:
            Tuple of (is_valid, list_of_errors).
        """
        errors: list[str] = []

        # Load from disk if not already loaded
        if not self._annotations:
            self._load_from_disk()

        for i, record_id in enumerate(self._chain):
            annotation = self._annotations.get(record_id)
            if annotation is None:
                errors.append(f"Missing annotation for record {record_id}")
                continue

            # Verify individual hash
            if not annotation.verify_hash():
                errors.append(
                    f"Hash verification failed for record {record_id}"
                )
                continue

            # Verify chain link
            if i > 0:
                prev_id = self._chain[i - 1]
                prev_annotation = self._annotations.get(prev_id)
                if prev_annotation is None:
                    errors.append(
                        f"Chain broken: {record_id} references missing {prev_id}"
                    )
                    continue

                expected_prev_hash = prev_annotation.hash
                if annotation.prev_hash != expected_prev_hash:
                    errors.append(
                        f"Chain broken: {record_id} prev_hash doesn't match "
                        f"{prev_id} hash"
                    )

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("Annotation chain verification passed (%d annotations)", len(self._chain))
        else:
            logger.warning(
                "Annotation chain verification failed: %d errors", len(errors)
            )

        return is_valid, errors

    def create_annotation(
        self,
        record_id: str,
        score: int,
        hallucination: bool,
        wrong_citation: bool,
        incorrect_refusal: bool,
        annotator_id: str,
        prev_hash: str = "",
    ) -> Annotation:
        """Create a new annotation with computed hash.

        Args:
            record_id: Golden record ID.
            score: Expert score (1-5).
            hallucination: Hallucination flag.
            wrong_citation: Wrong citation flag.
            incorrect_refusal: Incorrect refusal flag.
            annotator_id: Expert identifier.
            prev_hash: Previous hash in the chain.

        Returns:
            Created Annotation with computed hash.
        """
        annotation = Annotation(
            record_id=record_id,
            score=score,
            hallucination=hallucination,
            wrong_citation=wrong_citation,
            incorrect_refusal=incorrect_refusal,
            annotator_id=annotator_id,
            hash="",  # Will be computed
            prev_hash=prev_hash,
            source=AnnotationSource.HUMAN,
        )
        # Compute hash (includes prev_hash in computation)
        annotation.hash = annotation.compute_hash()
        return annotation

    def migrate_existing_annotations(
        self,
        annotations_data: list[dict[str, Any]],
        annotator_id: str = "migration",
    ) -> list[Annotation]:
        """Migrate existing annotations without hashes to hash-chain format.

        Args:
            annotations_data: List of annotation dicts (without hash/prev_hash).
            annotator_id: Annotator ID for migrated annotations.

        Returns:
            List of migrated Annotation objects with computed hashes.
        """
        migrated: list[Annotation] = []
        prev_hash = ""

        for data in annotations_data:
            annotation = Annotation(
                record_id=data["record_id"],
                score=data["score"],
                hallucination=data.get("hallucination", False),
                wrong_citation=data.get("wrong_citation", False),
                incorrect_refusal=data.get("incorrect_refusal", False),
                annotator_id=data.get("annotator_id", annotator_id),
                prev_hash=prev_hash,
                hash="",  # Will be computed
            )
            annotation.hash = annotation.compute_hash()
            migrated.append(annotation)
            prev_hash = annotation.hash

        # Save all migrated annotations
        for annotation in migrated:
            self.save_annotation(annotation)

        logger.info(
            "Migrated %d annotations to hash-chain format", len(migrated)
        )
        return migrated

    def get_annotations_by_record(self, record_id: str) -> list[Annotation]:
        """Get all annotations for a specific record.

        Args:
            record_id: Record identifier.

        Returns:
            List of annotations for the record.
        """
        return [
            a for a in self._annotations.values()
            if a.record_id == record_id
        ]

    def get_conflicts(self, judge_scores: dict[str, int], threshold: int = 2) -> list[dict[str, Any]]:
        """Find conflicts between judge scores and expert annotations.

        Args:
            judge_scores: Dict of record_id -> judge score.
            threshold: Minimum score difference to be considered a conflict.

        Returns:
            List of conflict dicts.
        """
        conflicts = []
        for record_id, judge_score in judge_scores.items():
            annotations = self.get_annotations_by_record(record_id)
            for annotation in annotations:
                diff = abs(judge_score - annotation.score)
                if diff >= threshold:
                    conflicts.append({
                        "record_id": record_id,
                        "judge_score": judge_score,
                        "expert_score": annotation.score,
                        "difference": diff,
                        "annotator_id": annotation.annotator_id,
                    })
        return conflicts

    def _save_to_disk(self) -> None:
        """Save all annotations to disk as JSONL."""
        if not self._annotations:
            return

        file_path = self._storage_path / "annotations.jsonl"
        with file_path.open("w", encoding="utf-8") as f:
            for record_id in self._chain:
                annotation = self._annotations.get(record_id)
                if annotation:
                    f.write(
                        json.dumps(
                            annotation.model_dump(default=str),
                            ensure_ascii=False,
                            default=str,
                        )
                        + "\n"
                    )

    def _load_from_disk(self) -> None:
        """Load all annotations from disk."""
        file_path = self._storage_path / "annotations.jsonl"
        if not file_path.exists():
            return

        self._annotations.clear()
        self._chain.clear()

        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    annotation = Annotation.model_validate(data)
                    self._annotations[annotation.record_id] = annotation
                    if annotation.record_id not in self._chain:
                        self._chain.append(annotation.record_id)
                except Exception as e:
                    logger.warning("Failed to load annotation: %s", e)
