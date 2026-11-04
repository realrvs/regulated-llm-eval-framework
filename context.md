# Context — Regulated LLM Eval Framework

## Входные данные проекта

| Параметр | Значение |
|----------|----------|
| feature | Regulated LLM Eval Framework |
| domain | data-pipeline |
| constraints | Python 3.11+, Pydantic, Typer CLI, pandas, scikit-learn, Jinja2, Streamlit, OpenTelemetry, 152-ФЗ, MIT |
| gost_compliance | false |
| security_context | regulatory: [152-ФЗ]; ai: [LLM-as-a-judge, RAG-evaluation, prompt-injection-surface, tool-calling-in-adapters]; assets: [PII, golden-set, expert-annotations, API-keys] |
| observability_context | stack: [otel, loki, prometheus, grafana]; slo: eval_run_p95_s=300, judge_latency_p95_ms=5000, availability=99.0%; existing_instrumentation: [otel-sdk-python] |

## Threat Model
- **Методология:** STRIDE + OWASP Top 10 for LLM (комбинированно)
- **Обоснование:** ai непусто (LLM-as-a-judge, RAG-eval, prompt-injection-surface, tool-calling) + PII + 152-ФЗ + secrets + внешние интеграции → правило 1 (STRIDE + OWASP LLM)
- **Скоуп:** CLI, адаптеры, PII-redactor, injection filter, secrets, judge, human-in-the-loop, golden set, OTel
- **Trust Boundaries:** 9 (TB-01..TB-09)
- **Ключевые угрозы:**
  - TM-01 (Risk 15, Critical) — Prompt Injection через retrieved docs → NFR-SEC-003
  - TM-02 (Risk 16, Critical) — PII утечка в LLM → NFR-SEC-002, NFR-SEC-001
  - TM-03 (Risk 15, Critical) — Secrets в логах/спанах → NFR-SEC-004
  - TM-05 (Risk 12, High) — Data poisoning golden set → FR-001, FR-002
  - TM-07 (Risk 12, High) — Model DoS → NFR-002, NFR-008
  - TM-11 (Risk 12, High) — PII в OTel-атрибутах → NFR-SEC-002
  - TM-13 (Risk 12, High) — Overreliance без калибровки → FR-005
  - TM-14 (Risk 12, High) — EoP через флаг foreign provider → NFR-SEC-001
