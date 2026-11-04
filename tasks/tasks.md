# Tasks: Regulated LLM Eval Framework

> Атомарность: 1 задача = 1 commit.
> ID: T-NNN, группировка по фазам (001–099 — foundation, 101–199 — datasets, 201–299 — adapters, 301–399 — security, 401–499 — judges, 501–599 — metrics, 601–699 — human_loop, 701–799 — ab, 801–899 — reports, 901–999 — observability, 1001–1099 — pipeline, 1101–1199 — tests, 1201–1299 — CI, 1301–1399 — docs, 1401–1499 — apply).
> Каждая задача ссылается на ≥1 FR/NFR/ADR. Security-задачи — на NFR-SEC + TM. Observability-задачи — на NFR-OBS + сигнал.

## Phase 0: Foundation (T-001 … T-009)

- [ ] T-001: Инициализация пакета `regulated-eval` (pyproject.toml, hatchling, MIT, Python 3.11+) (`pyproject.toml`, `LICENSE`, `README.md`)
  - **FR/NFR**: FR-014, NFR-006
  - **Estimate**: 2 SP
  - **Dependencies**: —

- [ ] T-002: Настройка src-layout и `__init__.py` с `__version__` (`src/regulated_eval/__init__.py`)
  - **FR/NFR**: FR-014
  - **Estimate**: 1 SP
  - **Dependencies**: T-001

- [ ] T-003: Базовый CLI-скелет на Typer с `--version`, `--help`, глобальными флагами (`src/regulated_eval/cli.py`)
  - **FR/NFR**: FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-002

- [ ] T-004: Pydantic-схемы (GoldenRecord, JudgeResult, RunManifest, Annotation) (`src/regulated_eval/schemas.py`)
  - **FR/NFR**: FR-001, FR-004, FR-012, NFR-SEC-005
  - **TM Ref**: TM-04, TM-05, TM-10
  - **Estimate**: 3 SP
  - **Dependencies**: T-002

- [ ] T-005: Конфиг через pydantic-settings + env (`src/regulated_eval/config.py`)
  - **FR/NFR**: FR-013, NFR-SEC-001
  - **TM Ref**: TM-03, TM-14
  - **Estimate**: 2 SP
  - **Dependencies**: T-002

- [ ] T-006: OTel bootstrap (TracerProvider, MeterProvider, LoggerProvider) + OTLP exporter (`src/regulated_eval/observability/otel_setup.py`)
  - **FR/NFR**: NFR-OBS-001..005
  - **ADR Ref**: ADR-004
  - **Estimate**: 3 SP
  - **Dependencies**: T-005

- [ ] T-007: Логирование structured JSON + корреляция с OTel (`src/regulated_eval/observability/logs.py`)
  - **FR/NFR**: NFR-OBS-001..005
  - **ADR Ref**: ADR-004
  - **Estimate**: 2 SP
  - **Dependencies**: T-006

- [ ] T-008: RedactingSpanProcessor + RedactingLogProcessor (allowlist атрибутов) (`src/regulated_eval/observability/redaction.py`)
  - **FR/NFR**: NFR-SEC-002, NFR-OBS-001..005
  - **TM Ref**: TM-11
  - **ADR Ref**: ADR-004
  - **Estimate**: 3 SP
  - **Dependencies**: T-006, T-007

- [ ] T-009: Базовые исключения (`DatasetVersionNotFound`, `ForeignProviderNotAllowed`, `MissingCredentials`, `AnnotationTampered`, `CalibrationFailed`, `RateLimitExhausted`, `RunNotFound`) (`src/regulated_eval/exceptions.py`)
  - **FR/NFR**: FR-002, FR-005, FR-013, NFR-SEC-001, NFR-SEC-005
  - **TM Ref**: TM-03, TM-09, TM-14
  - **Estimate**: 1 SP
  - **Dependencies**: T-002

## Phase 1: Datasets (T-101 … T-105)

- [ ] T-101: Pydantic-валидация golden set (strict mode) (`src/regulated_eval/datasets/loader.py`)
  - **FR/NFR**: FR-001
  - **TM Ref**: TM-05
  - **Estimate**: 3 SP
  - **Dependencies**: T-004, T-009

