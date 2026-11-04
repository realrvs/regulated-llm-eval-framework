# Apply: Regulated LLM Eval Framework

> Финальный артефакт pipeline. Содержит: миграции, feature flags, canary deployment, observability verification, rollback plan.
> Definition of Done — в конце документа.

## Миграции

Проект greenfield, миграций схемы БД нет. «Миграции» — это seed-данные и совместимость артефактов между версиями.

- [ ] **M-001: Seed golden set v1.2.0** — 20 sample-вопросов для quickstart + 120 полных (для публичного кейса) (`datasets/tax_qa_v1/sample.jsonl`, `datasets/tax_qa_v1/full.jsonl`)
  - **FR/NFR**: FR-001
  - **Estimate**: 1 SP
  - **Rollback**: удалить файлы, `dataset list` покажет пусто

- [ ] **M-002: Seed calibration dataset v1** — 40 экспертных аннотаций для калибровки (`datasets/calibration_v1/sample.jsonl`)
  - **FR/NFR**: FR-005
  - **Estimate**: 1 SP
  - **Rollback**: удалить файл, `calibrate` вернёт `DatasetVersionNotFound`

- [ ] **M-003: Миграция схемы `RunManifest` v1.0.0 → v1.1.0** (добавление `ack_source` для foreign provider, ADR-002)
  - **FR/NFR**: FR-012, NFR-SEC-001
  - **TM Ref**: TM-14
  - **ADR Ref**: ADR-002
  - **Estimate**: 1 SP
  - **Rollback**: старые манифесты читаются как `ack_source="not_applicable"`; новые — не откатываются (forward-only)

- [ ] **M-004: Миграция hash-цепочки аннотаций** — при первом запуске v1.0.0 на существующих аннотациях (без `hash`) — `annotations migrate --path` проставляет `hash` и `prev_hash` по цепочке
  - **FR/NFR**: NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 2 SP
  - **Rollback**: `annotations verify --path` покажет `valid=true` после миграции; при откате — предупреждение `broken_at` для записей без hash

## Feature Flags

| Flag | Default | TTL | Связанный FR | Связанный TM |
|---|---|---|---|---|
| `REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER` | `false` | постоянно (env) | FR-003, NFR-SEC-001 | TM-02, TM-14 |
| `REGULATED_EVAL_ACK_152FZ` | `false` | постоянно (env) | NFR-SEC-001 | TM-14 |
| `REGULATED_EVAL_OTEL_ENABLED` | `true` | 90 дней (потом — default `true` без флага) | NFR-OBS-001..005 | TM-11 |
| `REGULATED_EVAL_OTEL_SAMPLING_RATIO` | `0.1` (success), `1.0` (error) | 90 дней | NFR-OBS-001..005 | — |
| `REGULATED_EVAL_PII_REDACTION_ENABLED` | `true` | постоянно (нельзя отключить в production) | FR-010, NFR-SEC-002 | TM-02, TM-11 |
| `REGULATED_EVAL_INJECTION_FILTER_ENABLED` | `true` | постоянно (нельзя отключить в production) | FR-011, NFR-SEC-003 | TM-01 |
| `REGULATED_EVAL_ANNOTATION_CHAIN_ENABLED` | `true` | постоянно | NFR-SEC-005 | TM-09, TM-10 |

> **Важно:** PII redaction, injection filter и annotation chain **не отключаемы** в production (нарушение 152-ФЗ / NFR-SEC). Флаги существуют только для тестовых сценариев (mock-адаптеры, тесты).

## Canary Deployment (для HTTP-обёртки `serve`, если используется в CI)

1. **Deploy canary 5% трафика** на `serve` (если развёрнут в CI-инфраструктуре).
2. **Monitor SLO canary vs baseline:**
   - `eval.run.duration` p95 ≤ 300s (NFR-001)
   - `llm.request.duration{role="judge"}` p95 ≤ 5000ms (NFR-002)
   - `eval.run.failed{reason="internal"}` rate ≤ 1% (NFR-003)
   - `judge.calibration.kappa` ≥ 0.6 (FR-005, TM-13)
   - `annotation.tamper` = 0 (NFR-SEC-005)
   - `otel.attribute.dropped` = 0 для обязательных атрибутов (ADR-004)
   - `provider.foreign.allowed{ack_source="env"}` — мониторинг (TM-14)
