"""Human-in-the-loop package.

Covers FR-007, NFR-SEC-005, TM-09, ADR-005.

Submodules:
- annotation_store: Persistent storage with hash-chain integrity
"""

from __future__ import annotations

from regulated_eval.human_loop.annotation_store import AnnotationStore

__all__ = ["AnnotationStore"]