- [ ] T-102: Версионирование golden set (semver + content hash) (`src/regulated_eval/datasets/versioning.py`)
  - **FR/NFR**: FR-002
  - **TM Ref**: TM-05
  - **Estimate**: 2 SP
  - **Dependencies**: T-101

- [ ] T-103: RunManifest с hash-цепочкой (`src/regulated_eval/datasets/manifest.py`)
  - **FR/NFR**: FR-012
  - **TM Ref**: TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 2 SP
  - **Dependencies**: T-102

- [ ] T-104: CLI-команды `dataset load` и `dataset list` (`src/regulated_eval/cli.py`)
  - **FR/NFR**: FR-001, FR-002, FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-101, T-102, T-103, T-003

- [ ] T-105: Sample golden set (20 вопросов по УСН/НДС/взносам) для quickstart (`datasets/tax_qa_v1/sample.jsonl`)
  - **FR/NFR**: FR-001
  - **Estimate**: 2 SP
  - **Dependencies**: T-101

## Phase 2: Adapters (T-201 … T-208)

- [ ] T-201: BaseAdapter Protocol (generate, cost estimation, provider name) (`src/regulated_eval/adapters/base.py`)
  - **FR/NFR**: FR-003, FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-004, T-009

- [ ] T-202: Retry-политика с exponential backoff (tenacity) (`src/regulated_eval/adapters/retry.py`)
  - **FR/NFR**: FR-003, NFR-008
  - **TM Ref**: TM-07
  - **Estimate**: 2 SP
  - **Dependencies**: T-201

- [ ] T-203: YandexGPT адаптер (httpx, retry, cost) (`src/regulated_eval/adapters/yandexgpt.py`)
  - **FR/NFR**: FR-003
  - **TM Ref**: TM-08
  - **ADR Ref**: ADR-002
  - **Estimate**: 3 SP
  - **Dependencies**: T-201, T-202

- [ ] T-204: GigaChat адаптер (`src/regulated_eval/adapters/gigachat.py`)
  - **FR/NFR**: FR-003
  - **TM Ref**: TM-08
  - **ADR Ref**: ADR-002
  - **Estimate**: 3 SP
  - **Dependencies**: T-201, T-202

- [ ] T-205: OpenAI-compatible адаптер с opt-in (`src/regulated_eval/adapters/openai_compat.py`)
  - **FR/NFR**: FR-003, NFR-SEC-001
  - **TM Ref**: TM-02, TM-06, TM-08, TM-14
  - **ADR Ref**: ADR-002
  - **Estimate**: 3 SP
  - **Dependencies**: T-201, T-202

- [ ] T-206: Cost tracking (tokens + estimated cost per run) (`src/regulated_eval/adapters/cost.py`)
  - **FR/NFR**: FR-015
  - **Estimate**: 2 SP
  - **Dependencies**: T-201

- [ ] T-207: Provider allowlist + double opt-in (CLI + library + env + TTY) (`src/regulated_eval/security/secrets.py::is_provider_allowed`)
  - **FR/NFR**: NFR-SEC-001
  - **TM Ref**: TM-02, TM-06, TM-08, TM-14
  - **ADR Ref**: ADR-002
  - **Estimate**: 3 SP
  - **Dependencies**: T-205, T-005

- [ ] T-208: Secrets management (`get_api_key` из env, маскирование в логах) (`src/regulated_eval/security/secrets.py`)
  - **FR/NFR**: FR-013, NFR-SEC-004
  - **TM Ref**: TM-03
  - **Estimate**: 2 SP
  - **Dependencies**: T-005, T-007

## Phase 3: Security (T-301 … T-306)

- [ ] T-301: PII redactor: Presidio + кастомные regex для РФ (ИНН, СНИЛС, паспорт, телефон, адрес) (`src/regulated_eval/security/pii_redactor.py`)
  - **FR/NFR**: FR-010, NFR-SEC-002
  - **TM Ref**: TM-02, TM-11
  - **ADR Ref**: ADR-001
  - **Estimate**: 5 SP
  - **Dependencies**: T-007, T-009

- [ ] T-302: Prompt-injection фильтр retrieved-документов (allowlist + эвристики) (`src/regulated_eval/security/injection_filter.py`)
  - **FR/NFR**: FR-011, NFR-SEC-003
  - **TM Ref**: TM-01
  - **Estimate**: 3 SP
  - **Dependencies**: T-007, T-009

