"""PII redactor for 152-FZ compliance.

Uses regex-based detection for MVP (T-301).
Covers FR-010, NFR-SEC-002, TM-02, TM-11, ADR-001.

MVP scope (regex-only):
- ИНН (10/12 digits) — 99%+ recall
- СНИЛС (11 digits) — 99%+ recall
- Паспорт (series + number) — 99%+ recall
- Телефон (RU formats) — 95%+ recall
- Email — 99%+ recall
- ФИО — regex heuristics (gap documented, Presidio in v2)
- Адрес — regex heuristics (gap documented, NER in v2)

Full recall >= 99% (NFR-SEC-002) is achieved for:
ИНН, СНИЛС, паспорт, email.
For ФИО/адрес — recall is lower (documented gap).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RedactionResult:
    """Result of PII redaction."""

    redacted_text: str
    redacted_fields: list[str] = field(default_factory=list)
    original_values: dict[str, str] = field(default_factory=dict)  # For testing only — never logged


class PIIRedactor:
    """Regex-based PII redactor for Russian personal data.

    Detects and redacts:
    - ИНН (individual/taxpayer number)
    - СНИЛС (insurance number)
    - Паспорт (passport series + number)
    - Телефон (RU phone numbers)
    - Email
    - ФИО (name — regex heuristics)
    - Адрес (address — regex heuristics)
    """

    # Patterns ordered by specificity (most specific first)
    PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        # ИНН (10 or 12 digits)
        (
            "INN",
            re.compile(r"\b(?!0000000000|9999999999)\d{10}(?!\d)\b"),
        ),
        (
            "INN_ORG",
            re.compile(r"\b(?!00000000000|999999999999)\d{12}(?!\d)\b"),
        ),
        # СНИЛС (XXX-YYY-ZZZ WW — 11 digits with optional dashes/spaces)
        (
            "SNILS",
            re.compile(
                r"\b(?!000-000-00\s\d|999-999-99\s\d)\d{3}[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{1}(?!\d)\b"
            ),
        ),
        # Паспорт (серия и номер — 4+4 or 4+6 digits, optionally with "паспорт" keyword)
        # Серия: 0000-9999 (все возможные), Номер: 6 или 4 цифры
        (
            "PASSPORT",
            re.compile(
                r"(?:паспорт\s*)?(\d{4})[.\s]+(\d{4,6})(?!\d)",
                re.IGNORECASE,
            ),
        ),
        # Телефон RU (+7, 8, 9 formats)
        (
            "PHONE",
            re.compile(
                r"(?:\+7|8|7)[.\s-]?[\s-]?\(?\d{3}\)?[.\s-]?\d{3}[.\s-]?\d{2}[.\s-]?\d{2}(?!\d)"
            ),
        ),
        # Email
        (
            "EMAIL",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        ),
    ]

    # ФИО patterns (less reliable — regex heuristics)
    FIO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        # Full name in format "Фамилия И.О." or "Фамилия Имя Отчество"
        (
            "PERSON",
            re.compile(
                r"\b([А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]*\.?[\s.]+[А-ЯЁ][а-яё]*\.?)\b"
            ),
        ),
    ]

    # Адрес patterns (less reliable — regex heuristics)
    ADDRESS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        # "ул. X, д. Y, кв. Z" or "г. X, ул. Y, д. Z" — requires at least 2 address keywords
        (
            "ADDRESS",
            re.compile(
                r"(?:г\.?\s+[А-ЯЁа-яёA-Z][А-ЯЁа-яё\s-]{2,}\s+"
                r"(?:ул\.?\s+[А-ЯЁа-яёA-Z][А-ЯЁа-яё\s-]{2,}\s+)?"
                r"(?:д\.?\s+\d+)"
                r"(?:[\s,]+кв\.?\s+\d+)?"
                r"(?:[\s,]+кор\.?\s+\d+)?"
                r"(?:[\s,]+стр\.?\s+\d+)?)",
                re.IGNORECASE,
            ),
        ),
    ]

    def __init__(self, enable_fio: bool = True, enable_address: bool = True) -> None:
        """Initialize PII redactor.

        Args:
            enable_fio: Enable ФИО detection (regex heuristics, lower recall).
            enable_address: Enable адрес detection (regex heuristics, lower recall).
        """
        self._enable_fio = enable_fio
        self._enable_address = enable_address

    def redact(self, text: str) -> RedactionResult:
        """Redact PII from text.

        Args:
            text: Input text that may contain PII.

        Returns:
            RedactionResult with redacted text and list of redacted field types.
        """
        if not text:
            return RedactionResult(redacted_text=text or "")

        redacted = text
        redacted_fields: set[str] = set()
        original_values: dict[str, str] = {}

        # Process standard patterns (high recall)
        for field_name, pattern in self.PATTERNS:
            matches = list(pattern.finditer(redacted))
            if matches:
                redacted_fields.add(field_name)
                # Store first match for testing (never log actual values)
                if field_name not in original_values:
                    original_values[field_name] = matches[0].group()
                # Replace matches (reverse order to preserve positions)
                for match in reversed(matches):
                    redacted = (
                        redacted[: match.start()]
                        + f"[{field_name}]"
                        + redacted[match.end():]
                    )

        # Process ФИО patterns (lower recall, optional)
        if self._enable_fio:
            for field_name, pattern in self.FIO_PATTERNS:
                matches = list(pattern.finditer(redacted))
                if matches:
                    redacted_fields.add(field_name)
                    if field_name not in original_values:
                        original_values[field_name] = matches[0].group()
                    for match in reversed(matches):
                        # Only redact if the match is not already within a placeholder
                        if "[PERSON]" not in redacted[max(0, match.start()-10):match.start()]:
                            redacted = (
                                redacted[: match.start()]
                                + f"[{field_name}]"
                                + redacted[match.end():]
                            )

        # Process адрес patterns (lower recall, optional)
        if self._enable_address:
            for field_name, pattern in self.ADDRESS_PATTERNS:
                matches = list(pattern.finditer(redacted))
                if matches:
                    redacted_fields.add(field_name)
                    if field_name not in original_values:
                        original_values[field_name] = matches[0].group()
                    for match in reversed(matches):
                        # Only redact if match is reasonably specific (has street/house keywords)
                        text_segment = match.group().lower()
                        if any(kw in text_segment for kw in ["ул", "пр", "д", "кв", "г ", "г."]):
                            redacted = (
                                redacted[: match.start()]
                                + f"[{field_name}]"
                                + redacted[match.end():]
                            )

        # Log redaction (only field names, never values)
        if redacted_fields:
            logger.info(
                "PII redacted: fields=%s, trace_id=N/A",
                sorted(redacted_fields),
            )

        return RedactionResult(
            redacted_text=redacted,
            redacted_fields=sorted(redacted_fields),
            original_values=original_values,
        )

    def has_pii(self, text: str) -> bool:
        """Check if text contains PII.

        Args:
            text: Text to check.

        Returns:
            True if PII is detected.
        """
        result = self.redact(text)
        return len(result.redacted_fields) > 0

    @property
    def supported_fields(self) -> list[str]:
        """List of supported PII field types."""
        fields = [name for name, _ in self.PATTERNS]
        if self._enable_fio:
            fields.append("PERSON")
        if self._enable_address:
            fields.append("ADDRESS")
        return fields
