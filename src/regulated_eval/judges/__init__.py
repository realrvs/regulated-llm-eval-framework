# Judges package

"""LLM-as-a-judge evaluation package.

Covers FR-004, FR-005, FR-007, TM-04, TM-09, TM-10, TM-13, ADR-003, ADR-005.

Submodules:
- judge: LLM-as-a-judge with repair-retry strategy
- calibration: Cohen's kappa + bootstrap CI
- conflicts: Judge-human conflict resolution
"""

from __future__ import annotations

from regulated_eval.judges.calibration import CalibrationEngine
from regulated_eval.judges.conflicts import ConflictResolver, ResolutionType
from regulated_eval.judges.judge import Judge

__all__ = [
    "Judge",
    "CalibrationEngine",
    "ConflictResolver",
    "ResolutionType",
]