- [ ] T-303: Audit-логи redaction + injection (без значений, только имена) (`src/regulated_eval/security/audit.py`)
  - **FR/NFR**: NFR-SEC-002, NFR-SEC-003
  - **TM Ref**: TM-01, TM-02, TM-11
  - **Estimate**: 2 SP
  - **Dependencies**: T-301, T-302, T-007

- [ ] T-304: Интеграция PII-фильтра в адаптеры (до отправки в LLM) (`src/regulated_eval/adapters/base.py`)
  - **FR/NFR**: FR-010, NFR-SEC-002
  - **TM Ref**: TM-02
  - **Estimate**: 2 SP
  - **Dependencies**: T-301, T-201

- [ ] T-305: Annotation hash-chain (canonical JSON + sha256 + prev_hash) (`src/regulated_eval/human_loop/annotation_store.py`)
  - **FR/NFR**: NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 3 SP
  - **Dependencies**: T-004, T-009

- [ ] T-306: CLI `annotations verify` (`src/regulated_eval/cli.py`)
  - **FR/NFR**: NFR-SEC-005, FR-014
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 1 SP
  - **Dependencies**: T-305

## Phase 4: Judges (T-401 … T-407)

- [ ] T-401: LLM-as-a-judge (промпт + парсинг + repair-retry) (`src/regulated_eval/judges/judge.py`)
  - **FR/NFR**: FR-004
  - **TM Ref**: TM-04
  - **ADR Ref**: ADR-003
  - **Estimate**: 5 SP
  - **Dependencies**: T-004, T-201, T-301, T-208

- [ ] T-402: Промпт судьи v1 с few-shot и CoT (`src/regulated_eval/judges/prompts/judge_v1.md`)
  - **FR/NFR**: FR-004, FR-005
  - **TM Ref**: TM-04
  - **Estimate**: 2 SP
  - **Dependencies**: T-401

- [ ] T-403: Cohen's kappa + bootstrap CI + agreement (`src/regulated_eval/judges/calibration.py`)
  - **FR/NFR**: FR-005
  - **TM Ref**: TM-13
  - **ADR Ref**: ADR-003
  - **Estimate**: 3 SP
  - **Dependencies**: T-401

- [ ] T-404: Разрешение конфликтов judge vs эксперт (CLI + audit) (`src/regulated_eval/judges/conflicts.py`)
  - **FR/NFR**: FR-007, NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 2 SP
  - **Dependencies**: T-401, T-305

- [ ] T-405: CLI `calibrate` и `conflicts resolve` (`src/regulated_eval/cli.py`)
  - **FR/NFR**: FR-005, FR-007, FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-403, T-404, T-003

- [ ] T-406: Авто-проверка hash-цепочки аннотаций при старте прогона (`src/regulated_eval/pipeline.py`)
  - **FR/NFR**: NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 1 SP
  - **Dependencies**: T-305

- [ ] T-407: Calibration dataset (sample, 40 записей) (`datasets/calibration_v1/sample.jsonl`)
  - **FR/NFR**: FR-005
  - **Estimate**: 2 SP
  - **Dependencies**: T-403

## Phase 5: Metrics (T-501 … T-505)

- [ ] T-501: Hallucination rate + citation accuracy (`src/regulated_eval/metrics/hallucination.py`, `citation.py`)
  - **FR/NFR**: FR-006
  - **Estimate**: 2 SP
  - **Dependencies**: T-401

- [ ] T-502: Refusal correctness + factual consistency (`src/regulated_eval/metrics/refusal.py`)
  - **FR/NFR**: FR-006
  - **Estimate**: 2 SP
  - **Dependencies**: T-401

- [ ] T-503: Агрегатор метрик по category/difficulty/model (pandas) (`src/regulated_eval/metrics/aggregator.py`)
  - **FR/NFR**: FR-006
  - **Estimate**: 3 SP
  - **Dependencies**: T-501, T-502

- [ ] T-504: Метрики OTel (`hallucination.rate`, `citation_accuracy`) (`src/regulated_eval/observability/metrics.py`)
  - **FR/NFR**: FR-006, NFR-OBS-001..005
  - **ADR Ref**: ADR-004
  - **Estimate**: 2 SP
  - **Dependencies**: T-503, T-006

