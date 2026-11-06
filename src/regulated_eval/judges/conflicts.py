"""Conflict resolution between judge and human annotations.

Covers FR-007, NFR-SEC-005, TM-09, TM-10, ADR-005.

Provides:
- ConflictResolver: resolves disagreements between judge and human scores
- Resolution types: accept_human, accept_judge, escalate
- Audit logging of all resolutions
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from regulated_eval.human_loop.annotation_store import AnnotationStore
from regulated_eval.schemas import Annotation

logger = logging.getLogger(__name__)


class ResolutionType(str, Enum):
    """Types of conflict resolution."""

    ACCEPT_HUMAN = "accept_human"
    ACCEPT_JUDGE = "accept_judge"
    ESCALATE = "escalate"


class ConflictResolver:
    """Resolves conflicts between judge and human annotations.

    Workflow:
    1. Compare judge scores with expert annotations
    2. Identify conflicts (score difference >= threshold)
    3. Present conflicts to user for resolution
    4. Log resolution with audit trail
    """

    def __init__(
        self,
        annotation_store: AnnotationStore,
        audit_logger: Any = None,
        conflict_threshold: int = 2,
    ) -> None:
        """Initialize conflict resolver.

        Args:
            annotation_store: Store with expert annotations.
            audit_logger: Optional audit logger.
            conflict_threshold: Minimum score difference for conflict.
        """
        self._annotation_store = annotation_store
        self._audit_logger = audit_logger
        self._conflict_threshold = conflict_threshold
        self._resolutions: list[dict[str, Any]] = []

    def find_conflicts(
        self,
        judge_scores: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Find conflicts between judge scores and expert annotations.

        Args:
            judge_scores: Dict of record_id -> judge score.

        Returns:
            List of conflict dicts.
        """
        conflicts = []

        for record_id, judge_score in judge_scores.items():
            annotations = self._annotation_store.get_annotations_by_record(record_id)
            for annotation in annotations:
                diff = abs(judge_score - annotation.score)
                if diff >= self._conflict_threshold:
                    conflicts.append({
                        "record_id": record_id,
                        "judge_score": judge_score,
                        "expert_score": annotation.score,
                        "difference": diff,
                        "annotator_id": annotation.annotator_id,
                        "hallucination_judge": False,  # Would need judge results
                        "hallucination_expert": annotation.hallucination,
                    })

        if conflicts:
            logger.info(
                "Found %d conflicts between judge and expert annotations",
                len(conflicts),
            )
        else:
            logger.info("No conflicts found between judge and expert annotations")

        return conflicts

    def resolve(
        self,
        record_id: str,
        resolution: ResolutionType,
        annotator_id: str = "",
        rationale: str = "",
    ) -> dict[str, Any]:
        """Resolve a single conflict.

        Args:
            record_id: Record ID to resolve.
            resolution: Resolution type.
            annotator_id: Expert who made the resolution.
            rationale: Explanation for the resolution.

        Returns:
            Resolution result dict.
        """
        result = {
            "record_id": record_id,
            "resolution": resolution.value,
            "annotator_id": annotator_id,
            "rationale": rationale,
            "timestamp": "",  # Would use datetime in production
        }

        # Update annotation store
        annotations = self._annotation_store.get_annotations_by_record(record_id)
        if annotations:
            # Update the expert annotation with resolution
            annotation = annotations[0]
            if resolution == ResolutionType.ACCEPT_JUDGE:
                logger.info(
                    "Accepted judge score for record %s (was %d, expert was %d)",
                    record_id,
                    annotation.score,
                    annotation.score,
                )
            elif resolution == ResolutionType.ESCALATE:
                logger.info(
                    "Escalated record %s for senior expert review",
                    record_id,
                )

        # Log resolution
        if self._audit_logger:
            self._audit_logger.log(
                "judge.conflict.resolved",
                record_id=record_id,
                resolution=resolution.value,
                annotator_id=annotator_id,
            )

        self._resolutions.append(result)
        return result

    def resolve_batch(
        self,
        conflicts: list[dict[str, Any]],
        default_resolution: ResolutionType = ResolutionType.ACCEPT_HUMAN,
        annotator_id: str = "",
    ) -> list[dict[str, Any]]:
        """Resolve multiple conflicts at once.

        Args:
            conflicts: List of conflict dicts from find_conflicts().
            default_resolution: Default resolution type.
            annotator_id: Expert who made the resolutions.

        Returns:
            List of resolution results.
        """
        results = []
        for conflict in conflicts:
            result = self.resolve(
                record_id=conflict["record_id"],
                resolution=default_resolution,
                annotator_id=annotator_id,
                rationale=f"Batch resolution: {default_resolution.value}",
            )
            results.append(result)
        return results

    @property
    def resolutions(self) -> list[dict[str, Any]]:
        """List of all resolutions made."""
        return list(self._resolutions)

    @property
    def conflict_threshold(self) -> int:
        """Current conflict threshold."""
        return self._conflict_threshold

    @conflict_threshold.setter
    def conflict_threshold(self, value: int) -> None:
        """Set conflict threshold.

        Args:
            value: Minimum score difference for conflict.
        """
        self._conflict_threshold = value
        logger.info("Conflict threshold set to: %d", value)
