"""Unit tests for PII redactor.

Covers T-1104, FR-010, NFR-SEC-002, TM-02, TM-11, ADR-001.
"""

from __future__ import annotations

import pytest

from regulated_eval.security.pii_redactor import PIIRedactor


class TestPIIRedactor:
    """Tests for PIIRedactor class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.redactor = PIIRedactor(enable_fio=True, enable_address=True)

    def test_redact_inn(self) -> None:
        """Test INN (10-digit taxpayer number) redaction."""
        text = "ИНН 7701234567 компании"
        result = self.redactor.redact(text)
        assert "[INN]" in result.redacted_text
        assert "7701234567" not in result.redacted_text
        assert "INN" in result.redacted_fields

    def test_redact_snils(self) -> None:
        """Test СНИЛС (insurance number) redaction."""
        text = "СНИЛС 123-456-789 01"
        result = self.redactor.redact(text)
        assert "[SNILS]" in result.redacted_text
        assert "123-456-789" not in result.redacted_text
        assert "SNILS" in result.redacted_fields

    def test_redact_phone(self) -> None:
        """Test Russian phone number redaction."""
        text = "Телефон: +7 (999) 123-45-67"
        result = self.redactor.redact(text)
        assert "[PHONE]" in result.redacted_text
        assert "+7 (999) 123-45-67" not in result.redacted_text
        assert "PHONE" in result.redacted_fields

    def test_redact_email(self) -> None:
        """Test email redaction."""
        text = "Email: ivan@example.com"
        result = self.redactor.redact(text)
        assert "[EMAIL]" in result.redacted_text
        assert "ivan@example.com" not in result.redacted_text
        assert "EMAIL" in result.redacted_fields

    def test_redact_multiple_pii(self) -> None:
        """Test redaction of multiple PII types in one text."""
        text = "Иванов И.И., ИНН 7701234567, телефон +7 (999) 123-45-67"
        result = self.redactor.redact(text)
        assert "7701234567" not in result.redacted_text
        assert "+7 (999) 123-45-67" not in result.redacted_text
        assert "INN" in result.redacted_fields
        assert "PHONE" in result.redacted_fields

    def test_no_pii_returns_original(self) -> None:
        """Test that text without PII is returned unchanged."""
        text = "Это обычный текст без персональных данных"
        result = self.redactor.redact(text)
        assert result.redacted_text == text
        assert result.redacted_fields == []

    def test_empty_text(self) -> None:
        """Test empty text handling."""
        result = self.redactor.redact("")
        assert result.redacted_text == ""
        assert result.redacted_fields == []

    def test_has_pii_detection(self) -> None:
        """Test has_pii detection."""
        assert self.redactor.has_pii("ИНН 7701234567") is True
        assert self.redactor.has_pii("Обычный текст") is False

    def test_supported_fields(self) -> None:
        """Test supported fields list."""
        fields = self.redactor.supported_fields
        assert "INN" in fields
        assert "SNILS" in fields
        assert "PHONE" in fields
        assert "EMAIL" in fields
        assert "PERSON" in fields
        assert "ADDRESS" in fields

    def test_disabled_fio(self) -> None:
        """Test that ФИО detection can be disabled."""
        redactor = PIIRedactor(enable_fio=False, enable_address=True)
        text = "Иванов Иван Иванович"
        result = redactor.redact(text)
        # With FIO disabled, PERSON should not be in fields
        assert "PERSON" not in result.redacted_fields

    def test_disabled_address(self) -> None:
        """Test that address detection can be disabled."""
        redactor = PIIRedactor(enable_fio=True, enable_address=False)
        text = "г. Москва, ул. Тверская, д. 1"
        result = redactor.redact(text)
        assert "ADDRESS" not in result.redacted_fields

    def test_inn_org_redaction(self) -> None:
        """Test organization INN (12-digit) redaction."""
        text = "ИНН организации 770123456789"
        result = self.redactor.redact(text)
        assert "770123456789" not in result.redacted_text
        assert "INN_ORG" in result.redacted_fields

    def test_passport_redaction(self) -> None:
        """Test passport series and number redaction."""
        text = "Паспорт 1234 567890"
        result = self.redactor.redact(text)
        assert "1234" not in result.redacted_text or "PASSPORT" in result.redacted_fields

    def test_original_values_stored(self) -> None:
        """Test that original values are stored in result (for testing only)."""
        text = "ИНН 7701234567"
        result = self.redactor.redact(text)
        assert "INN" in result.original_values
        assert result.original_values["INN"] == "7701234567"


class TestPIIRedactorEdgeCases:
    """Edge case tests for PIIRedactor."""

    def test_inn_not_false_positive(self) -> None:
        """Test that random 10-digit numbers aren't falsely detected as INN."""
        redactor = PIIRedactor()
        # Invalid INN (all zeros) should not be detected
        result = redactor.redact("0000000000")
        assert "INN" not in result.redacted_fields

    def test_snils_not_false_positive(self) -> None:
        """Test that invalid СНИЛС formats aren't detected."""
        redactor = PIIRedactor()
        # Invalid СНИЛС (all nines) should not be detected
        result = redactor.redact("999-999-99 99")
        assert "SNILS" not in result.redacted_fields

    def test_multiple_same_pii_type(self) -> None:
        """Test redaction of multiple PII of the same type."""
        text = "ИНН 7701234567 и ИНН 5001000123"
        result = redactor = PIIRedactor()
        result = redactor.redact(text)
        assert "7701234567" not in result.redacted_text
        assert "5001000123" not in result.redacted_text
