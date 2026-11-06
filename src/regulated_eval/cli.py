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
import sys
import uuid
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
def main(
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
    version: str | None = typer.Option(
        None, "--version", "-V", help="Explicit version (else from manifest or 0.1.0)."
    ),
    strict: bool = typer.Option(False, "--strict", help="Pydantic strict mode."),
) -> None:
    """Load and validate a golden set (FR-001)."""
    from regulated_eval.datasets.loader import load_golden_set  # noqa: PLC0414
    from regulated_eval.datasets.versioning import (  # noqa: PLC0414
        create_golden_set_summary,
        compute_dataset_hash,
        next_version,
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
    judge_model: str | None = typer.Option(
        None, "--judge-model", "-j", help="Judge model (default: same as --model)."
    ),
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
    judge_model: str = typer.Option(..., "--judge-model", "-j", help="Judge model."),
    threshold: float = typer.Option(0.6, "--threshold", "-t", help="Cohen's kappa threshold."),
    ci_level: float = typer.Option(0.95, "--ci-level", help="Confidence interval level."),
) -> None:
    """Calibrate judge against expert annotations (FR-005)."""
    typer.echo("[T-405] calibrate — not yet implemented")


# ============================================================
# Report command (FR-009)
# ============================================================


@app.command()
def report(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID for report generation."),
    format: str = typer.Option("md", "--format", "-f", help="Report format: md, html, both."),
    compare: str | None = typer.Option(
        None, "--compare", "-c", help="Run ID of previous run for delta comparison."
    ),
    output_dir: str = typer.Option("reports/", "--output-dir", "-o", help="Output directory."),
) -> None:
    """Generate Markdown/HTML report (FR-009)."""
    typer.echo("[T-803] report — not yet implemented")


# ============================================================
# A/B command (FR-008)
# ============================================================


@app.command()
def ab(
    prompt_a: str = typer.Option(..., "--prompt-a", help="Prompt A file or identifier."),
    prompt_b: str = typer.Option(..., "--prompt-b", help="Prompt B file or identifier."),
    dataset: str = typer.Option(..., "--dataset", "-d", help="Dataset path."),
    model: str = typer.Option(..., "--model", "-m", help="Model to test."),
) -> None:
    """Run A/B test between two prompts or models (FR-008)."""
    typer.echo("[T-702] ab — not yet implemented")


# ============================================================
# Conflicts resolve (FR-007)
# ============================================================


@app.command()
def conflicts_resolve(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID to resolve conflicts for."),
) -> None:
    """Resolve judge vs expert conflicts (FR-007)."""
    typer.echo("[T-405] conflicts resolve — not yet implemented")


# ============================================================
# Run replay (FR-012)
# ============================================================


@app.command(name="replay")
def run_replay(
    run_id: str = typer.Option(..., "--run", "-r", help="Run ID to replay."),
) -> None:
    """Replay a previous run for reproducibility (FR-012)."""
    typer.echo("[T-1003] run replay — not yet implemented")


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
