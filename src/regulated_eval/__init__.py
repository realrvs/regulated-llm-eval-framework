"""Regulated LLM Eval Framework — evaluation for LLMs in regulated domains.

Library API (FR-014):
- run_eval: Run full evaluation pipeline
- calibrate_judge: Calibrate judge against expert annotations
- generate_report: Generate Markdown/HTML report
- ab_test: Run A/B test
- resolve_conflicts: Resolve judge-human conflicts
- replay_run: Replay previous run
- load_dataset: Load and validate dataset
- verify_annotations: Verify annotation chain
"""

__version__ = "0.1.0"

from regulated_eval.adapters import (
    BaseAdapter,
    GigaChatAdapter,
    LLMRequest,
    LLMResponse,
    OpenAICompatibleAdapter,
    YandexGPTAdapter,
    create_adapter,
)
from regulated_eval.config import Config
from regulated_eval.datasets.loader import load_golden_set
from regulated_eval.datasets.manifest import create_manifest, load_manifest_file, save_manifest_file
from regulated_eval.human_loop.annotation_store import AnnotationStore
from regulated_eval.judges import CalibrationEngine, ConflictResolver
from regulated_eval.metrics.aggregator import MetricsAggregator
from regulated_eval.observability import (
    init_otel,
    record_eval_run_duration,
    record_hallucination_rate,
    record_llm_request_duration,
    shutdown_otel,
)
from regulated_eval.pipeline import EvalOrchestrator, ReplayOrchestrator
from regulated_eval.reports import generate_html_report, generate_markdown_report
from regulated_eval.schemas import (
    Annotation,
    CalibrationResult,
    GoldenRecord,
    GoldenSetSummary,
    JudgeResult,
    MetricsBlock,
    RunManifest,
)

__all__ = [
    # Version
    "__version__",
    # Config
    "Config",
    # Adapters
    "BaseAdapter",
    "LLMRequest",
    "LLMResponse",
    "YandexGPTAdapter",
    "GigaChatAdapter",
    "OpenAICompatibleAdapter",
    "create_adapter",
    # Pipeline
    "EvalOrchestrator",
    "ReplayOrchestrator",
    # Datasets
    "load_golden_set",
    "create_manifest",
    "save_manifest_file",
    "load_manifest_file",
    # Judges
    "CalibrationEngine",
    "ConflictResolver",
    # Metrics
    "MetricsAggregator",
    # Reports
    "generate_markdown_report",
    "generate_html_report",
    # Security
    "AnnotationStore",
    # Observability
    "init_otel",
    "shutdown_otel",
    "record_eval_run_duration",
    "record_llm_request_duration",
    "record_hallucination_rate",
    # Schemas
    "GoldenRecord",
    "JudgeResult",
    "RunManifest",
    "Annotation",
    "MetricsBlock",
    "CalibrationResult",
    "GoldenSetSummary",
]
