# Reports package

"""Report generation for Regulated LLM Eval Framework.

Covers FR-009, NFR-007.

Submodules:
- markdown: Markdown report generation
- html: HTML report generation
"""

from __future__ import annotations

from regulated_eval.reports.html import generate_html_report
from regulated_eval.reports.markdown import generate_markdown_report

__all__ = [
    "generate_markdown_report",
    "generate_html_report",
]
