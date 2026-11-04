# ADR-001: Выбор PII-redaction стека (presidio + кастомные regex для РФ)

## Статус
Accepted

## Контекст

Threat model выявил TM-02 (Risk 16, Critical — PII утекает в LLM-провайдера) и TM-11 (Risk 12, High — PII в OTel-атрибутах). Требование NFR-SEC-002 обязывает редактировать ≥ 99% PII до отправки в LLM с audit-логом без раскрытия значений. NFR-SEC-001 требует allowlist провайдеров. NFR-006 — portability (Linux/macOS/Windows), NFR-009 — CI с покрытием ≥ 80%.

Активы PII: ФИО, ИНН (10/12 цифр), СНИЛС, паспорт (серия/номер), телефон, email, адрес. Домен — российский regulated (152-ФЗ), значит шаблоны должны покрывать РФ-форматы, а не только западные.

Альтернативы:
1. **Microsoft Presidio** (open-source) — зрелый NER+regex, но «из коробки» оптимизирован под англоязычные форматы (SSN, US phone); для РФ-форматов нужны кастомные recognizers.
2. **Кастомный regex-набор** — полный контроль, но нужно самим реализовывать NER для ФИО (тяжело) и адресов (очень тяжело).
3. **Комбинация: Presidio + кастомные recognizers для РФ-форматов** — берём NER и pipeline у Presidio, добавляем regex для ИНН/СНИЛС/паспорт/телефон РФ, и кастомный recognizer для адресов на основе ФИАС-справочника (опционально).
4. **Внешний сервис redaction (API)** — не подходит: PII уходил бы в третий сервис, нарушение 152-ФЗ, лишняя зависимость.

## Решение

Выбираем **вариант 3: Presidio + кастомные recognizers для РФ-форматов**.

- `security/pii_redactor.py` использует `presidio-analyzer` + `presidio-anonymizer`.
- Добавляем собственные recognizers:
  - `RuInnRecognizer` (10/12 цифр + checksum),
  - `RuSnilsRecognizer` (11 цифр + checksum),
  - `RuPassportRecognizer` (серия 4 + номер 6),
  - `RuPhoneRecognizer` (+7/8 + 10 цифр),
  - `RuAddressRecognizer` (эвристики: «г.», «ул.», «д.», «кв.», индексы 6 цифр) — v1 упрощённый, v2 — ФИАС.
- `EmailRecognizer` — стандартный Presidio.
- `PersonRecognizer` — Presidio NER (spacy `ru_core_news_sm`).
- Результат: `(redacted_text, redacted_fields[])`, где `redacted_fields` содержит только имена типов (`PERSON`, `INN`, `SNILS`, `PASSPORT`, `PHONE`, `EMAIL`, `ADDRESS`) — **без значений**.
- Audit-лог `security.pii.redacted{field.name, run.id, trace_id}` — только имена полей.
- Redaction применяется **до** адаптера LLM (TB-03) и **до** OTel-атрибутов (TB-08, через middleware).

**Порог качества:** ≥ 99% recall на тестовом наборе из 100 записей (TC-SEC-002). Проверка — в CI, релиз блокируется при провале.

## Последствия

**Плюсы:**
- Зрелый NER для ФИО (Presidio + spacy ru) — не изобретаем колесо.
- Кастомные regex для РФ-форматов — точность на ИНН/СНИЛС/паспорт.
- Один pipeline для LLM-промптов и OTel-атрибутов (единый redaction middleware).
- Покрывает TM-02, TM-11 → NFR-SEC-002.

**Минусы:**
- Зависимости: `presidio-analyzer`, `presidio-anonymizer`, `spacy`, `ru_core_news_sm` — увеличивают размер wheel (~150–200 MB с моделью). Митигация: модель ставится отдельно (`pip install regulated-eval[ru-ner]`), базовая установка — только regex-набор (без NER, recall ~85% для ФИО, но 99% для ИНН/СНИЛС/паспорт).
- Latency redaction ~50–150ms на запись при полном стеке. Митигация: батчинг, кэш для повторяющихся строк.
- Presidio — Microsoft, но open-source (MIT). Supply chain риск — покрывается TM-12 (pip-audit в CI).

**Риски:**
- Ложноотрицательный PII → нарушение 152-ФЗ. → **Митигация:** тест TC-SEC-002 с 100 записями, порог ≥ 99% recall, релиз блокируется при провале; в v1.1 — добавить adversarial-набор (PII с опечатками, транслит, base64).
- Ложноположительный PII (редактируем не-PII) → снижение качества judge. → **Митигация:** мониторинг `pii.redaction.false_positive` (сэмпл ручной проверки), конфигурируемый порог confidence.

**Влияние на наблюдаемость:**
- Добавлен сигнал `security.pii.redacted` (audit-log, PII-риск: только имя поля, не значение).
- Добавлена метрика `pii.redaction.count{field.type}` (для мониторинга объёма).
- Redaction middleware для OTel (см. ADR-004) фильтрует атрибуты по allowlist.

## Альтернативы

| Альтернатива | Отклонена | Причина |
|---|---|---|
| Только Presidio (без РФ-recognizers) | Да | Не покрывает ИНН/СНИЛС/паспорт РФ → нарушение NFR-SEC-002 |
| Только кастомный regex | Да | NER для ФИО/адресов — слишком дорого в разработке и поддержке |
| Внешний redaction API | Да | PII уходил бы в третий сервис → нарушение 152-ФЗ |
| LLM-based redaction (LLM сам редактирует) | Да | Сам LLM — untrusted, галлюцинации; PII всё равно уйдёт в провайдера |