3. **Auto-rollback при degradation > 10% по любому SLO:**
   - Trigger: Prometheus alert `SloDegradation` fires.
   - Action: feature flag toggle (`REGULATED_EVAL_OTEL_ENABLED=false` для отключения телеметрии) → ротация pods → rollback deployment.
   - **PII redaction, injection filter, annotation chain — НЕ отключаются даже при rollback** (безопасность важнее SLO).
4. Если canary stable 24h → 50% → 100%.
5. Отключить feature flag для old code path (если был).

> Для CLI-сценария (локальный запуск) canary не применим — вместо этого используется `run replay` (FR-012) с проверкой `reproducible=true`.

## Observability Verification

> Проверка, что сигналы из Observability Contract реально видны в бэкендах после деплоя.

- [ ] **OV-01: Grafana dashboard** — виден дашборд с RED-метриками для фичи:
  - `eval.run.duration` (histogram, p50/p95/p99)
  - `eval.run.failed` (counter, by `error.reason`)
  - `llm.request.duration` (histogram, by `llm.provider`, `llm.role`)
  - `judge.calibration.kappa` (gauge)
  - `hallucination.rate`, `citation_accuracy` (gauges, by `dataset.version`, `model.name`)

- [ ] **OV-02: Loki** — есть логи с `trace_id` для тестового запроса:
  - `security.pii.redacted{field.name, run.id, trace_id}` — **без значений PII**
  - `injection.suspected{source, run.id, trace_id}` — **без содержимого документа**
  - `judge.conflict.resolved{record.id, resolution, annotator.id, trace_id}`
  - `ab.test.completed{prompt.a, prompt.b, delta, p_value, trace_id}`

- [ ] **OV-03: Jaeger / OTel** — виден трейс, связанный с `trace_id` из HTTP/CLI:
  - Span `eval.run` (root) с атрибутами `run.id`, `dataset.version`, `model.name`
  - Span `judge.evaluate` (child) с `record.id`, `judge.model`, `judge.prompt.version`
  - Span `adapter.call` (child) с `llm.provider`, `llm.model`
  - `traceparent` присутствует в исходящем HTTP-запросе к LLM-провайдеру

- [ ] **OV-04: Prometheus alerts** — срабатывают на тестовом сценарии:
  - `EvalRunSloViolation` (p95 > 300s)
  - `JudgeSloViolation` (p95 > 5s)
  - `AvailabilitySloViolation` (< 99.0%)
  - `RateLimitHigh` (> 20% rate-limited)
  - `AnnotationTamper` (> 0)
  - `PiiLeakDetected` (grep нашёл PII в логах) — **критичный**
  - `OtelAttributeDropped` (> 0 для обязательных атрибутов)
  - `ForeignProviderEnvUsage` (еженедельно, `ack_source="env"`)

- [ ] **OV-05: `security.pii.redacted` audit-лог фиксируется при redaction** — проверить на тестовой записи с ИНН:
  - В логе только `field.name="INN"`, без значения `770123456789`
  - `pii_redacted=true` во всех спанах

- [ ] **OV-06: Retention policy** — соответствует NFR-SEC-002:
  - Audit-логи `security.pii.redacted` — retention ≥ 1 год (152-ФЗ, аудит)
  - Спаны с `trace_id` — retention ≥ 30 дней
  - Метрики — retention ≥ 90 дней (Prometheus)
  - PII в логах — **0 записей** (проверка через grep-тест в CI)

- [ ] **OV-07: Sampling policy** — проверено, что:
  - Success-прогоны сэмплируются 10% (`REGULATED_EVAL_OTEL_SAMPLING_RATIO=0.1`)
  - Error-прогоны — 100% (не сэмплируются)
  - Sampling не влияет на метрики (histograms всегда полные)

## Rollback Plan

### Rollback v1.0.0 (полный)

