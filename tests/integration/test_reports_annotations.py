"""Integration tests for report generation and annotation store.

Covers T-1113, T-1114, FR-007, FR-009, NFR-SEC-005.
"""

from __future__ import annotations

from pathlib import Path

from regulated_eval.human_loop.annotation_store import AnnotationStore
from regulated_eval.judges.conflicts import ConflictResolver, ResolutionType
from regulated_eval.reports.html import generate_html_report
from regulated_eval.reports.markdown import generate_markdown_report
from regulated_eval.schemas import (
    CalibrationResult,
    MetricsBlock,
    RunManifest,
)


class TestReportGenerationIntegration:
    """Integration tests for report generation (Markdown + HTML)."""

    def _create_test_manifest(self) -> RunManifest:
        """Create a test manifest."""
        return RunManifest(
            run_id="test-run-001",
            dataset_version="1.0.0",
            dataset_content_hash="sha256:abc123def456",
            model_provider="yandexgpt",
            model_name="yandexgpt-lite",
            judge_model="yandexgpt",
            judge_prompt_version="v1",
            seed=42,
            package_version="0.1.0",
            tokens_input=10000,
            tokens_output=5000,
            trace_id="test-trace-001",
        )

    def _create_test_metrics(self) -> MetricsBlock:
        """Create test metrics with categories and difficulty."""
        return MetricsBlock(
            hallucination_rate=0.15,
            citation_accuracy=0.85,
            refusal_correctness=0.90,
            factual_consistency=0.80,
            by_category={
                "УСН": {
                    "hallucination_rate": 0.10,
                    "citation_accuracy": 0.90,
                    "refusal_correctness": 0.95,
                    "factual_consistency": 0.85,
                },
                "НДС": {
                    "hallucination_rate": 0.20,
                    "citation_accuracy": 0.80,
                    "refusal_correctness": 0.85,
                    "factual_consistency": 0.75,
                },
            },
            by_difficulty={
                "easy": {
                    "hallucination_rate": 0.05,
                    "citation_accuracy": 0.95,
                    "refusal_correctness": 0.98,
                    "factual_consistency": 0.92,
                },
                "hard": {
                    "hallucination_rate": 0.25,
                    "citation_accuracy": 0.75,
                    "refusal_correctness": 0.80,
                    "factual_consistency": 0.68,
                },
            },
        )

    def _create_test_calibration(self) -> CalibrationResult:
        """Create test calibration result."""
        return CalibrationResult(
            status="PASS",
            kappa=0.72,
            ci_low=0.58,
            ci_high=0.86,
            ci_level=0.95,
            agreement=0.85,
            threshold=0.6,
            recommendations=[],
        )

    def test_generate_markdown_report(self, tmp_path: Path) -> None:
        """Test Markdown report generation."""
        manifest = self._create_test_manifest()
        metrics = self._create_test_metrics()
        calibration = self._create_test_calibration()

        report_path = generate_markdown_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            calibration=calibration,
            output_dir=tmp_path,
        )

        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")

        # Verify key content
        assert "Eval Report: test-run-001" in content
        assert "15.00%" in content
        assert "85.00%" in content
        assert "Metrics by Category" in content
        assert "Metrics by Difficulty" in content
        assert "Judge Calibration" in content
        assert "0.72" in content

    def test_generate_html_report(self, tmp_path: Path) -> None:
        """Test HTML report generation."""
        manifest = self._create_test_manifest()
        metrics = self._create_test_metrics()
        calibration = self._create_test_calibration()

        report_path = generate_html_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            calibration=calibration,
            output_dir=tmp_path,
        )

        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")

        # Verify HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "Eval Report: test-run-001" in content
        assert "Metrics by Category" in content
        assert "Judge Calibration" in content
        assert "PASS" in content

    def test_report_without_calibration(self, tmp_path: Path) -> None:
        """Test report generation without calibration data."""
        manifest = self._create_test_manifest()
        metrics = self._create_test_metrics()

        # Markdown
        md_path = generate_markdown_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            calibration=None,
            output_dir=tmp_path,
        )
        md_content = md_path.read_text(encoding="utf-8")
        assert "Eval Report: test-run-001" in md_content
        assert "Judge Calibration" not in md_content

        # HTML
        html_path = generate_html_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            calibration=None,
            output_dir=tmp_path,
        )
        html_content = html_path.read_text(encoding="utf-8")
        assert "Judge Calibration" not in html_content

    def test_report_with_cost(self, tmp_path: Path) -> None:
        """Test report with estimated cost."""
        manifest = self._create_test_manifest()
        manifest.estimated_cost_rub = 45.50
        metrics = self._create_test_metrics()

        report_path = generate_markdown_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            output_dir=tmp_path,
        )

        content = report_path.read_text(encoding="utf-8")
        assert "45.5000 RUB" in content

    def test_report_without_cost(self, tmp_path: Path) -> None:
        """Test report without estimated cost."""
        manifest = self._create_test_manifest()
        manifest.estimated_cost_rub = None
        metrics = self._create_test_metrics()

        report_path = generate_markdown_report(
            run_id="test-run-001",
            manifest=manifest,
            metrics=metrics,
            output_dir=tmp_path,
        )

        content = report_path.read_text(encoding="utf-8")
        assert "N/A" in content


