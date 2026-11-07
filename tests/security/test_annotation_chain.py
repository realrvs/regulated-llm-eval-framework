"""Security tests: annotation hash-chain integrity.

Covers TC-SEC-005, TC-SEC-005b.
"""

import tempfile
from pathlib import Path

import pytest

from regulated_eval.human_loop.annotation_store import AnnotationStore
from regulated_eval.schemas import AnnotationSource


class TestHashChainIntegrity:
    """Test hash-chain for annotation tamper detection (TC-SEC-005)."""

    def test_create_valid_chain(self, tmp_path):
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        assert store.save_annotation(a1) is True
        assert a1.hash is not None
        assert len(a1.hash) == 64  # SHA-256 hex

        a2 = store.create_annotation("rec-2", 5, False, False, False, "expert-1", prev_hash=a1.hash)
        assert store.save_annotation(a2) is True

        valid, errors = store.verify_chain()
        assert valid is True
        assert errors == []

    def test_tampered_annotation_detected(self, tmp_path):
        """Tampering with annotation score breaks hash (TC-SEC-005)."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        a2 = store.create_annotation("rec-2", 5, False, False, False, "expert-1", prev_hash=a1.hash)
        store.save_annotation(a2)

        # Tamper with a2
        from regulated_eval.schemas import Annotation
        tampered = Annotation(
            record_id="rec-2",
            score=1,  # Changed from 5
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert-1",
            hash=a2.hash,  # Old hash
            prev_hash=a1.hash,
            source=AnnotationSource.HUMAN,
        )
        # Hash verification should fail
        assert tampered.verify_hash() is False

    def test_chain_break_detected(self, tmp_path):
        """Wrong prev_hash breaks the chain."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        # a2 with wrong prev_hash
        a2 = store.create_annotation("rec-2", 5, False, False, False, "expert-1", prev_hash="wrong-hash")
        store.save_annotation(a2)

        valid, errors = store.verify_chain()
        assert valid is False
        assert any("Chain broken" in e for e in errors)

    def test_migration_creates_valid_chain(self, tmp_path):
        """Migration from non-hash annotations creates valid chain."""
        store = AnnotationStore(storage_path=tmp_path)

        old_data = [
            {"record_id": "rec-1", "score": 4, "hallucination": False, "wrong_citation": False, "incorrect_refusal": False, "annotator_id": "expert-1"},
            {"record_id": "rec-2", "score": 3, "hallucination": True, "wrong_citation": False, "incorrect_refusal": False, "annotator_id": "expert-1"},
        ]

        migrated = store.migrate_existing_annotations(old_data)
        assert len(migrated) == 2
        assert all(a.hash is not None for a in migrated)

        valid, errors = store.verify_chain()
        assert valid is True
        assert errors == []

    def test_hash_includes_prev_hash(self, tmp_path):
        """Hash computation includes prev_hash in input."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        a2_same_data = store.create_annotation("rec-2", 4, False, False, False, "expert-1", prev_hash="")

        # Different prev_hash → different hash
        assert a1.hash != a2_same_data.hash

    def test_load_after_save(self, tmp_path):
        """Save and reload annotation."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        store.save_annotation(a1)

        loaded = store.load_annotation("rec-1")
        assert loaded is not None
        assert loaded.record_id == "rec-1"
        assert loaded.score == 4
        assert loaded.hash == a1.hash

    def test_load_all_annotations(self, tmp_path):
        """Load all annotations from store."""
        store = AnnotationStore(storage_path=tmp_path)

        a1 = store.create_annotation("rec-1", 4, False, False, False, "expert-1")
        a2 = store.create_annotation("rec-2", 3, True, False, False, "expert-1", prev_hash=a1.hash)
        store.save_annotation(a1)
        store.save_annotation(a2)

        all_ann = store.load_all_annotations()
        assert len(all_ann) == 2
        record_ids = {a.record_id for a in all_ann}
        assert record_ids == {"rec-1", "rec-2"}