- **Вход для ADR:** ADR-001 (PII stack), ADR-002 (provider allowlist), ADR-003 (judge output validation), ADR-004 (OTel instrumentation), ADR-005 (annotation hash chain)
## Принятые ADR
- ADR-001: Выбор PII-redaction стека (presidio + кастомные regex для РФ) — Accepted — TM-02, TM-11
- ADR-002: Provider allowlist и opt-in для foreign provider — Accepted — TM-02, TM-06, TM-08, TM-14
- ADR-003: Стратегия валидации вывода судьи (Pydantic + repair-retry) — Accepted — TM-04
- ADR-004: OTel-инструментация — auto + manual с redaction-middleware — Accepted — TM-11
- ADR-005: Хеш-цепочка аннотаций (собственная реализация) — Accepted — TM-09, TM-10
## Согласованные endpoints
- CLI: `dataset load`, `dataset list`, `run`, `calibrate`, `report`, `ab`, `conflicts resolve`, `run replay`, `annotations verify`, `serve`
- Library API: `run_eval`, `calibrate_judge`, `generate_report`, `ab_test`, `resolve_conflicts`, `replay_run`, `load_dataset`, `verify_annotations`
- Data Artifacts (JSON Schema): `golden_set_summary`, `dataset_list`, `run_result`, `metrics_block`, `run_manifest`, `judge_result`, `annotation`, `calibration_result`, `ab_result`, `conflicts_result`, `replay_result`, `annotations_verify_result`, `report_result`
- HTTP (optional serve): `POST /api/v1/runs`, `GET /api/v1/runs/{run_id}`, `POST /api/v1/runs/{run_id}/replay`, `POST /api/v1/calibrate`, `POST /api/v1/ab`
- Exit codes: 0..8 (см. api-contract.yaml#conventions.exit_codes)
## Observability
- **Стек:** otel, loki, prometheus, grafana
- **SLO:** eval_run_p95=300s; judge_p95=5000ms; availability=99.0%
- **Ключевые сигналы:** см. spec.md § Observability Contract
- **Redaction policy:** PII (ФИО, ИНН, СНИЛС, паспорт, телефон, email, адрес) редактируется до отправки в LLM; audit-лог только с `field.name`, без значений
- **Корреляция:** W3C `traceparent` между CLI → адаптер → judge → LLM-провайдер; `X-Request-ID` для library API

## Открытые вопросы
- [ ] Порог `expert_validated` в golden set v1 (≥ 80% — предварительно)
- [ ] Прайс-лист провайдеров для cost tracking (актуализировать на apply)

## Пропущенные артефакты
- (нет)

## Traceability Matrix (INCREMENTAL)

> Полная матрица — после `apply`. Здесь — сводка по артефактам.
> Детализация: FR/NFR/NFR-SEC/NFR-OBS → Test IDs → API endpoints.

| ID | Тип | Spec § | TM § | ADR | API | Task IDs | Test IDs | Verify |
|----|-----|--------|------|-----|-----|----------|----------|--------|
| FR-001 | FR | spec.md#fr-001 | TM-05 | ADR-001 | cli.dataset_load, library_api.load_dataset | T-001..T-003 | TC-001, TC-002 | Integration |
| FR-002 | FR | spec.md#fr-002 | TM-05 | — | cli.dataset_load, cli.dataset_list | T-004..T-005 | TC-003, TC-004 | Integration |
| FR-003 | FR | spec.md#fr-003 | — | ADR-002 | cli.run, library_api.run_eval | T-010..T-013 | TC-005, TC-006 | Integration |
| FR-004 | FR | spec.md#fr-004 | TM-04 | ADR-003 | cli.run, artifacts.judge_result | T-014..T-016 | TC-007, TC-008 | Integration |
| FR-005 | FR | spec.md#fr-005 | TM-13 | ADR-003 | cli.calibrate, library_api.calibrate_judge | T-017..T-018 | TC-009, TC-010 | Integration |
| FR-006 | FR | spec.md#fr-006 | — | — | cli.run, artifacts.metrics_block | T-019..T-020 | TC-011, TC-012 | Integration |
| FR-007 | FR | spec.md#fr-007 | TM-09, TM-10 | ADR-005 | cli.conflicts_resolve, artifacts.annotation | T-021..T-024 | TC-013, TC-014 | E2E |
| FR-008 | FR | spec.md#fr-008 | — | — | cli.ab, artifacts.ab_result | T-025..T-027 | TC-015, TC-016 | Integration |
| FR-009 | FR | spec.md#fr-009 | — | — | cli.report, artifacts.report_result | T-028..T-030 | TC-017, TC-018 | Integration |
| FR-010 | FR | spec.md#fr-010 | TM-02, TM-11 | ADR-001, ADR-004 | cli.run | T-031..T-033 | TC-019 | Security |
| FR-011 | FR | spec.md#fr-011 | TM-01 | — | cli.run | T-034..T-035 | TC-020 | Security |
| FR-012 | FR | spec.md#fr-012 | — | ADR-005 | cli.replay, artifacts.run_manifest | T-036..T-038 | TC-003, TC-021, TC-022 | Integration |
| FR-013 | FR | spec.md#fr-013 | TM-03 | — | cli.run | T-039..T-040 | TC-023, TC-024 | Unit |
| FR-014 | FR | spec.md#fr-014 | — | — | cli.*, library_api.* | T-041..T-042 | TC-025 | E2E |
| FR-015 | FR | spec.md#fr-015 | — | — | artifacts.run_manifest | T-043..T-044 | TC-026, TC-027 | Integration |
| NFR-001 | NFR | spec.md#nfr-001 | — | — | — | T-1113 | TC-028, TC-029 | Performance |
| NFR-002 | NFR | spec.md#nfr-002 | TM-07 | — | — | T-1113 | TC-030, TC-031 | Performance |
| NFR-003 | NFR | spec.md#nfr-003 | — | — | — | T-1112 | TC-032, TC-033 | Observability |
| NFR-004 | NFR | spec.md#nfr-004 | TM-15 | — | — | T-1113 | TC-034, TC-035 | Performance |
| NFR-005 | NFR | spec.md#nfr-005 | — | — | — | T-1003 | TC-036, TC-037 | Integration |
| NFR-006 | NFR | spec.md#nfr-006 | — | — | — | T-001, T-1203 | TC-038, TC-039 | E2E |
| NFR-007 | NFR | spec.md#nfr-007 | — | — | — | T-801, T-802, T-1113 | TC-040, TC-041 | Performance |
| NFR-008 | NFR | spec.md#nfr-008 | TM-07 | — | — | T-202, T-1103 | TC-006, TC-042, TC-043 | Integration |
| NFR-009 | NFR | spec.md#nfr-009 | — | — | — | T-1201..T-1205 | TC-044, TC-045 | CI |
| NFR-010 | NFR | spec.md#nfr-010 | — | — | — | T-1301..T-1305 | TC-046, TC-047 | E2E |
| NFR-SEC-001 | NFR-SEC | spec.md#nfr-sec-001 | TM-02, TM-06, TM-08, TM-14 | ADR-002 | cli.run, library_api.run_eval | T-055..T-056 | TC-SEC-001, TC-SEC-001b | Security |
| NFR-SEC-002 | NFR-SEC | spec.md#nfr-sec-002 | TM-02, TM-11 | ADR-001, ADR-004 | cli.run | T-057..T-059 | TC-019, TC-SEC-002, TC-SEC-002b | Security |
| NFR-SEC-003 | NFR-SEC | spec.md#nfr-sec-003 | TM-01 | — | cli.run | T-060..T-061 | TC-020, TC-SEC-003 | Security |
| NFR-SEC-004 | NFR-SEC | spec.md#nfr-sec-004 | TM-03 | — | artifacts.run_manifest | T-062..T-063 | TC-023, TC-024, TC-SEC-004 | Security |
| NFR-SEC-005 | NFR-SEC | spec.md#nfr-sec-005 | TM-09, TM-10 | ADR-005 | cli.conflicts_resolve, cli.annotations_verify | T-064..T-066 | TC-013, TC-014, TC-SEC-005, TC-SEC-005b | Security |
| NFR-OBS-001..005 | NFR-OBS | spec.md#observability-contract | TM-11 | ADR-004 | cli.* | T-067..T-072 | TC-OBS-001..010 | Observability |