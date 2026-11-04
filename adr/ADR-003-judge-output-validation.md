# ADR-003: Стратегия валидации вывода судьи (Pydantic + repair-retry)

## Статус
Accepted

## Контекст

FR-004 требует, чтобы LLM-as-a-judge возвращал структурированный результат: `score ∈ [1..5]`, бинарные флаги (`hallucination`, `wrong_citation`, `incorrect_refusal`), обоснование. Threat model выявил TM-04 (Risk 9 — Insecure Output Handling: judge возвращает невалидный JSON / эксплойт, например `__proto__` или гигантский payload). TB-05 (LLM output → Judge/Metrics) — untrusted → trusted.

Проблема: LLM недетерминирован, иногда возвращает:
- невалидный JSON (запятые, кавычки, markdown-обёртка),
- JSON с лишними/недостающими полями,
- JSON с `score=7` (вне диапазона),
- JSON с огромным payload (DoS),
- JSON с инъекцией (`__proto__`, `constructor`).

Альтернативы:
1. **Строгий fail:** любая ошибка → запись помечается `parse_error`, прогон продолжается. Просто, но много `parse_error` → метрики неполные.
2. **Pydantic + repair-retry:** 1 retry с repair-промптом («твой предыдущий ответ невалиден, верни строгий JSON по схеме X»), при повторной ошибке — `parse_error`. Компромисс.
3. **Pydantic + N retry (N=3):** больше попыток, дороже, но выше success rate.
4. **Fallback-модель:** при ошибке — переключиться на другую модель судьи. Сложно, дорого.
5. **Regex-парсинг:** вытащить `score` и флаги regex-ом. Хрупко, не покрывает вложенные структуры.

## Решение

Выбираем **вариант 2: Pydantic-валидация + 1 repair-retry**:

- Судья возвращает JSON. Парсим через `JudgeResult.model_validate_json()` (Pydantic v2, strict mode).
- **Ограничения до парсинга:**
  - размер ответа ≤ 8 KB (защита от DoS, TM-04),
  - запрет ключей `__proto__`, `constructor`, `prototype` (защита от prototype pollution),
  - запрет вложенности > 3 уровней.
- **При ошибке валидации:** 1 retry с repair-промптом:
  ```
  Your previous response was invalid: {error}. Return ONLY valid JSON matching this schema: {schema}. No markdown, no explanations.
  ```
- **При повторной ошибке:** запись помечается `judge_status=parse_error`, попадает в отчёт, прогон продолжается (не падает).
- **Логирование:** `judge.parse_error{record.id, error.type, trace_id}` — для мониторинга.
- **Метрика:** `judge.parse_error.rate` — если > 5%, alert (значит, промпт судьи плохой).
- **Никогда не выполняем** код из ответа судьи (никакого `eval`, `exec`, `pickle`).

**Дополнительно (TM-04):**
- Pydantic v2 `strict=True` — не коэрсит типы (`score: int` не примет `"5"`).
- `score: Literal[1,2,3,4,5]` — явный диапазон.
- `rationale: str = Field(max_length=2000)` — ограничение размера.
- `model_config = ConfigDict(extra="forbid")` — запрет лишних полей.

## Последствия

**Плюсы:**
- Высокий success rate (~95–98% после 1 retry) при низкой стоимости.
- Защита от DoS и prototype pollution (TM-04).
- Прозрачная метрика `judge.parse_error.rate` — видно, когда промпт судьи деградировал.
- Pydantic v2 strict — надёжная типизация.

**Минусы:**
- 1 retry = +1 вызов LLM при ошибке → +стоимость. Митигация: retry только при ошибке, метрика `judge.retry.count` для контроля.
- Repair-промпт может сам спровоцировать галлюцинацию. Митигация: repair-промпт минималистичный, без контекста вопроса (только схема + ошибка).
- Pydantic strict может отклонить валидный по смыслу JSON (`"score": "5"`). Митигация: в repair-промпте явно указать типы.

**Риски:**
- Судья возвращает JSON с огромным вложенным payload → DoS. → **Митигация:** лимит 8 KB + запрет вложенности > 3 + Pydantic strict.
- Repair-retry создаёт бесконечный цикл. → **Митигация:** жёсткий лимит 1 retry.
- `parse_error` > 5% → метрики недостоверны. → **Митигация:** alert, блокировка публикации отчёта при `parse_error.rate > 5%`.

**Влияние на наблюдаемость:**
- Новый сигнал `judge.parse_error` (log, structured).
- Метрика `judge.parse_error.rate` (gauge).
- Метрика `judge.retry.count` (counter).
- Алерт `judge.parse_error.rate > 0.05`.

## Альтернативы

| Альтернатива | Отклонена | Причина |
|---|---|---|
| Строгий fail без retry | Да | Много `parse_error`, метрики неполные |
| N retry (N=3) | Да | Дороже, эффект насыщается после 1 retry |
| Fallback-модель | Да | Сложно, дорого, непрозрачно |
| Regex-парсинг | Да | Хрупко, не покрывает вложенные структуры |
| LLM-based repair (второй судья) | Да | Двойная стоимость, двойная недетерминированность |