- [ ] T-505: Обработка `N/A` для отсутствующих категорий (`src/regulated_eval/metrics/aggregator.py`)
  - **FR/NFR**: FR-006
  - **Estimate**: 1 SP
  - **Dependencies**: T-503

## Phase 6: Human-in-the-loop (T-601 … T-603)

- [ ] T-601: Streamlit-приложение для экспертной разметки (`src/regulated_eval/human_loop/streamlit_app.py`)
  - **FR/NFR**: FR-007
  - **TM Ref**: TM-09
  - **Estimate**: 3 SP
  - **Dependencies**: T-305, T-401

- [ ] T-602: Annotation store: сохранение с hash, загрузка, валидация (`src/regulated_eval/human_loop/annotation_store.py`)
  - **FR/NFR**: FR-007, NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **ADR Ref**: ADR-005
  - **Estimate**: 3 SP
  - **Dependencies**: T-305

- [ ] T-603: Conflict resolution UI (встроен в Streamlit) (`src/regulated_eval/human_loop/streamlit_app.py`)
  - **FR/NFR**: FR-007
  - **Estimate**: 2 SP
  - **Dependencies**: T-601, T-404

## Phase 7: A/B (T-701 … T-703)

- [ ] T-701: Bootstrap CI + Wilcoxon + Cohen's d (`src/regulated_eval/ab/bootstrap.py`, `significance.py`, `effect_size.py`)
  - **FR/NFR**: FR-008
  - **Estimate**: 3 SP
  - **Dependencies**: T-503

- [ ] T-702: A/B orchestrator + CLI `ab` (`src/regulated_eval/ab/__init__.py`, `cli.py`)
  - **FR/NFR**: FR-008, FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-701, T-003

- [ ] T-703: Интерпретация результатов (`not_significant`, recommendation) (`src/regulated_eval/ab/significance.py`)
  - **FR/NFR**: FR-008
  - **Estimate**: 1 SP
  - **Dependencies**: T-701

## Phase 8: Reports (T-801 … T-803)

- [ ] T-801: Jinja2-шаблоны (Markdown, HTML) (`src/regulated_eval/reports/templates/`)
  - **FR/NFR**: FR-009, NFR-007
  - **Estimate**: 2 SP
  - **Dependencies**: T-503, T-403

- [ ] T-802: Renderer Markdown + HTML (`src/regulated_eval/reports/markdown.py`, `html.py`)
  - **FR/NFR**: FR-009, NFR-007
  - **Estimate**: 3 SP
  - **Dependencies**: T-801

- [ ] T-803: Delta-отчёт (compare_run_id) + CLI `report` (`src/regulated_eval/reports/__init__.py`, `cli.py`)
  - **FR/NFR**: FR-009, FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-802, T-003

## Phase 9: Observability (T-901 … T-907)

- [ ] T-901: Span `eval.run` в EvalOrchestrator (`src/regulated_eval/pipeline.py`)
  - **FR/NFR**: NFR-OBS-001
  - **ADR Ref**: ADR-004
  - **Estimate**: 2 SP
  - **Dependencies**: T-006

- [ ] T-902: Span `judge.evaluate` (`src/regulated_eval/judges/judge.py`)
  - **FR/NFR**: NFR-OBS-002
  - **ADR Ref**: ADR-004
  - **Estimate**: 1 SP
  - **Dependencies**: T-401, T-006

- [ ] T-903: Span `adapter.call` + `llm.request.duration` (`src/regulated_eval/adapters/base.py`)
  - **FR/NFR**: NFR-OBS-003
  - **ADR Ref**: ADR-004
  - **Estimate**: 1 SP
  - **Dependencies**: T-201, T-006

- [ ] T-904: Метрика `eval.run.duration` + `eval.run.failed` (`src/regulated_eval/observability/metrics.py`)
  - **FR/NFR**: NFR-OBS-001
  - **ADR Ref**: ADR-004
  - **Estimate**: 1 SP
  - **Dependencies**: T-901, T-504

- [ ] T-905: Audit-логи (`security.pii.redacted`, `injection.suspected`, `judge.conflict.resolved`, `ab.test.completed`) (`src/regulated_eval/observability/logs.py`)
  - **FR/NFR**: NFR-OBS-001..005
  - **TM Ref**: TM-01, TM-02, TM-09, TM-11
  - **ADR Ref**: ADR-004
  - **Estimate**: 2 SP
  - **Dependencies**: T-303, T-404, T-702, T-007

