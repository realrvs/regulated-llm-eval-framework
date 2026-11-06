"""HTML report generator.

Covers FR-009, NFR-007.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from regulated_eval.schemas import CalibrationResult, MetricsBlock, RunManifest


def generate_html_report(
    run_id: str,
    manifest: RunManifest,
    metrics: MetricsBlock,
    calibration: CalibrationResult | None = None,
    output_dir: str | Path = "reports/",
) -> Path:
    """Generate an HTML report for an eval run.

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

    report_path = output_dir / f"run_{run_id}.html"

    # Build HTML content
    html = _build_html(run_id, manifest, metrics, calibration)

    with report_path.open("w", encoding="utf-8") as f:
        f.write(html)

    return report_path


def _build_html(
    run_id: str,
    manifest: RunManifest,
    metrics: MetricsBlock,
    calibration: CalibrationResult | None,
) -> str:
    """Build HTML report content.

    Args:
        run_id: Run identifier.
        manifest: Run manifest.
        metrics: Computed metrics.
        calibration: Optional calibration result.

    Returns:
        HTML string.
    """
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    cost_display = (
        f"{manifest.estimated_cost_rub:.4f} RUB"
        if manifest.estimated_cost_rub is not None
        else "N/A"
    )

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"UTF-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "<title>Eval Report: {}".format(run_id),
        "</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }",
        ".container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        "h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }",
        "h2 { color: #555; margin-top: 30px; }",
        "table { width: 100%; border-collapse: collapse; margin: 15px 0; }",
        "th, td { padding: 10px 15px; text-align: left; border-bottom: 1px solid #ddd; }",
        "th { background: #007bff; color: white; }",
        "tr:hover { background: #f5f5f5; }",
        ".metric { font-size: 1.2em; font-weight: bold; }",
        ".pass { color: #28a745; }",
        ".fail { color: #dc3545; }",
        ".summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }",
        ".summary-card { background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff; }",
        ".summary-card label { font-size: 0.85em; color: #666; display: block; }",
        ".summary-card value { font-size: 1.3em; font-weight: bold; color: #333; }",
        "</style>",
        "</head>",
        "<body>",
        "<div class=\"container\">",
        "<h1>Eval Report: {}".format(run_id),
        "<p><small>Generated: {}</small></p>".format(generated),
        "</div>",
    ]

    # Summary cards
    html_parts.extend([
        "<div class=\"container\">",
        "<h2>Summary</h2>",
        "<div class=\"summary-grid\">",
        '<div class="summary-card"><label>Dataset</label><value>{} v{}</value></div>'.format(
            manifest.dataset_version.split(".")[0] if "." in manifest.dataset_version else manifest.dataset_version,
            manifest.dataset_version,
        ),
        '<div class="summary-card"><label>Model</label><value>{}/{} </value></div>'.format(
            manifest.model_provider, manifest.model_name
        ),
        '<div class="summary-card"><label>Judge</label><value>{}</value></div>'.format(
            manifest.judge_model
        ),
        '<div class="summary-card"><label>Tokens (in/out)</label><value>{:,} / {:,}</value></div>'.format(
            manifest.tokens_input, manifest.tokens_output
        ),
        '<div class="summary-card"><label>Cost</label><value>{}</value></div>'.format(cost_display),
        '<div class="summary-card"><label>Seed</label><value>{}</value></div>'.format(manifest.seed),
        "</div>",
    ])

    # Metrics
    html_parts.extend([
        "<h2>Metrics</h2>",
        "<table>",
        "<tr><th>Metric</th><th>Value</th></tr>",
        "<tr><td>Hallucination Rate</td><td class=\"metric\">{:.2%}</td></tr>".format(
            metrics.hallucination_rate
        ),
        "<tr><td>Citation Accuracy</td><td class=\"metric\">{:.2%}</td></tr>".format(
            metrics.citation_accuracy
        ),
        "<tr><td>Refusal Correctness</td><td class=\"metric\">{:.2%}</td></tr>".format(
            metrics.refusal_correctness
        ),
        "<tr><td>Factual Consistency</td><td class=\"metric\">{:.2%}</td></tr>".format(
            metrics.factual_consistency
        ),
        "</table>",
    ])

    # Metrics by category
    if metrics.by_category:
        html_parts.extend([
            "<h2>Metrics by Category</h2>",
            "<table>",
            "<tr><th>Category</th><th>Hallucination</th><th>Citation</th><th>Refusal</th><th>Consistency</th></tr>",
        ])
        for cat, cat_metrics in sorted(metrics.by_category.items()):
            hr = cat_metrics.get("hallucination_rate", 0)
            ca = cat_metrics.get("citation_accuracy", 0)
            rc = cat_metrics.get("refusal_correctness", 0)
            fc = cat_metrics.get("factual_consistency", 0)
            html_parts.append(
                "<tr><td>{}</td><td>{:.2%}</td><td>{:.2%}</td><td>{:.2%}</td><td>{:.2%}</td></tr>".format(
                    cat, hr, ca, rc, fc
                )
            )
        html_parts.append("</table>")

    # Metrics by difficulty
    if metrics.by_difficulty:
        html_parts.extend([
            "<h2>Metrics by Difficulty</h2>",
            "<table>",
            "<tr><th>Difficulty</th><th>Hallucination</th><th>Citation</th><th>Refusal</th><th>Consistency</th></tr>",
        ])
        for diff, diff_metrics in sorted(metrics.by_difficulty.items()):
            hr = diff_metrics.get("hallucination_rate", 0)
            ca = diff_metrics.get("citation_accuracy", 0)
            rc = diff_metrics.get("refusal_correctness", 0)
            fc = diff_metrics.get("factual_consistency", 0)
            html_parts.append(
                "<tr><td>{}</td><td>{:.2%}</td><td>{:.2%}</td><td>{:.2%}</td><td>{:.2%}</td></tr>".format(
                    diff, hr, ca, rc, fc
                )
            )
        html_parts.append("</table>")

    # Calibration
    if calibration:
        status_class = "pass" if calibration.status == "PASS" else "fail"
        html_parts.extend([
            "<h2>Judge Calibration</h2>",
            "<table>",
            "<tr><td>Status</td><td class=\"{}\">{}</td></tr>".format(status_class, calibration.status),
            "<tr><td>Cohen's Kappa</td><td>{:.2f} [{}% CI {:.2f}-{:.2f}]</td></tr>".format(
                calibration.kappa,
                int(calibration.ci_level * 100),
                calibration.ci_low,
                calibration.ci_high,
            ),
            "<tr><td>Agreement Rate</td><td>{:.2%}</td></tr>".format(calibration.agreement),
            "<tr><td>Threshold</td><td>{}</td></tr>".format(calibration.threshold),
            "</table>",
        ])
        if calibration.recommendations:
            html_parts.append("<h3>Recommendations</h3><ul>")
            for rec in calibration.recommendations:
                html_parts.append("<li>{}</li>".format(rec))
            html_parts.append("</ul>")

    html_parts.extend([
        "</div>",
        "</body>",
        "</html>",
    ])

    return "\n".join(html_parts)
