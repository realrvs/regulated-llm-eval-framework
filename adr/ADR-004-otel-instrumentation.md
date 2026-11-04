# ADR-004: OTel-инструментация — auto + manual с redaction-middleware

## Статус
Accepted

## Контекст

Observability Contract (spec.md) требует 13 сигналов: 6 метрик, 3 спана, 4 audit-лога. NFR-OBS: eval-run p95 ≤ 300s, judge p95 ≤ 5000ms, availability ≥ 99.0%. Threat model выявил TM-11 (Risk 12, High — PII в OTel-атрибутах). Есть `otel-sdk-python` в `existing_instrumentation`.

Нужно:
1. Инструментировать все runtime-пути (eval.run, judge.evaluate, adapter.call).
2. Гарантировать, что PII/secrets не попадают в атрибуты.
3. Пробросить `traceparent` между CLI → адаптер → LLM-провайдер.
4. Не раздувать код ручной инструментацией везде, где можно auto.

Альтернативы:
1. **Только auto-instrumentation** (`opentelemetry-instrumentation-httpx`, `-fastapi`, etc.) — быстро, но нет бизнес-атрибутов (`llm.provider`, `llm.role`, `run.id`), нет контроля над PII.
2. **Только manual** — полный контроль, но много boilerplate, легко забыть спан.
3. **Auto + manual (гибрид) + redaction-middleware** — auto для HTTP-клиентов и фреймворков, manual для бизнес-операций, redaction-middleware на уровне OTel SDK для фильтрации атрибутов.
4. **OTel Collector с processor для redaction** — redaction на стороне Collector, но PII уже ушёл из процесса (нарушение NFR-SEC-002 — «PII не покидает процесс»).

## Решение

Выбираем **вариант 3: auto + manual + redaction-middleware на уровне SDK**:

- **Auto-instrumentation:**
  - `opentelemetry-instrumentation-httpx` — спаны `HTTP CLIENT` для вызовов YandexGPT/GigaChat/OpenAI.
  - `opentelemetry-instrumentation-logging` — корреляция логов с трейсами.
  - `opentelemetry-instrumentation-asyncio` — контекст в async-тасках.
- **Manual instrumentation:**
  - `eval.run` (span) — root span прогона, атрибуты `run.id`, `dataset.version`, `model.name`.
  - `judge.evaluate` (span) — на каждый вызов судьи, атрибуты `record.id`, `judge.model`, `judge.prompt.version`.
  - `adapter.call` (span) — на каждый вызов адаптера, атрибуты `llm.provider`, `llm.model`.
  - Метрики (`eval.run.duration`, `llm.request.duration`, `judge.calibration.kappa`, `hallucination.rate`, `citation_accuracy`) — через `opentelemetry.metrics`.
  - Audit-логи (`security.pii.redacted`, `injection.suspected`, `judge.conflict.resolved`, `ab.test.completed`) — через `opentelemetry.sdk._logs` + structured JSON.
- **Redaction-middleware (ключевое для TM-11):**
  - `observability/otel_setup.py::RedactingSpanProcessor` — кастомный `SpanProcessor`, который на `on_end` фильтрует атрибуты по allowlist.
  - **Allowlist атрибутов:** `run.id`, `dataset.version`, `model.provider`, `model.name`, `llm.provider`, `llm.model`, `llm.role`, `record.id`, `judge.model`, `judge.prompt.version`, `error.reason`, `http.method`, `http.route`, `http.status_code`, `trace_id`.
  - **Запрещённые атрибуты:** `question`, `reference_answer`, `model_answer`, `rationale`, `prompt`, `api_key`, `authorization`, `pii.*` (кроме `field.name`).
  - Если атрибут не в allowlist — он удаляется, счётчик `otel.attribute.dropped{name}` инкрементируется.
  - Аналогично для логов (`RedactingLogProcessor`).
- **Корреляция:**
  - W3C `traceparent` — auto через `httpx` instrumentation.
  - `X-Request-ID` — генерируется в CLI, кладётся в `run.id`, добавляется в HTTP-заголовки адаптером.
- **Экспорт:** OTLP → Collector → Prometheus (метрики) / Loki (логи) / Jaeger (спаны). Конфигурируется через env `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Последствия

**Плюсы:**
- Покрывает TM-11 → NFR-SEC-002 (PII не попадает в OTel).
- Бизнес-атрибуты в спанах — можно фильтровать в Jaeger по `run.id`, `llm.provider`.
- Auto-instrumentation снижает boilerplate.
- Единый механизм redaction для спанов и логов.

**Минусы:**
- Redaction-middleware добавляет ~1–2ms на спан. Митигация: allowlist-check O(1), кэш.
- Custom SpanProcessor — нужно тестировать (TC-OBS-004). Митигация: unit-тесты + integration-тест с OTel Collector.
- Allowlist нужно поддерживать при добавлении новых сигналов. Митигация: allowlist в коде + тест, который проверяет, что все сигналы из Observability Contract имеют разрешённые атрибуты.

**Риски:**
- Разработчик добавляет PII-атрибут, middleware его дропает, но бизнес-логика ломается. → **Митигация:** `otel.attribute.dropped` метрика + alert при > 0 в production; в CI — тест, что обязательные атрибуты из Observability Contract не дропаются.
- OTel Collector недоступен → буферизация в SDK, потеря при переполнении. → **Митигация:** `OTEL_BSP_MAX_QUEUE_SIZE`, `OTEL_BSP_MAX_EXPORT_BATCH_SIZE`, best-effort (не блокирует прогон).
- Performance overhead на eval-run. → **Митигация:** sampling (`ParentBased(TraceIdRatioBased(0.1))` для success-прогонов, 100% для ошибок).

**Влияние на наблюдаемость:**
- Добавлен `RedactingSpanProcessor` и `RedactingLogProcessor`.
- Новая метрика `otel.attribute.dropped{name}` (counter).
- Новый audit-лог `otel.redaction.drop{attribute.name, run.id, trace_id}` — при дропе в production (для аудита).
- Sampling policy зафиксирована в конфиге.

## Альтернативы

| Альтернатива | Отклонена | Причина |
|---|---|---|
| Только auto | Да | Нет бизнес-атрибутов, нет контроля PII |
| Только manual | Да | Boilerplate, легко забыть спан |
| Redaction в Collector | Да | PII покидает процесс → нарушение NFR-SEC-002 |
| Без OTel (свои метрики) | Да | Не совместимо с существующим стеком, дублирование |