- [ ] T-906: Проброс `traceparent` через `httpx` + `X-Request-ID` (`src/regulated_eval/adapters/base.py`)
  - **FR/NFR**: NFR-OBS-004
  - **ADR Ref**: ADR-004
  - **Estimate**: 2 SP
  - **Dependencies**: T-201, T-006

- [ ] T-907: Sampling policy (10% success, 100% error) (`src/regulated_eval/observability/otel_setup.py`)
  - **FR/NFR**: NFR-OBS-001..005
  - **ADR Ref**: ADR-004
  - **Estimate**: 1 SP
  - **Dependencies**: T-006

## Phase 10: Pipeline (T-1001 … T-1003)

- [ ] T-1001: EvalOrchestrator (load → redact → generate → judge → metrics → report) (`src/regulated_eval/pipeline.py`)
  - **FR/NFR**: FR-003, FR-004, FR-006, FR-009, FR-010, FR-011, FR-012
  - **TM Ref**: TM-01, TM-02, TM-04, TM-07
  - **Estimate**: 5 SP
  - **Dependencies**: T-101, T-201, T-301, T-302, T-401, T-503, T-802, T-901, T-904

- [ ] T-1002: CalibrationOrchestrator (`src/regulated_eval/pipeline.py`)
  - **FR/NFR**: FR-005
  - **TM Ref**: TM-13
  - **Estimate**: 2 SP
  - **Dependencies**: T-403, T-407

- [ ] T-1003: Replay (сравнение метрик ± 1%) + CLI `run replay` (`src/regulated_eval/pipeline.py`, `cli.py`)
  - **FR/NFR**: FR-012, NFR-005
  - **Estimate**: 2 SP
  - **Dependencies**: T-1001, T-003

## Phase 11: Tests (T-1101 … T-1114)

- [ ] T-1101: Unit-тесты foundation (config, exceptions, schemas) (`tests/unit/test_foundation.py`)
  - **FR/NFR**: FR-014, NFR-SEC-001
  - **Estimate**: 2 SP
  - **Dependencies**: T-001..T-009

- [ ] T-1102: Unit + integration тесты datasets (TC-001..TC-004) (`tests/unit/test_datasets.py`, `tests/integration/test_datasets.py`)
  - **FR/NFR**: FR-001, FR-002
  - **TM Ref**: TM-05
  - **Estimate**: 3 SP
  - **Dependencies**: T-105

- [ ] T-1103: Unit + integration тесты adapters (TC-005, TC-006) (`tests/integration/test_adapters.py`)
  - **FR/NFR**: FR-003, NFR-008
  - **TM Ref**: TM-07
  - **Estimate**: 3 SP
  - **Dependencies**: T-208

- [ ] T-1104: Security-тесты PII + injection (TC-019, TC-020, TC-SEC-002, TC-SEC-003) (`tests/security/test_pii.py`, `test_injection.py`)
  - **FR/NFR**: FR-010, FR-011, NFR-SEC-002, NFR-SEC-003
  - **TM Ref**: TM-01, TM-02, TM-11
  - **Estimate**: 5 SP
  - **Dependencies**: T-301, T-302, T-303

- [ ] T-1105: Security-тесты secrets + provider allowlist (TC-023, TC-024, TC-SEC-001, TC-SEC-001b, TC-SEC-004) (`tests/security/test_secrets.py`, `test_provider_allowlist.py`)
  - **FR/NFR**: FR-013, NFR-SEC-001, NFR-SEC-004
  - **TM Ref**: TM-03, TM-14
  - **Estimate**: 3 SP
  - **Dependencies**: T-207, T-208

- [ ] T-1106: Security-тесты hash-цепочки (TC-SEC-005, TC-SEC-005b) (`tests/security/test_annotation_chain.py`)
  - **FR/NFR**: NFR-SEC-005
  - **TM Ref**: TM-09, TM-10
  - **Estimate**: 3 SP
  - **Dependencies**: T-305

- [ ] T-1107: Unit-тесты judges (TC-007, TC-008) (`tests/unit/test_judge.py`)
  - **FR/NFR**: FR-004
  - **TM Ref**: TM-04
  - **Estimate**: 2 SP
  - **Dependencies**: T-401

