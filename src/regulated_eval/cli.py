"""CLI entry point for Regulated LLM Eval Framework.

Covers FR-014.

Commands:
- dataset load: Load and validate golden set
- dataset list: List available datasets
- run: Run evaluation
- calibrate: Calibrate judge
- report: Generate report
- ab: A/B test
- conflicts resolve: Resolve judge-human conflicts
- run replay: Replay previous run
- annotations verify: Verify annotation chain
- serve: Start HTTP server (optional)
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(
    name="regulated-eval",
    help="Regulated LLM Eval Framework — evaluation for LLMs in regulated domains.",
    add_completion=False,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=False,
)


def _version_callback(value: bool) -> None:
    """Callback for --version flag."""
    if value:
        from regulated_eval import __version__  # noqa: PLC0414

        typer.echo(f"regulated-eval {__version__}")
        raise typer.Exit()


# ============================================================
# Global flags
# ============================================================


@app.callback()
def cli_main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML config file.",
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        help="Logging level: debug, info, warning, error.",
    ),
    traceparent: str | None = typer.Option(
        None,
        "--traceparent",
        help="W3C traceparent for distributed tracing.",
    ),
    x_request_id: str | None = typer.Option(
        None,
        "--x-request-id",
        help="External run.id (uuid4); if not set — generated.",
    ),
) -> None:
    """Global CLI flags."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["log_level"] = log_level
    ctx.obj["traceparent"] = traceparent
    ctx.obj["x_request_id"] = x_request_id


# ============================================================
# Dataset commands (FR-001, FR-002)
# ============================================================


@app.command()
def dataset_load(
    path: str = typer.Option(..., "--path", "-p", help="Path to JSONL/JSON golden set file."),
    version: str | None = typer.Option(None, "--version", "-V", help="Explicit version (else from manifest or 0.1.0)."),
    strict: bool = typer.Option(False, "--strict", help="Pydantic strict mode."),
) -> None:
    """Load and validate a golden set (FR-001)."""
    from regulated_eval.datasets.loader import load_golden_set  # noqa: PLC0414
    from regulated_eval.datasets.versioning import (  # noqa: PLC0414
        compute_dataset_hash,
        create_golden_set_summary,
    )

    try:
        records = load_golden_set(path, strict=strict)
        dataset_hash = compute_dataset_hash(records)

        if version is None:
            version = "0.1.0"

        summary = create_golden_set_summary(records, version, dataset_hash)

        typer.echo(f"Dataset loaded: {summary.total_records} records")
        typer.echo(f"Version: {summary.version}")
        typer.echo(f"Content hash: {summary.content_hash}")
        typer.echo(f"Expert validated ratio: {summary.expert_validated_ratio:.2%}")
        typer.echo("")
        typer.echo("By category:")
        for cat, count in sorted(summary.by_category.items()):
            typer.echo(f"  {cat}: {count}")
        typer.echo("")
        typer.echo("By difficulty:")
        for diff, count in sorted(summary.by_difficulty.items()):
            typer.echo(f"  {diff}: {count}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def dataset_list(
    dataset_dir: str = typer.Option("datasets/", "--dir", "-d", help="Dataset directory."),
) -> None:
    """List available datasets (FR-002)."""
    dataset_path = Path(dataset_dir)
    if not dataset_path.exists():
        typer.echo(f"Dataset directory not found: {dataset_dir}")
        raise typer.Exit(code=3)

    jsonl_files = list(dataset_path.glob("**/*.jsonl"))
    json_files = list(dataset_path.glob("**/*.json"))
    all_files = jsonl_files + json_files

    if not all_files:
        typer.echo("No datasets found.")
        return

    typer.echo("Available datasets:")
    for f in sorted(all_files):
        typer.echo(f"  {f.relative_to(dataset_path)}")


# ============================================================
# Run command (FR-003, FR-004, FR-006)
# ============================================================


