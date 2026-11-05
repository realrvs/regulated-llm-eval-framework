"""CLI entry point for Regulated LLM Eval Framework."""

from __future__ import annotations

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
        help="Path to YAML config file (CLI > env > config > defaults).",
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
    """Global CLI flags — processed before subcommands."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["log_level"] = log_level
    ctx.obj["traceparent"] = traceparent
    ctx.obj["x_request_id"] = x_request_id


# ============================================================
# Placeholder subcommands — implemented in later tasks
# ============================================================


@app.command()
def dataset_load(
    path: str = typer.Option(..., "--path", "-p", help="Path to JSONL/JSON golden set file."),
    version: str | None = typer.Option(
        None, "--version", "-V", help="Explicit version (else from manifest or 0.1.0)."
    ),
    strict: bool = typer.Option(True, "--strict", help="Pydantic strict mode."),
) -> None:
    """Load and validate a golden set (FR-001)."""
    typer.echo("[T-104] dataset load — not yet implemented")


@app.command()
def run(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Dataset name@version, e.g. tax_qa_v1@1.2.0."),
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
    typer.echo("[T-1001] run — not yet implemented")


@app.command()
def calibrate(
    dataset: str = typer.Option(..., "--dataset", "-d", help="Calibration dataset name."),
    judge_model: str = typer.Option(..., "--judge-model", "-j", help="Judge model for calibration."),
    threshold: float = typer.Option(0.6, "--threshold", "-t", help="Cohen's kappa threshold."),
    ci_level: float = typer.Option(0.95, "--ci-level", help="Confidence interval level."),
) -> None:
    """Calibrate judge against expert annotations (FR-005)."""
    typer.echo("[T-405] calibrate — not yet implemented")


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
# Entry point
# ============================================================


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
