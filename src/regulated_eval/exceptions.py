"""Custom exceptions for Regulated LLM Eval Framework."""

from __future__ import annotations


class RegulatedEvalError(Exception):
    """Base exception for all framework errors."""


class ValidationError(RegulatedEvalError):
    """Pydantic or schema validation failed (exit code 2)."""


class DatasetVersionNotFound(RegulatedEvalError):
    """Requested dataset version does not exist (exit code 3)."""


class ForeignProviderNotAllowed(RegulatedEvalError):
    """Foreign provider used without opt-in (exit code 4)."""


class MissingCredentials(RegulatedEvalError):
    """API key not found in environment (exit code 5)."""


class AnnotationTampered(RegulatedEvalError):
    """Annotation hash-chain integrity violation (exit code 6)."""


class CalibrationFailed(RegulatedEvalError):
    """Judge calibration below threshold (exit code 7)."""


class RateLimitExhausted(RegulatedEvalError):
    """All retry attempts exhausted due to rate-limit (exit code 8)."""


class RunNotFound(RegulatedEvalError):
    """Requested run ID not found."""