@app.command()
def run(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Dataset path (file or directory)."),
    model: str = typer.Option(..., "--model", "-m", help="Model: yandexgpt, gigachat, openai_compat."),
    judge_model: str | None = typer.Option(None, "--judge-model", "-j", help="Judge model (default: same as --model)."),
    parallelism: int = typer.Option(8, "--parallelism", "-P", help="Parallelism (1–32)."),
    seed: int = typer.Option(42, "--seed", help="Random seed for reproducibility."),
    allow_foreign_provider: bool = typer.Option(
        False,
        "--allow-foreign-provider",
        help="Required for openai_compat (152-FZ opt-in).",
    ),
    i_understand_152fz: bool = typer.Option(
        False,
        "--i-understand-152fz",
        help="Acknowledge 152-FZ implications (required with --allow-foreign-provider).",
    ),
    report_format: str = typer.Option(
        "md",
        "--report",
        "-r",
        help="Report format: md, html, both.",
    ),
) -> None:
    """Run evaluation on golden set through model + judge (FR-003, FR-004, FR-006)."""
    import asyncio
    from pathlib import Path

    from regulated_eval.adapters import create_adapter  # noqa: PLC0414
    from regulated_eval.config import Config  # noqa: PLC0414
    from regulated_eval.exceptions import ForeignProviderNotAllowed  # noqa: PLC0414
    from regulated_eval.observability import init_otel, shutdown_otel  # noqa: PLC0414
    from regulated_eval.pipeline import EvalOrchestrator  # noqa: PLC0414
    from regulated_eval.reports import generate_html_report, generate_markdown_report  # noqa: PLC0414

    # Initialize OTel
    init_otel()

    # Create config
    config = Config(
        allow_foreign_provider=allow_foreign_provider,
        acknowledge_152fz=i_understand_152fz,
    )

    # Validate foreign provider
    adapter = create_adapter(model, config=config)
    if adapter.is_foreign:
        try:
            config.validate_foreign_provider()
        except ForeignProviderNotAllowed as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=4)

    # Create orchestrator
    orchestrator = EvalOrchestrator(adapter, config=config)

    # Run evaluation
    try:
        result = asyncio.get_event_loop().run_until_complete(
            orchestrator.run(
                dataset_path=dataset,
                seed=seed,
            )
        )

        run_id = result["run_id"]
        manifest = result["manifest"]
        metrics = result["metrics"]

        typer.echo(f"Run completed: {run_id}")
        typer.echo(f"Records processed: {len(result['judge_results'])}")
        typer.echo(f"Hallucination rate: {metrics.hallucination_rate:.2%}")
        typer.echo(f"Citation accuracy: {metrics.citation_accuracy:.2%}")
        typer.echo(f"Tokens: {manifest.tokens_input:,} in / {manifest.tokens_output:,} out")

        # Save run result as JSON (for report, replay, ab)
        output_dir = Path("reports/")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"run_{run_id}.json"
        output_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "manifest": manifest.model_dump(default=str),
                    "metrics": metrics.model_dump(),
                    "judge_results": [jr.model_dump() for jr in result["judge_results"]],
                    "total_tokens_input": result["total_tokens_input"],
                    "total_tokens_output": result["total_tokens_output"],
                    "estimated_cost_rub": result["estimated_cost_rub"],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        typer.echo(f"Run result saved: {output_path}")

        # Generate report
        if report_format in ("md", "both"):
            report_path = generate_markdown_report(run_id, manifest, metrics)
            typer.echo(f"Markdown report: {report_path}")

        if report_format in ("html", "both"):
            report_path = generate_html_report(run_id, manifest, metrics)
            typer.echo(f"HTML report: {report_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        shutdown_otel()


# ============================================================
# Calibrate command (FR-005)
# ============================================================


@app.command()
def calibrate(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Calibration dataset path."),
    annotations: str = typer.Option(
        "annotations/",
        "--annotations",
        "-a",
        help="Path to annotations directory or JSON file.",
    ),
    judge_model: str = typer.Option(..., "--judge-model", "-j", help="Judge model."),
    threshold: float = typer.Option(0.6, "--threshold", "-t", help="Cohen's kappa threshold."),
    ci_level: float = typer.Option(0.95, "--ci-level", help="Confidence interval level."),
    parallelism: int = typer.Option(8, "--parallelism", "-P", help="Parallelism (1–32)."),
    allow_foreign_provider: bool = typer.Option(
        False, "--allow-foreign-provider", help="Required for openai_compat (152-FZ opt-in)."
    ),
    i_understand_152fz: bool = typer.Option(False, "--i-understand-152fz", help="Acknowledge 152-FZ implications."),
) -> None:
    """Calibrate judge against expert annotations (FR-005)."""

    from regulated_eval.adapters import create_adapter  # noqa: PLC0414
    from regulated_eval.config import Config  # noqa: PLC0414
    from regulated_eval.exceptions import CalibrationFailed, ForeignProviderNotAllowed  # noqa: PLC0414
    from regulated_eval.human_loop.annotation_store import AnnotationStore  # noqa: PLC0414
    from regulated_eval.observability import init_otel, shutdown_otel  # noqa: PLC0414
    from regulated_eval.pipeline import EvalOrchestrator  # noqa: PLC0414

    init_otel()

    try:
        config = Config(
            allow_foreign_provider=allow_foreign_provider,
            acknowledge_152fz=i_understand_152fz,
        )
        adapter = create_adapter(judge_model, config=config)
        if adapter.is_foreign:
            try:
                config.validate_foreign_provider()
            except ForeignProviderNotAllowed as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(code=4)

        orchestrator = EvalOrchestrator(adapter, config=config)

        # Load annotations
        store = AnnotationStore(annotations)
        annotations_list = store.load_all_annotations()

        result = orchestrator.calibrate_sync(
            dataset_path=dataset,
            annotations=annotations_list,
            threshold=threshold,
            ci_level=ci_level,
        )

        typer.echo(f"Calibration status: {result.status}")
        typer.echo(
            f"Cohen's kappa: {result.kappa:.2f} [{int(result.ci_level * 100)}% CI {result.ci_low:.2f}-{result.ci_high:.2f}]"
        )
        typer.echo(f"Agreement rate: {result.agreement:.2%}")
        typer.echo(f"Threshold: {result.threshold}")

        if result.recommendations:
            typer.echo("")
            typer.echo("Recommendations:")
            for rec in result.recommendations:
                typer.echo(f"  - {rec}")

        if result.status == "FAIL":
            raise typer.Exit(code=5)

    except CalibrationFailed as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=5)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        shutdown_otel()