class TestAnnotationStoreIntegration:
    """Integration tests for AnnotationStore with hash-chain."""

    def test_save_and_load_annotation(self, tmp_path: Path) -> None:
        """Test saving and loading annotations."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        annotation = store.create_annotation(
            record_id="test_001",
            score=5,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
        )

        assert store.save_annotation(annotation) is True
        loaded = store.load_annotation("test_001")
        assert loaded is not None
        assert loaded.record_id == "test_001"
        assert loaded.score == 5

    def test_chain_verification(self, tmp_path: Path) -> None:
        """Test hash-chain verification."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        # Create chain of annotations
        prev_hash = ""
        for i in range(3):
            annotation = store.create_annotation(
                record_id=f"test_{i:03d}",
                score=5 - i,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                prev_hash=prev_hash,
            )
            store.save_annotation(annotation)
            prev_hash = annotation.hash

        # Verify chain
        is_valid, errors = store.verify_chain()
        assert is_valid is True
        assert len(errors) == 0

    def test_chain_tamper_detection(self, tmp_path: Path) -> None:
        """Test tamper detection in hash-chain."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        # Create valid chain
        prev_hash = ""
        for i in range(3):
            annotation = store.create_annotation(
                record_id=f"test_{i:03d}",
                score=5 - i,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
                prev_hash=prev_hash,
            )
            store.save_annotation(annotation)
            prev_hash = annotation.hash

        # Tamper with second annotation
        annotations = store.load_all_annotations()
        for ann in annotations:
            if ann.record_id == "test_001":
                ann.score = 1  # Tamper
                break

        # Save tampered annotation
        store.save_annotation(annotations[0])

        # Verify should detect tampering
        is_valid, errors = store.verify_chain()
        assert is_valid is False
        assert len(errors) > 0

    def test_migrate_existing_annotations(self, tmp_path: Path) -> None:
        """Test migration of existing annotations to hash-chain format."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        existing_data = [
            {
                "record_id": "old_001",
                "score": 4,
                "hallucination": False,
                "wrong_citation": False,
                "incorrect_refusal": False,
                "annotator_id": "legacy_expert",
            },
            {
                "record_id": "old_002",
                "score": 3,
                "hallucination": True,
                "wrong_citation": False,
                "incorrect_refusal": False,
                "annotator_id": "legacy_expert",
            },
        ]

        migrated = store.migrate_existing_annotations(existing_data)
        assert len(migrated) == 2
        assert migrated[0].record_id == "old_001"
        assert migrated[0].hash != ""

        # Verify migrated chain
        is_valid, errors = store.verify_chain()
        assert is_valid is True

    def test_get_conflicts(self, tmp_path: Path) -> None:
        """Test conflict detection between judge and expert."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        # Save expert annotation
        annotation = store.create_annotation(
            record_id="test_001",
            score=5,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
        )
        store.save_annotation(annotation)

        # Find conflicts (judge score differs by >= 2)
        judge_scores = {"test_001": 2}  # Score of 2 vs expert 5 = diff 3
        conflicts = store.get_conflicts(judge_scores, threshold=2)
        assert len(conflicts) == 1
        assert conflicts[0]["difference"] == 3


class TestConflictResolverIntegration:
    """Integration tests for ConflictResolver."""

    def test_find_and_resolve_conflicts(self, tmp_path: Path) -> None:
        """Test finding and resolving conflicts."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        # Save expert annotations
        for i in range(3):
            annotation = store.create_annotation(
                record_id=f"conflict_{i:03d}",
                score=5 if i < 2 else 1,
                hallucination=False,
                wrong_citation=False,
                incorrect_refusal=False,
                annotator_id="expert_01",
            )
            store.save_annotation(annotation)

        resolver = ConflictResolver(store)

        # Judge scores: 2, 2, 1 (conflicts with first two, not third)
        judge_scores = {
            "conflict_000": 2,  # diff=3, conflict
            "conflict_001": 2,  # diff=3, conflict
            "conflict_002": 1,  # diff=0, no conflict
        }

        conflicts = resolver.find_conflicts(judge_scores)
        assert len(conflicts) == 2

        # Resolve conflicts
        results = resolver.resolve_batch(
            conflicts,
            default_resolution=ResolutionType.ACCEPT_HUMAN,
            annotator_id="expert_01",
        )
        assert len(results) == 2
        assert all(r["resolution"] == "accept_human" for r in results)

    def test_resolution_types(self, tmp_path: Path) -> None:
        """Test different resolution types."""
        store = AnnotationStore(storage_path=tmp_path / "annotations")

        annotation = store.create_annotation(
            record_id="test_001",
            score=5,
            hallucination=False,
            wrong_citation=False,
            incorrect_refusal=False,
            annotator_id="expert_01",
        )
        store.save_annotation(annotation)

        resolver = ConflictResolver(store)

        for resolution_type in ResolutionType:
            result = resolver.resolve(
                record_id="test_001",
                resolution=resolution_type,
                annotator_id="expert_01",
                rationale=f"Test {resolution_type.value}",
            )
            assert result["resolution"] == resolution_type.value