- [ ] T-1108: Integration-тесты калибровки (TC-009, TC-010) (`tests/integration/test_calibration.py`)
  - **FR/NFR**: FR-005
  - **TM Ref**: TM-13
  - **Estimate**: 2 SP
  - **Dependencies**: T-403

- [ ] T-1109: Integration-тесты метрик (TC-011, TC-012) (`tests/integration/test_metrics.py`)
  - **FR/NFR**: FR-006
  - **Estimate**: 2 SP
  - **Dependencies**: T-503

- [ ] T-1110: E2E-тесты human-in-the-loop (TC-013, TC-014) (`tests/e2e/test_human_loop.py`)
  - **FR/NFR**: FR-007
  - **TM Ref**: TM-09
  - **Estimate**: 3 SP
  - **Dependencies**: T-601, T-602, T-404

- [ ] T-1111: Integration-тесты A/B (TC-015, TC-016) (`tests/integration/test_ab.py`)
  - **FR/NFR**: FR-008
  - **Estimate**: 2 SP
  - **Dependencies**: T-701

- [ ] T-1112: Observability-тесты (TC-OBS-001..010) (`tests/observability/`)
  - **FR/NFR**: NFR-OBS-001..005
  - **TM Ref**: TM-11
  - **Estimate**: 5 SP
  - **Dependencies**: T-907

- [ ] T-1113: Performance-тесты (TC-028, TC-030, TC-034, TC-040, TC-041) (`tests/performance/`)
  - **FR/NFR**: NFR-001, NFR-002, NFR-004, NFR-007
  - **Estimate**: 3 SP
  - **Dependencies**: T-1001, T-802

- [ ] T-1114: E2E-тесты CLI vs library (TC-025) (`tests/e2e/test_cli_vs_library.py`)
  - **FR/NFR**: FR-014
  - **Estimate**: 2 SP
  - **Dependencies**: T-1001, T-003

## Phase 12: CI (T-1201 … T-1205)

- [ ] T-1201: GitHub Actions: lint (ruff) + mypy (`.github/workflows/lint.yml`)
  - **FR/NFR**: NFR-009
  - **Estimate**: 1 SP
  - **Dependencies**: T-001

- [ ] T-1202: GitHub Actions: pytest + coverage ≥ 80% (`.github/workflows/test.yml`)
  - **FR/NFR**: NFR-009
  - **Estimate**: 2 SP
  - **Dependencies**: T-1101..T-1114

- [ ] T-1203: GitHub Actions: matrix (ubuntu/macos/windows × py3.11/3.12) (TC-038, TC-039) (`.github/workflows/matrix.yml`)
  - **FR/NFR**: NFR-006, NFR-009
  - **Estimate**: 2 SP
  - **Dependencies**: T-1202

- [ ] T-1204: GitHub Actions: pip-audit (TM-12) (`.github/workflows/security.yml`)
  - **FR/NFR**: NFR-009
  - **TM Ref**: TM-12
  - **Estimate**: 1 SP
  - **Dependencies**: T-1201

- [ ] T-1205: GitHub Actions: docs-check (методология + PRD + case_study) (TC-047) (`.github/workflows/docs.yml`)
  - **FR/NFR**: NFR-010
  - **Estimate**: 1 SP
  - **Dependencies**: T-1301

## Phase 13: Documentation (T-1301 … T-1305)

- [ ] T-1301: README с quickstart ≤ 5 минут (TC-046) (`README.md`)
  - **FR/NFR**: NFR-010
  - **Estimate**: 2 SP
  - **Dependencies**: T-1001

- [ ] T-1302: `methodology.md` (как считаем метрики, калибровку, A/B) (`docs/methodology.md`)
  - **FR/NFR**: FR-005, FR-006, FR-008, NFR-010
  - **Estimate**: 2 SP
  - **Dependencies**: T-403, T-503, T-701

- [ ] T-1303: `PRD.md` (проблема, пользователи, scope, метрики) (`docs/PRD.md`)
  - **FR/NFR**: NFR-010
  - **Estimate**: 2 SP
  - **Dependencies**: —

- [ ] T-1304: `case_study.md` (гипотеза → методология → результаты → выводы) (`docs/case_study.md`)
  - **FR/NFR**: NFR-010
  - **Estimate**: 2 SP
  - **Dependencies**: T-1001, T-1302