# ============================================================
# Report command (FR-009)
# ============================================================


@app.command()
def report(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID for report generation."),
    format: str = typer.Option("md", "--format", "-f", help="Report format: md, html, both."),
    compare: str | None = typer.Option(None, "--compare", "-c", help="Run ID of previous run for delta comparison."),
    output_dir: str = typer.Option("reports/", "--output-dir", "-o", help="Output directory."),
) -> None:
    """Generate Markdown/HTML report (FR-009)."""
    from pathlib import Path

    from regulated_eval.reports import generate_html_report, generate_markdown_report  # noqa: PLC0414
    from regulated_eval.schemas import MetricsBlock, RunManifest  # noqa: PLC0414

    output_path = Path(output_dir) / f"run_{run_id}.json"

    if not output_path.exists():
        typer.echo(f"Run result not found: {output_path}", err=True)
        typer.echo("Hint: run 'regulated-eval run' first to generate the result.", err=True)
        raise typer.Exit(code=3)

    data = json.loads(output_path.read_text(encoding="utf-8"))

    manifest = RunManifest(**data["manifest"])
    metrics = MetricsBlock(**data["metrics"])

    if format in ("md", "both"):
        report_path = generate_markdown_report(run_id, manifest, metrics, output_dir=output_dir)
        typer.echo(f"Markdown report: {report_path}")

    if format in ("html", "both"):
        report_path = generate_html_report(run_id, manifest, metrics, output_dir=output_dir)
        typer.echo(f"HTML report: {report_path}")

    if compare:
        compare_path = Path(output_dir) / f"run_{compare}.json"
        if compare_path.exists():
            compare_data = json.loads(compare_path.read_text(encoding="utf-8"))
            compare_metrics = MetricsBlock(**compare_data["metrics"])
            delta_hallucination = metrics.hallucination_rate - compare_metrics.hallucination_rate
            delta_citation = metrics.citation_accuracy - compare_metrics.citation_accuracy
            typer.echo("")
            typer.echo(f"Delta vs run {compare}:")
            typer.echo(f"  Hallucination rate: {delta_hallucination:+.2%}")
            typer.echo(f"  Citation accuracy: {delta_citation:+.2%}")
        else:
            typer.echo(f"Compare run not found: {compare_path}", err=True)