1. **Stop new runs** — CLI-команда `regulated-eval serve stop` (если используется) или остановка CI-пайплайна.
2. **Feature flags:**
   - `REGULATED_EVAL_OTEL_ENABLED=false` (отключает экспорт телеметрии, не блокирует прогоны)
   - `REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER=false`
   - `REGULATED_EVAL_ACK_152FZ=false`
3. **Pip-package rollback:** `pip install regulated-eval==<prev_version>` (стабильная предыдущая версия, если была).
4. **Data rollback (если нужно):**
   - `datasets/` — откат через git (`git checkout <prev_tag> -- datasets/`)
   - `annotations/` — **не откатывать** (hash-цепочка защищает от подмены; откат = tamper)
   - `reports/` — можно удалить (генерируются заново)
5. **Verify rollback:**
   - `regulated-eval --version` показывает предыдущую версию
   - `regulated-eval dataset list` — видит предыдущие датасеты
   - `regulated-eval annotations verify --path annotations/` — `valid=true`
6. **Post-rollback:** уведомить владельца продукта, создать post-mortem, зафиксировать в `docs/incidents/`.

### Rollback M-003 (схема RunManifest v1.0.0 → v1.1.0)

- Forward-only: новые манифесты с `ack_source` не читаются старым кодом (Pydantic `extra="forbid"` — упадёт с `ValidationError`).
- **Rollback:** только откат кода к версии, поддерживающей v1.0.0. Манифесты v1.1.0 остаются в `manifests/` — старый код их пропустит (skip), новые прогоны создадут v1.0.0.
- **Митигация:** перед деплоем M-003 — `run replay` на эталонном прогоне для проверки совместимости.

### Rollback M-004 (hash-цепочка аннотаций)

- Миграция forward-only. Откат невозможен без потери hash.
- **Митигация:** перед миграцией — бэкап `annotations/` в git (`git commit -m "pre-migration annotations backup"`).
- При откате — `annotations verify` покажет `broken_at` для записей без `hash`; требуется повторная миграция.

---

## Definition of Done (OpenSpec)

- [x] Все FR покрыты ≥1 Task и ≥1 Test
  - FR-001..FR-015 → T-101..T-206, TC-001..TC-027 ✅
- [x] Все NFR покрыты ≥1 Task, ≥1 Test и ≥1 Verify Method
  - NFR-001..NFR-010 → T-1113, T-1201..T-1205, T-1301..T-1305, TC-028..TC-047 ✅
- [x] Все NFR-SEC покрывают ≥1 TM-NNN и имеют Security-тест
  - NFR-SEC-001..005 → TM-01..TM-14, TC-SEC-001..005b ✅
- [x] Все TM-NNN имеют контроль и связанный NFR-SEC
  - TM-01..TM-15 → NFR-SEC-001..005, TC-SEC-* ✅
- [x] Методология Threat Modeling обоснована и зафиксирована в `context.md`
  - STRIDE + OWASP LLM, обоснование в `threat-model.md` § 1 ✅
- [x] Trust Boundaries визуализированы с цветовой кодировкой
  - 9 TB (TB-01..TB-09), Mermaid-диаграмма ✅
- [x] Нет ADR без связи с design.md (§) или TM (§)
  - ADR-001..ADR-005 → TM-02, TM-11, TM-04, TM-09/10, TM-11 ✅
- [x] Нет пустых обязательных ячеек в Traceability Matrix
  - Заполнено в `context.md` ✅
- [x] Матрица Task → FR/NFR/TM полностью построена
  - 96 задач, все с FR/NFR/TM/ADR ✅
- [x] `context.md` актуален
  - Обновлён на каждом шаге (Threat Model, ADR, Endpoints, Traceability) ✅
- [x] Все NFR-OBS покрыты ≥1 Task, ≥1 Observability-тест и ≥1 сигналом в Observability Contract
  - NFR-OBS-001..005 → T-901..T-907, TC-OBS-001..010, 13 сигналов ✅
- [x] Observability Contract заполнен для каждой фичи с runtime-путём
  - 6 метрик + 3 спана + 4 audit-лога + SLO ✅
