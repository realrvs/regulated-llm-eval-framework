"""E2E tests for human-in-the-loop annotation store.

Covers TC-013, TC-014.
"""

from regulated_eval.human_loop.annotation_store import AnnotationStore
from regulated_eval.schemas import AnnotationSource


class TestHumanInTheLoopE2E:
    """End-to-end tests for human-in-the-loop workflow."""

    def test_full_annotation_workflow(self, tmp_path):
        """Create → save → load → verify chain (TC-013)."""
        store = AnnotationStore(storage_path=tmp_path)

        # Step 1: Create annotations
        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        assert store.save_annotation(a1) is True

        a2 = store.create_annotation("rec-2", 5, False, False, False, "expert-1", prev_hash=a1.hash)
        assert store.save_annotation(a2) is True

        a3 = store.create_annotation("rec-3", 3, True, False, False, "expert-1", prev_hash=a2.hash)
        assert store.save_annotation(a3) is True

        # Step 2: Verify chain
        valid, errors = store.verify_chain()
        assert valid is True
        assert errors == []

        # Step 3: Load and verify
        loaded_a1 = store.load_annotation("rec-1")
        assert loaded_a1 is not None
        assert loaded_a1.score == 4
        assert loaded_a1.hash == a1.hash

        all_ann = store.load_all_annotations()
        assert len(all_ann) == 3

    def test_conflict_detection(self, tmp_path):
        """Detect conflicts between judge and expert (TC-014)."""
        store = AnnotationStore(storage_path=tmp_path)

        # Create annotations
        a1 = store.create_annotation("rec-1", 5, False, False, False, "expert-1")
        a2 = store.create_annotation("rec-2", 2, True, True, False, "expert-1", prev_hash=a1.hash)
        store.save_annotation(a1)
        store.save_annotation(a2)

        # Judge scores differ from expert
        judge_scores = {
            "rec-1": 5,  # Match
            "rec-2": 4,  # Conflict (diff=2)
        }

        conflicts = store.get_conflicts(judge_scores, threshold=2)
        assert len(conflicts) == 1
        assert conflicts[0]["record_id"] == "rec-2"
        assert conflicts[0]["judge_score"] == 4
        assert conflicts[0]["expert_score"] == 2
        assert conflicts[0]["difference"] == 2

    def test_no_conflicts(self, tmp_path):
        """No conflicts when judge matches expert."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        judge_scores = {"rec-1": 4}
        conflicts = store.get_conflicts(judge_scores, threshold=2)
        assert len(conflicts) == 0

    def test_multiple_annotators(self, tmp_path):
        """Multiple annotators for same record."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        a2 = store.create_annotation("rec-1", 5, False, False, False, "expert-2", prev_hash=a1.hash)
        store.save_annotation(a2)

        rec_annotations = store.get_annotations_by_record("rec-1")
        assert len(rec_annotations) == 2
        annotator_ids = {a.annotator_id for a in rec_annotations}
        assert annotator_ids == {"expert-1", "expert-2"}

    def test_persistence_across_reloads(self, tmp_path):
        """Annotations persist across store reloads."""
        # First store
        store1 = AnnotationStore(storage_path=tmp_path)
        a1 = store1.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store1.save_annotation(a1)

        # New store instance loads from disk
        store2 = AnnotationStore(storage_path=tmp_path)
        loaded = store2.load_annotation("rec-1")

        assert loaded is not None
        assert loaded.score == 4
        assert loaded.hash == a1.hash

        valid, errors = store2.verify_chain()
        assert valid is True

    def test_tamper_detection_e2e(self, tmp_path):
        """End-to-end tamper detection."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        a2 = store.create_annotation("rec-2", 5, False, False, False, "expert-1", prev_hash=a1.hash)
        store.save_annotation(a2)

        # Verify before tamper
        valid_before, _ = store.verify_chain()
        assert valid_before is True

        # Tamper with a2's score (bypassing hash)
        from regulated_eval.schemas import Annotation

        tampered = Annotation(
            record_id="rec-2",
            score=1,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert-1",
            hash=a2.hash,
            prev_hash=a1.hash,
            source=AnnotationSource.HUMAN,
        )
        store._annotations[tampered.hash] = tampered

        # Verify after tamper
        valid_after, errors = store.verify_chain()
        assert valid_after is False
        assert any("Hash verification failed" in e for e in errors)