# ============================================================
# A/B command (FR-008)
# ============================================================


@app.command()
def ab(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Dataset path."),
    model_a: str = typer.Option(..., "--model-a", "-m", help="Model A (e.g. yandexgpt)."),
    model_b: str = typer.Option(..., "--model-b", help="Model B (e.g. gigachat)."),
    judge_model: str = typer.Option(..., "--judge-model", "-j", help="Judge model."),
    prompt_a: str = typer.Option("default", "--prompt-a", help="Prompt A identifier."),
    prompt_b: str = typer.Option("default", "--prompt-b", help="Prompt B identifier."),
    allow_foreign_provider: bool = typer.Option(
        False, "--allow-foreign-provider", help="Required for openai_compat (152-FZ opt-in)."
    ),
    i_understand_152fz: bool = typer.Option(False, "--i-understand-152fz", help="Acknowledge 152-FZ implications."),
    output_dir: str = typer.Option("reports/", "--output-dir", "-o", help="Output directory."),
) -> None:
    """Run A/B test between two models or prompts (FR-008)."""
    import asyncio
    from pathlib import Path

    from regulated_eval.ab import ABTest  # noqa: PLC0414
    from regulated_eval.adapters import create_adapter  # noqa: PLC0414
    from regulated_eval.adapters.base import LLMRequest  # noqa: PLC0414
    from regulated_eval.config import Config  # noqa: PLC0414
    from regulated_eval.datasets.loader import load_golden_set  # noqa: PLC0414
    from regulated_eval.judges.judge import Judge  # noqa: PLC0414
    from regulated_eval.observability import init_otel, shutdown_otel  # noqa: PLC0414

    init_otel()

    try:
        config = Config(
            allow_foreign_provider=allow_foreign_provider,
            acknowledge_152fz=i_understand_152fz,
        )

        # Load dataset
        records = load_golden_set(dataset, strict=False)
        typer.echo(f"Loaded {len(records)} records from {dataset}")

        # Run model A
        typer.echo(f"\nRunning Model A: {model_a}...")
        adapter_a = create_adapter(model_a, config=config)
        judge_a = Judge(adapter=adapter_a, config=config, prompt_version="v1")
        scores_a: list[float] = []

        for record in records:
            request = LLMRequest(prompt=record.question, model=adapter_a.model_name(), temperature=0.0, max_tokens=1024)
            response = asyncio.run(adapter_a.generate(request))
            if response and response.text:
                jr = judge_a.evaluate(record, response.text, trace_id="ab-test")
                scores_a.append(float(jr.score))

        typer.echo(
            f"  Model A: {len(scores_a)} scores, mean={sum(scores_a) / len(scores_a):.2f}"
            if scores_a
            else "  Model A: no scores"
        )

        # Run model B
        typer.echo(f"\nRunning Model B: {model_b}...")
        adapter_b = create_adapter(model_b, config=config)
        judge_b = Judge(adapter=adapter_b, config=config, prompt_version="v1")
        scores_b: list[float] = []

        for record in records:
            request = LLMRequest(prompt=record.question, model=adapter_b.model_name(), temperature=0.0, max_tokens=1024)
            response = asyncio.run(adapter_b.generate(request))
            if response and response.text:
                jr = judge_b.evaluate(record, response.text, trace_id="ab-test")
                scores_b.append(float(jr.score))

        typer.echo(
            f"  Model B: {len(scores_b)} scores, mean={sum(scores_b) / len(scores_b):.2f}"
            if scores_b
            else "  Model B: no scores"
        )

        # Run A/B test
        ab_test = ABTest()
        result = ab_test.run(
            scores_a=scores_a,
            scores_b=scores_b,
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            model_a=model_a,
            model_b=model_b,
            higher_is_better=True,
        )

        typer.echo("")
        typer.echo("=== A/B Test Results ===")
        typer.echo(f"Model A mean score: {result.metric_a:.2f} (n={result.n_a})")
        typer.echo(f"Model B mean score: {result.metric_b:.2f} (n={result.n_b})")
        typer.echo(f"Delta (B-A): {result.delta:+.2f}")
        typer.echo(f"95% CI: [{result.ci_low:.2f}, {result.ci_high:.2f}]")
        typer.echo(f"P-value: {result.p_value:.4f}")
        typer.echo(f"Cohen's d: {result.cohens_d:+.2f}")
        typer.echo(f"Significant: {result.significant}")
        typer.echo(f"Winner: {result.winner}")
        typer.echo("")
        typer.echo(result.interpretation)

        # Save result
        output_path = Path(output_dir) / f"ab_{model_a}_vs_{model_b}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "model_a": model_a,
                    "model_b": model_b,
                    "metric_a": result.metric_a,
                    "metric_b": result.metric_b,
                    "delta": result.delta,
                    "p_value": result.p_value,
                    "ci_low": result.ci_low,
                    "ci_high": result.ci_high,
                    "cohens_d": result.cohens_d,
                    "significant": result.significant,
                    "winner": result.winner,
                    "interpretation": result.interpretation,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        typer.echo(f"\nResult saved: {output_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        shutdown_otel()


# ============================================================
# Conflicts resolve (FR-007)
# ============================================================


@app.command()
def conflicts_resolve(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID to resolve conflicts for."),
    annotations: str = typer.Option("annotations/", "--annotations", "-a", help="Annotations directory."),
    threshold: int = typer.Option(2, "--threshold", "-t", help="Score difference threshold for conflict."),
    default_resolution: str = typer.Option(
        "accept_human",
        "--default",
        help="Default resolution: accept_human, accept_judge, escalate.",
    ),
    annotator_id: str = typer.Option("", "--annotator", help="Expert who resolves conflicts."),
) -> None:
    """Resolve judge vs expert conflicts (FR-007)."""
    from pathlib import Path

    from regulated_eval.human_loop.annotation_store import AnnotationStore  # noqa: PLC0414
    from regulated_eval.judges.conflicts import ConflictResolver, ResolutionType  # noqa: PLC0414

    # Load run result
    run_path = Path("reports/") / f"run_{run_id}.json"
    if not run_path.exists():
        typer.echo(f"Run result not found: {run_path}", err=True)
        raise typer.Exit(code=3)

    data = json.loads(run_path.read_text(encoding="utf-8"))
    judge_results = data.get("judge_results", [])

    # Build judge scores map
    judge_scores = {jr["record_id"]: jr["score"] for jr in judge_results if jr.get("judge_status") == "ok"}

    # Load annotations
    store = AnnotationStore(annotations)
    store.load_all_annotations()

    # Find conflicts
    resolver = ConflictResolver(
        annotation_store=store,
        conflict_threshold=threshold,
    )
    conflicts = resolver.find_conflicts(judge_scores)

    if not conflicts:
        typer.echo("No conflicts found.")
        return

    typer.echo(f"Found {len(conflicts)} conflicts:")
    for i, conflict in enumerate(conflicts, 1):
        typer.echo(
            f"  {i}. {conflict['record_id']}: "
            f"judge={conflict['judge_score']}, "
            f"expert={conflict['expert_score']}, "
            f"diff={conflict['difference']}"
        )

    # Resolve conflicts
    resolution_map = {
        "accept_human": ResolutionType.ACCEPT_HUMAN,
        "accept_judge": ResolutionType.ACCEPT_JUDGE,
        "escalate": ResolutionType.ESCALATE,
    }
    resolution_type = resolution_map.get(default_resolution, ResolutionType.ACCEPT_HUMAN)

    results = resolver.resolve_batch(
        conflicts=conflicts,
        default_resolution=resolution_type,
        annotator_id=annotator_id,
    )

    typer.echo(f"\nResolved {len(results)} conflicts with: {default_resolution}")
    for result in results:
        typer.echo(f"  {result['record_id']}: {result['resolution']}")


# ============================================================
# Run replay (FR-012)
# ============================================================


@app.command(name="replay")
def run_replay(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID to replay."),
    dataset: str = typer.Option(..., "--dataset", "-d", help="Dataset path (same as original)."),
    tolerance: float = typer.Option(0.01, "--tolerance", "-t", help="Max metric difference (default 1%%)."),
    model: str = typer.Option(..., "--model", "-m", help="Model (same as original)."),
    allow_foreign_provider: bool = typer.Option(
        False, "--allow-foreign-provider", help="Required for openai_compat (152-FZ opt-in)."
    ),
    i_understand_152fz: bool = typer.Option(False, "--i-understand-152fz", help="Acknowledge 152-FZ implications."),
) -> None:
    """Replay a previous run for reproducibility (FR-012)."""
    from pathlib import Path

    from regulated_eval.adapters import create_adapter  # noqa: PLC0414
    from regulated_eval.config import Config  # noqa: PLC0414
    from regulated_eval.datasets.manifest import load_manifest_file  # noqa: PLC0414
    from regulated_eval.observability import init_otel, shutdown_otel  # noqa: PLC0414
    from regulated_eval.pipeline import EvalOrchestrator, ReplayOrchestrator  # noqa: PLC0414

    init_otel()

    try:
        config = Config(
            allow_foreign_provider=allow_foreign_provider,
            acknowledge_152fz=i_understand_152fz,
        )
        adapter = create_adapter(model, config=config)
        if adapter.is_foreign:
            config.validate_foreign_provider()

        orchestrator = EvalOrchestrator(adapter, config=config)
        replay = ReplayOrchestrator(orchestrator)

        # Load manifest
        manifest_path = Path("reports/") / f"run_{run_id}.json"
        manifest = load_manifest_file(manifest_path)

        # Run replay
        result = replay.replay(
            manifest=manifest,
            dataset_path=dataset,
            tolerance=tolerance,
        )

        typer.echo(f"Replay of run {result['run_id']}:")
        typer.echo(f"  Reproducible: {result['reproducible']}")
        typer.echo("")
        typer.echo("Differences:")
        for key, diff in result["differences"].items():
            typer.echo(f"  {key}: {diff:+.4f} (tolerance: {tolerance:.2f})")

        if result["reproducible"]:
            typer.echo("")
            typer.echo("✅ Metrics are within tolerance — run is reproducible.")
        else:
            typer.echo("")
            typer.echo("❌ Metrics exceed tolerance — run may not be reproducible.")
            raise typer.Exit(code=7)

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    finally:
        shutdown_otel()


# ============================================================
# Annotations verify (NFR-SEC-005)
# ============================================================


@app.command()
def annotations_verify(
    path: str = typer.Option("annotations/", "--path", "-p", help="Annotations directory."),
) -> None:
    """Verify annotation hash-chain integrity (NFR-SEC-005)."""
    from regulated_eval.human_loop.annotation_store import AnnotationStore  # noqa: PLC0414

    store = AnnotationStore(path)
    is_valid, errors = store.verify_chain()

    if is_valid:
        typer.echo(f"Annotation chain valid ({len(store.load_all_annotations())} annotations)")
    else:
        typer.echo(f"Annotation chain INVALID: {len(errors)} errors")
        for error in errors:
            typer.echo(f"  - {error}")
        raise typer.Exit(code=6)


# ============================================================
# Serve (optional HTTP server)
# ============================================================


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to."),
    port: int = typer.Option(8501, "--port", "-p", help="Port to bind to."),
) -> None:
    """Start the Streamlit serve UI (FR-007, optional)."""
    typer.echo("[Optional] serve — use 'streamlit run' directly")


# ============================================================
# Entry point
# ============================================================


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