- [x] В `apply.md` есть Observability Verification checklist
  - OV-01..OV-07 ✅
- [x] Корреляция (`traceparent` / `X-Request-ID`) зафиксирована в API Contract
  - `conventions.correlation`, `cli.run`, `library_api_http` ✅
- [x] Все сигналы с PII имеют redaction-контроль, связанный с TM
  - `security.pii.redacted` → TM-02, TM-11 → ADR-001, ADR-004 ✅
- [x] (Если `gost_compliance: true`) Сгенерированы все соответствующие ГОСТ-документы
  - `gost_compliance: false` — ГОСТ не требуется ✅

---

## Post-Apply Checklist (для первого публичного релиза)

- [ ] **Git tag** `v1.0.0` + GitHub Release с notes
- [ ] **PyPI publish** (`twine upload dist/*`)
- [ ] **README quickstart** проверен на чистой машине (≤ 5 минут, TC-046)
- [ ] **Case study** опубликован (`docs/case_study.md` → пост в LinkedIn/Telegram)
- [ ] **152-ФЗ раздел** в README (`docs/152fz.md` → ссылка из README)
- [ ] **Security policy** (`SECURITY.md` с контактом для disclosure)
- [ ] **Contributing guide** (`CONTRIBUTING.md`)
- [ ] **License** MIT (`LICENSE`)
- [ ] **CI зелёный** на всех 3 ОС × 2 версиях Python
- [ ] **Coverage ≥ 80%** (TC-044)
- [ ] **pip-audit** без critical/high (TM-12)
- [ ] **Observability Verification** (OV-01..OV-07) выполнена
- [ ] **Rollback Plan** протестирован на staging
- [ ] **Post-mortem template** создан (`docs/incidents/template.md`)
- [ ] **Владелец продукта** уведомлён о релизе

---

## Финальная сводка проекта

| Артефакт | Файл | Строк (≈) | Статус |
|---|---|---|---|
| Proposal | `proposal.md` | 80 | ✅ |
| Specs | `specs/eval-pipeline/spec.md` | 400 | ✅ |
| Design | `design/design.md` | 350 | ✅ |
| Threat Model | `threat-model/threat-model.md` | 250 | ✅ |
| ADR | `adr/ADR-001..005.md` | 500 | ✅ |
| API Contract | `api/api-contract.yaml` | 450 | ✅ |
| Test Specs | `test-specs/eval-pipeline/tests.md` | 600 | ✅ |
| Tasks | `tasks/tasks.md` | 500 | ✅ |
| Apply | `apply/apply.md` | 200 | ✅ |
| Context | `context.md` | 150 | ✅ |

**Итого:** 9 артефактов OpenSpec + context.md, ~3500 строк документации, 96 задач, 64 теста, 15 угроз, 5 ADR, 13 сигналов observability.

**Оценка реализации:** ~191 SP ≈ 8–10 недель для 1 разработчика; ~6 недель для MVP.

**Готовность к отклику на вакансию «Директор по клиентским ИИ-продуктам»:**
- ✅ Клиентский GenAI-продукт (eval-фреймворк) с монетизируемым потенциалом
- ✅ Калиброванный LLM-as-a-judge (Cohen's kappa ≥ 0.6) — прямое требование вакансии
- ✅ Golden set + LLM-as-a-judge + экспертная проверка + A/B — прямое требование
- ✅ PII redaction + 152-ФЗ + injection filter — релевантно «Моё Дело»
- ✅ YandexGPT + GigaChat — российские LLM
- ✅ Юнит-экономика (cost tracking, tokens, estimated_cost_rub)
- ✅ Продуктовые метрики (hallucination_rate, citation_accuracy, retention через run history)
- ✅ SQL/BI — через pandas + OTel + Prometheus/Grafana (плюс, не минус)
- ✅ MCP-интеграции (из вашего профиля) — усиливают кейс

**Следующий шаг:** запустить `tasks/tasks.md` по фазам, начиная с T-001 (Foundation), и через 6–8 недель получить публичный проект с реальным кейсом для отклика.