- [ ] T-1305: `152-ФЗ.md` (раздел про foreign providers и opt-in) (`docs/152fz.md`)
  - **FR/NFR**: NFR-SEC-001
  - **TM Ref**: TM-02, TM-14
  - **ADR Ref**: ADR-002
  - **Estimate**: 1 SP
  - **Dependencies**: T-207

## Phase 14: Apply (T-1401 … T-1403)

- [ ] T-1401: Миграции / seed-данные (sample golden set + calibration) (`datasets/`)
  - **FR/NFR**: FR-001, FR-005
  - **Estimate**: 1 SP
  - **Dependencies**: T-105, T-407

- [ ] T-1402: Feature flags (env-based: `REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER`, `REGULATED_EVAL_ACK_152FZ`, `REGULATED_EVAL_OTEL_ENABLED`) (`src/regulated_eval/config.py`)
  - **FR/NFR**: NFR-SEC-001, NFR-OBS-001..005
  - **TM Ref**: TM-14
  - **ADR Ref**: ADR-002
  - **Estimate**: 1 SP
  - **Dependencies**: T-005, T-207

- [ ] T-1403: Observability Verification checklist (в `apply.md`) (`apply/apply.md`)
  - **FR/NFR**: NFR-OBS-001..005
  - **Estimate**: 1 SP
  - **Dependencies**: T-907, T-1112

---

## Summary

| Phase | Tasks | SP |
|---|---|---|
| 0: Foundation | T-001..T-009 (9) | 19 |
| 1: Datasets | T-101..T-105 (5) | 11 |
| 2: Adapters | T-201..T-208 (8) | 19 |
| 3: Security | T-301..T-306 (6) | 16 |
| 4: Judges | T-401..T-407 (7) | 18 |
| 5: Metrics | T-501..T-505 (5) | 10 |
| 6: Human-in-the-loop | T-601..T-603 (3) | 8 |
| 7: A/B | T-701..T-703 (3) | 6 |
| 8: Reports | T-801..T-803 (3) | 7 |
| 9: Observability | T-901..T-907 (7) | 10 |
| 10: Pipeline | T-1001..T-1003 (3) | 9 |
| 11: Tests | T-1101..T-1114 (14) | 40 |
| 12: CI | T-1201..T-1205 (5) | 7 |
| 13: Docs | T-1301..T-1305 (5) | 9 |
| 14: Apply | T-1401..T-1403 (3) | 3 |
| **Итого** | **96 задач** | **191 SP** |

> Оценка: ~191 SP ≈ 8–10 недель при 20 SP/неделю (1 разработчик). Для MVP (без полного покрытия тестами и CI-матрицы) — ~6 недель.

## Traceability (Task → FR/NFR/TM/ADR)

| Task | FR/NFR | TM Ref | ADR Ref | Estimate |
|---|---|---|---|---|
| T-001 | FR-014, NFR-006 | — | — | 2 |
| T-004 | FR-001, FR-004, FR-012, NFR-SEC-005 | TM-04, TM-05, TM-10 | ADR-005 | 3 |
| T-008 | NFR-SEC-002, NFR-OBS-001..005 | TM-11 | ADR-004 | 3 |
| T-207 | NFR-SEC-001 | TM-02, TM-06, TM-08, TM-14 | ADR-002 | 3 |
| T-301 | FR-010, NFR-SEC-002 | TM-02, TM-11 | ADR-001 | 5 |
| T-302 | FR-011, NFR-SEC-003 | TM-01 | — | 3 |
| T-305 | NFR-SEC-005 | TM-09, TM-10 | ADR-005 | 3 |
| T-401 | FR-004 | TM-04 | ADR-003 | 5 |
| T-403 | FR-005 | TM-13 | ADR-003 | 3 |
| T-904 | NFR-OBS-001 | — | ADR-004 | 1 |
| T-1001 | FR-003, FR-004, FR-006, FR-009, FR-010, FR-011, FR-012 | TM-01, TM-02, TM-04, TM-07 | — | 5 |
| T-1104 | FR-010, FR-011, NFR-SEC-002, NFR-SEC-003 | TM-01, TM-02, TM-11 | — | 5 |
| T-1112 | NFR-OBS-001..005 | TM-11 | ADR-004 | 5 |
| ... | ... | ... | ... | ... |

> Полная матрица — в `context.md` (Traceability Matrix).