"""Markdown report generator.

Covers FR-009, NFR-007.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from regulated_eval.schemas import CalibrationResult, MetricsBlock, RunManifest


def generate_markdown_report(
    run_id: str,
    manifest: RunManifest,
    metrics: MetricsBlock,
    calibration: CalibrationResult | None = None,
    output_dir: str | Path = "reports/",
) -> Path:
    """Generate a Markdown report for an eval run.

    Args:
        run_id: Run identifier.
        manifest: Run manifest.
        metrics: Computed metrics.
        calibration: Optional calibration result.
        output_dir: Output directory.

    Returns:
        Path to generated report file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / f"run_{run_id}.md"

    # Build report content
    lines: list[str] = []

    # Header
    lines.append(f"# Eval Report: {run_id}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Run ID | `{run_id}` |")
    lines.append(f"| Dataset | {manifest.dataset_version} (hash: `{manifest.dataset_content_hash[:16]}...`) |")
    lines.append(f"| Model | {manifest.model_provider}/{manifest.model_name} |")
    lines.append(f"| Judge | {manifest.judge_model} (prompt v{manifest.judge_prompt_version}) |")
    lines.append(f"| Seed | {manifest.seed} |")
    lines.append(f"| Tokens (in/out) | {manifest.tokens_input:,} / {manifest.tokens_output:,} |")
    if manifest.estimated_cost_rub is not None:
        lines.append(f"| Estimated Cost | {manifest.estimated_cost_rub:.4f} RUB |")
    else:
        lines.append("| Estimated Cost | N/A |")
    lines.append("")

    # Metrics
    lines.append("## Metrics")
    lines.append("")
    lines.append(f"- **Hallucination Rate:** {metrics.hallucination_rate:.2%}")
    lines.append(f"- **Citation Accuracy:** {metrics.citation_accuracy:.2%}")
    lines.append(f"- **Refusal Correctness:** {metrics.refusal_correctness:.2%}")
    lines.append(f"- **Factual Consistency:** {metrics.factual_consistency:.2%}")
    lines.append("")

    # Metrics by Category
    if metrics.by_category:
        lines.append("### Metrics by Category")
        lines.append("")
        lines.append(
            "| Category | Hallucination Rate | Citation Accuracy | Refusal Correctness | Factual Consistency |"
        )
        lines.append("|----------|-------------------|-------------------|---------------------|---------------------|")
        for cat, cat_metrics in sorted(metrics.by_category.items()):
            hr = cat_metrics.get("hallucination_rate", "N/A")
            ca = cat_metrics.get("citation_accuracy", "N/A")
            rc = cat_metrics.get("refusal_correctness", "N/A")
            fc = cat_metrics.get("factual_consistency", "N/A")

            def _fmt(v: float | str) -> str:
                if isinstance(v, float):
                    return f"{v:.2%}"
                return str(v)

            lines.append(f"| {cat} | {_fmt(hr)} | {_fmt(ca)} | {_fmt(rc)} | {_fmt(fc)} |")
        lines.append("")

    # Metrics by Difficulty
    if metrics.by_difficulty:
        lines.append("### Metrics by Difficulty")
        lines.append("")
        lines.append(
            "| Difficulty | Hallucination Rate | Citation Accuracy | Refusal Correctness | Factual Consistency |"
        )
        lines.append(
            "|------------|-------------------|-------------------|---------------------|---------------------|"
        )
        for diff, diff_metrics in sorted(metrics.by_difficulty.items()):
            hr = diff_metrics.get("hallucination_rate", "N/A")
            ca = diff_metrics.get("citation_accuracy", "N/A")
            rc = diff_metrics.get("refusal_correctness", "N/A")
            fc = diff_metrics.get("factual_consistency", "N/A")

            def _fmt(v: float | str) -> str:
                if isinstance(v, float):
                    return f"{v:.2%}"
                return str(v)

            lines.append(f"| {diff} | {_fmt(hr)} | {_fmt(ca)} | {_fmt(rc)} | {_fmt(fc)} |")
        lines.append("")

    # Calibration
    if calibration:
        lines.append("## Judge Calibration")
        lines.append("")
        lines.append(f"- **Status:** {calibration.status}")
        lines.append(
            f"- **Cohen's Kappa:** {calibration.kappa:.2f} [{int(calibration.ci_level * 100)}% CI {calibration.ci_low:.2f}-{calibration.ci_high:.2f}]"
        )
        lines.append(f"- **Agreement Rate:** {calibration.agreement:.2%}")
        lines.append(f"- **Threshold:** {calibration.threshold}")
        if calibration.recommendations:
            lines.append("")
            lines.append("**Recommendations:**")
            for rec in calibration.recommendations:
                lines.append(f"- {rec}")
        lines.append("")

    # Save report
    with report_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path
