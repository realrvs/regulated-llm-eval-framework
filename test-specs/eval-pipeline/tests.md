# Test Specs: eval-pipeline (Regulated LLM Eval Framework)

> Каждый FR/NFR/NFR-SEC/NFR-OBS покрыт ≥ 1 тестом.
> ID: `TC-NNN`. Priority: P0 (critical), P1 (high), P2 (medium), P3 (low).
> Security-тесты ссылаются на TM-NNN и содержат Observability Assertion об отсутствии PII.

## Functional Tests (FR)

### TC-001: Golden set загружается успешно
- **Type**: Integration
- **Covers**: FR-001
- **Priority**: P0
#### Steps
1. Given файл `datasets/tax_qa_v1.jsonl` с 120 валидными записями
2. When вызывается `load_dataset(path, version="1.2.0")`
3. Then возвращается `GoldenSet` с 120 записями, `expert_validated_ratio ≥ 0.8`, сохраняется манифест с `content_hash`
#### Data
- Input: 120 записей, все поля по схеме
- Expected Output: `GoldenSet(total=120, version="1.2.0", content_hash="sha256:...")`
#### Observability Assertions
- **Trace:** span `eval.run` отсутствует (это не прогон), но `load_dataset` эмитит `dataset.loaded` (log)
- **Logs:** `dataset.loaded{version, total_records, content_hash, trace_id}` в Loki

### TC-002: Невалидный golden set отклоняется
- **Type**: Unit
- **Covers**: FR-001
- **Priority**: P0
#### Steps
1. Given запись без `reference_answer`
2. When вызывается `load_dataset`
3. Then выбрасывается `ValidationError` с `record_id` и полем; exit code 2
#### Observability Assertions
- **Logs:** `dataset.validation.failed{record_id, field, trace_id}` в Loki

### TC-003: Прогон по фиксированной версии воспроизводим
- **Type**: Integration
- **Covers**: FR-002, FR-012
- **Priority**: P0
#### Steps
1. Given golden set v1.2.0 с content_hash `sha256:abc…`
2. When вызывается `run_eval(dataset="tax_qa_v1@1.2.0", model="yandexgpt")`
3. Then в `RunManifest` зафиксированы `dataset_version=1.2.0`, `dataset_content_hash=sha256:abc…`, `seed`, `package_version`
#### Observability Assertions
- **Trace:** span `eval.run` имеет атрибуты `dataset.version`, `model.provider`, `run.id`

### TC-004: Прогон по несуществующей версии
- **Type**: Unit
- **Covers**: FR-002
- **Priority**: P1
#### Steps
1. Given запрошена `tax_qa_v1@9.9.9`
2. When вызывается `run_eval`
3. Then `DatasetVersionNotFound`, exit code 3
#### Observability Assertions
- **Logs:** `dataset.version.not_found{requested_version, available_versions, trace_id}`

### TC-005: Успешный вызов адаптера YandexGPT
- **Type**: Integration
- **Covers**: FR-003
- **Priority**: P0
#### Steps
1. Given `YANDEXGPT_API_KEY` в env
2. When `run_eval(model="yandexgpt")`
3. Then каждый вопрос отправлен, ответ сохранён
#### Observability Assertions
- **Trace:** span `adapter.call` с `llm.provider="yandexgpt"`, `llm.model`, `trace_id`
- **Metrics:** `llm.request.duration{llm.provider="yandexgpt",llm.role="generator"}` увеличился

### TC-006: Rate-limit с retry
- **Type**: Integration
- **Covers**: FR-003, NFR-008
- **Priority**: P1
#### Steps
1. Given mock-адаптер возвращает 429 дважды, затем 200
2. When вызывается `generate`
3. Then retry с exponential backoff, итоговый успех
#### Observability Assertions
- **Metrics:** `adapter.retry.count{reason="rate_limit"}` = 2
- **Logs:** `adapter.rate_limited{attempt, backoff_ms, trace_id}`

### TC-007: Judge оценивает ответ
- **Type**: Integration
- **Covers**: FR-004
- **Priority**: P0
#### Steps
1. Given ответ модели и эталон из golden set
2. When `judge.evaluate(record, model_answer)`
3. Then `JudgeResult` с `score ∈ [1..5]`, флаги, `rationale`, `judge_model`, `judge_prompt_version`
#### Observability Assertions
- **Trace:** span `judge.evaluate` с `record.id`, `judge.model`, `judge.prompt.version`

### TC-008: Невалидный JSON от судьи → repair-retry
- **Type**: Unit
- **Covers**: FR-004
- **Priority**: P0
- **TM Ref**: TM-04
#### Steps
1. Given судья вернул невалидный JSON
2. When парсим через `JudgeResult.model_validate_json()`
3. Then 1 repair-retry; при повторной ошибке `judge_status=parse_error`, прогон не падает
#### Observability Assertions
- **Logs:** `judge.parse_error{record.id, error.type, trace_id}`
- **Metrics:** `judge.retry.count` = 1, `judge.parse_error.rate` инкрементирован
- **Security:** в repair-промпте и логах нет PII (`pii_redacted=true`)

### TC-009: Калибровка достигает порога
- **Type**: Integration
- **Covers**: FR-005
- **Priority**: P0
- **TM Ref**: TM-13
#### Steps
1. Given 40 экспертных аннотаций и ответы судьи
2. When `calibrate_judge(dataset, judge_model, threshold=0.6)`
3. Then `status=PASS`, `kappa ≥ 0.6`, `ci_low`, `ci_high`, `agreement`
#### Observability Assertions
- **Metrics:** `judge.calibration.kappa{dataset.version, judge.model}` ≥ 0.6

### TC-010: Калибровка ниже порога
- **Type**: Integration
- **Covers**: FR-005
- **Priority**: P0
- **TM Ref**: TM-13
#### Steps
1. Given kappa=0.45
2. When вызывается `calibrate_judge(threshold=0.6)`
3. Then `status=FAIL`, `recommendations` непустой, exit code 7
#### Observability Assertions
- **Metrics:** `judge.calibration.kappa` = 0.45
- **Logs:** `calibration.failed{kappa, threshold, recommendations}`

### TC-011: Расчёт метрик по прогону
- **Type**: Integration
- **Covers**: FR-006
- **Priority**: P0
#### Steps
1. Given прогон 120 вопросов с judge-оценками
2. When `aggregate(judge_results)`
3. Then `MetricsBlock` с `hallucination_rate`, `citation_accuracy`, `refusal_correctness`, `factual_consistency`, `by_category`, `by_difficulty`
#### Observability Assertions
- **Metrics:** `hallucination.rate`, `citation_accuracy` (gauges) с атрибутами `dataset.version`, `model.name`

### TC-012: Метрика для отсутствующей категории = N/A
- **Type**: Unit
- **Covers**: FR-006
- **Priority**: P1
#### Steps
1. Given в прогоне нет `difficulty=hard`
2. When агрегируем
3. Then `by_difficulty.hard = N/A`, прогон не падает

### TC-013: Эксперт размечает запись
- **Type**: E2E
- **Covers**: FR-007
- **Priority**: P1
- **TM Ref**: TM-09
#### Steps
1. Given Streamlit UI запущен, эксперт открыл `tax_042`
2. When выставил `score=4`, флаги, нажал «Сохранить»
3. Then аннотация сохранена с `annotator_id`, `timestamp`, `hash`, `prev_hash`
#### Observability Assertions
- **Logs:** `annotation.saved{record.id, hash, annotator.id, trace_id}`
- **Security:** PII не попадает в лог (только `record.id` и `hash`)

### TC-014: Разрешение конфликта judge vs эксперт
- **Type**: Integration
- **Covers**: FR-007
- **Priority**: P1
- **TM Ref**: TM-09
#### Steps
1. Given judge=5, эксперт=2
2. When `resolve_conflicts(strategy="accept_human", annotator_id="expert_1")`
3. Then решение залогировано, `ConflictsResult.resolutions[0].resolution="accept_human"`
#### Observability Assertions
- **Logs:** `judge.conflict.resolved{record.id, resolution, annotator.id, trace_id}`

### TC-015: A/B-сравнение промптов
- **Type**: Integration
- **Covers**: FR-008
- **Priority**: P1
#### Steps
1. Given prompt A и B, golden set
2. When `ab_test(prompt_a, prompt_b, dataset, model)`
3. Then `ABResult` с `delta`, `ci_low`, `ci_high`, `p_value`, `effect_size`, `significant`, `winner`
#### Observability Assertions
- **Logs:** `ab.test.completed{prompt.a, prompt.b, delta, p_value, trace_id}`

### TC-016: A/B без статистической значимости
- **Type**: Unit
- **Covers**: FR-008
- **Priority**: P2
#### Steps
1. Given delta=0.02, p=0.32
2. When формируется отчёт
3. Then `significant=false`, `winner=null`, `recommendation` — увеличить датасет

### TC-017: Генерация Markdown-отчёта
- **Type**: Integration
- **Covers**: FR-009
- **Priority**: P0
#### Steps
1. Given завершённый прогон
2. When `generate_report(run_id, format="md")`
3. Then создан `reports/<run_id>.md` с секциями Summary, Metrics, Top Errors, Judge Calibration

### TC-018: Delta-отчёт с предыдущим прогоном
- **Type**: Integration
- **Covers**: FR-009
- **Priority**: P1
#### Steps
1. Given `<run_id>` и `<run_id_prev>`
2. When `generate_report(run_id, compare_run_id=run_id_prev)`
3. Then отчёт содержит delta-таблицу с направлением и значимостью

### TC-019: PII редактируется
- **Type**: Security
- **Covers**: FR-010, NFR-SEC-002
- **Priority**: P0
- **TM Ref**: TM-02
#### Steps
1. Given вопрос «ИП Иванов И.И., ИНН 770123456789»
2. When `redact(text)`
3. Then в исходящем тексте `[PERSON]`, `[INN]`, исходный текст не покидает процесс
#### Data
- Input: 100 записей с PII (ФИО, ИНН, СНИЛС, паспорт, телефон, email, адрес)
- Expected: ≥ 99 записей без PII в исходящем промпте
#### Observability Assertions
- **Logs:** `security.pii.redacted{field.name, run.id, trace_id}` — **без значений**
- **Security:** в логах/спанах нет исходного PII (`pii_redacted=true`)
- **Correlation:** `trace_id` присутствует в audit-логе

### TC-020: Prompt injection блокируется
- **Type**: Security
- **Covers**: FR-011, NFR-SEC-003
- **Priority**: P0
- **TM Ref**: TM-01
#### Steps
1. Given 50 retrieved-документов с prompt-injection попытками
2. When `injection_filter.check(doc)` для каждого
3. Then ≥ 48 заблокированы, `injection.suspected` залогирован
#### Observability Assertions
- **Logs:** `injection.suspected{source, run.id, trace_id}` — **без содержимого документа**
- **Metrics:** `injection.blocked.count` ≥ 48
- **Security:** в логах нет содержимого документа (только `source`)

### TC-021: Replay прогона
- **Type**: Integration
- **Covers**: FR-012
- **Priority**: P1
#### Steps
1. Given прогон `<run_id>` и его манифест
2. When `replay_run(run_id, tolerance=0.01)`
3. Then `ReplayResult.reproducible=true`, метрики в пределах ± 1%

### TC-022: Replay расходится
- **Type**: Integration
- **Covers**: FR-012, NFR-005
- **Priority**: P1
#### Steps
1. Given расхождение 5%
2. When `replay_run(run_id, tolerance=0.01)`
3. Then `reproducible=false`, `metric_deltas[*].within_tolerance=false`, указаны наиболее расходящиеся записи

### TC-023: Ключ читается из env
- **Type**: Unit
- **Covers**: FR-013
- **Priority**: P0
- **TM Ref**: TM-03
#### Steps
1. Given `YANDEXGPT_API_KEY` в env
2. When инициализируется адаптер
3. Then ключ прочитан, в логах `***`, в манифест не попадает

### TC-024: Ключ отсутствует
- **Type**: Unit
- **Covers**: FR-013
- **Priority**: P1
- **TM Ref**: TM-03
#### Steps
1. Given env-переменная не задана
2. When `run_eval`
3. Then `MissingCredentials`, exit code 5

### TC-025: CLI и library API эквивалентны
- **Type**: E2E
- **Covers**: FR-014
- **Priority**: P1
#### Steps
1. Given `regulated-eval run --dataset ... --model yandexgpt --json`
2. When сравниваем с `run_eval(dataset=..., model=...)`
3. Then `RunResult` идентичен по структуре и метрикам

### TC-026: Cost tracking
- **Type**: Integration
- **Covers**: FR-015
- **Priority**: P1
#### Steps
1. Given прогон 120 вопросов через YandexGPT
2. When прогон завершён
3. Then в манифесте `tokens_input`, `tokens_output`, `estimated_cost_rub`
#### Observability Assertions
- **Metrics:** `llm.tokens.input`, `llm.tokens.output`, `llm.cost.rub` (counters)

### TC-027: Cost tracking без прайса
- **Type**: Unit
- **Covers**: FR-015
- **Priority**: P2
#### Steps
1. Given прайс для модели не сконфигурирован
2. When прогон завершён
3. Then `estimated_cost_rub=null`, в отчёте `N/A`

---

## Non-Functional Tests (NFR)

### TC-028: Eval run в пределах SLO
- **Type**: Performance
- **Covers**: NFR-001
- **Priority**: P0
#### Steps
1. Given golden set 150 вопросов, parallelism=8
2. When прогон завершён
3. Then `eval.run.duration` p95 ≤ 300s
#### Observability Assertions
- **Metrics:** `eval.run.duration{quantile="0.95"}` ≤ 300
- **Trace:** span `eval.run` длительностью ≤ 300s

### TC-029: Eval run превышает SLO
- **Type**: Performance
- **Covers**: NFR-001
- **Priority**: P1
#### Steps
1. Given прогон занял 420s
2. When формируется отчёт
3. Then `slo_violation=eval_run_latency`, метрика `eval.run.slo_violation` = 1
#### Observability Assertions
- **Metrics:** `eval.run.slo_violation` = 1

### TC-030: Judge latency в пределах SLO
- **Type**: Performance
- **Covers**: NFR-002
- **Priority**: P0
#### Steps
1. Given 120 вызовов judge
2. When прогон завершён
3. Then `llm.request.duration{role="judge"}` p95 ≤ 5000ms

### TC-031: Judge деградация → degraded
- **Type**: Performance
- **Covers**: NFR-002
- **Priority**: P1
#### Steps
1. Given p95 judge = 12000ms
2. When агрегируются метрики
3. Then `judge.latency.slo_violation`, отчёт `degraded`
#### Observability Assertions
- **Metrics:** `judge.latency.slo_violation` = 1

### TC-032: Availability CLI в норме
- **Type**: Observability
- **Covers**: NFR-003
- **Priority**: P1
#### Steps
1. Given 1000 запусков, 3 упали по внутренним причинам
2. When агрегируется `eval.run.failed{reason="internal"}`
3. Then availability = 99.7%, SLO соблюдён

### TC-033: Availability CLI ниже SLO
- **Type**: Observability
- **Covers**: NFR-003
- **Priority**: P1
#### Steps
1. Given availability = 98.5%
2. When агрегируется
3. Then alert `availability.slo_violation`, отчёт недели помечает инцидент

### TC-034: Scalability golden set 5000
- **Type**: Performance
- **Covers**: NFR-004
- **Priority**: P1
#### Steps
1. Given golden set 5000 вопросов
2. When прогон завершён
3. Then peak memory ≤ 2GB, время линейно от 150-baseline ± 20%

### TC-035: Memory превышает лимит
- **Type**: Performance
- **Covers**: NFR-004
- **Priority**: P2
#### Steps
1. Given peak memory = 3GB
2. When прогон завершён
3. Then `memory.slo_violation`, рекомендация — batch-режим

### TC-036: Determinism replay ± 1%
- **Type**: Integration
- **Covers**: NFR-005
- **Priority**: P0
#### Steps
1. Given прогон и его replay
2. When сравниваем метрики
3. Then расхождение ≤ 1%, `reproducible=true`

### TC-037: Non-determinism > 1%
- **Type**: Integration
- **Covers**: NFR-005
- **Priority**: P1
#### Steps
1. Given расхождение 5%
2. When сравниваем
3. Then `non_deterministic`, указаны расходящиеся записи

### TC-038: Portability macOS
- **Type**: E2E
- **Covers**: NFR-006
- **Priority**: P1
#### Steps
1. Given macOS 14, Python 3.11
2. When `pip install regulated-eval`
3. Then `regulated-eval --version` работает
#### Notes
Выполняется в CI matrix (ubuntu-latest, macos-latest, windows-latest)

### TC-039: Portability Windows
- **Type**: E2E
- **Covers**: NFR-006
- **Priority**: P1
#### Steps
1. Given Windows 11, Python 3.11
2. When `pip install regulated-eval`
3. Then `regulated-eval --version` работает

### TC-040: Markdown-отчёт ≤ 10s
- **Type**: Performance
- **Covers**: NFR-007
- **Priority**: P2
#### Steps
1. Given прогон 150 вопросов
2. When `report --format md`
3. Then отчёт сгенерирован ≤ 10s

### TC-041: HTML-отчёт ≤ 30s
- **Type**: Performance
- **Covers**: NFR-007
- **Priority**: P2
#### Steps
1. Given прогон 150 вопросов
2. When `report --format html`
3. Then отчёт сгенерирован ≤ 30s

### TC-042: Rate-limit 20% без падения
- **Type**: Integration
- **Covers**: NFR-008
- **Priority**: P1
#### Steps
1. Given 120 вызовов, 24 вернули 429
2. When прогон завершён
3. Then 24 помечены `rate_limited`, остальные оценены, прогон не падает
#### Observability Assertions
- **Metrics:** `eval.run.rate_limited.count` = 24

### TC-043: Rate-limit 50% → degraded
- **Type**: Integration
- **Covers**: NFR-008
- **Priority**: P1
#### Steps
1. Given 50% вызовов вернули 429
2. When прогон завершён
3. Then прогон `degraded`, alert `rate_limit.high`
#### Observability Assertions
- **Metrics:** `rate_limit.high` = 1

### TC-044: CI coverage ≥ 80%
- **Type**: CI
- **Covers**: NFR-009
- **Priority**: P0
#### Steps
1. Given CI-прогон `pytest --cov`
2. When завершён
3. Then coverage ≥ 80% для `judges`, `metrics`, `ab`, `datasets`; CI зелёный

### TC-045: CI coverage < 80%
- **Type**: CI
- **Covers**: NFR-009
- **Priority**: P1
#### Steps
1. Given coverage = 72%
2. When CI-прогон завершён
3. Then CI падает с сообщением `coverage below threshold`

### TC-046: Quickstart ≤ 5 минут
- **Type**: E2E
- **Covers**: NFR-010
- **Priority**: P1
#### Steps
1. Given новый пользователь
2. When следует README quickstart
3. Then первый отчёт получен ≤ 5 минут

### TC-047: Документация присутствует
- **Type**: CI
- **Covers**: NFR-010
- **Priority**: P2
#### Steps
1. Given релиз без methodology.md
2. When CI проверяет
3. Then CI падает

---

## Security Tests (NFR-SEC)

### TC-SEC-001: Foreign provider без opt-in блокируется
- **Type**: Security
- **Covers**: NFR-SEC-001
- **TM Ref**: TM-02, TM-06, TM-08, TM-14
- **Priority**: P0
#### Steps
1. Given `model="openai_compat"`, флаги не заданы
2. When `run_eval`
3. Then `ForeignProviderNotAllowed`, exit code 4
#### Observability Assertions
- **Logs:** `provider.foreign.blocked{provider, trace_id}`
- **Security:** в логах нет PII (`pii_redacted=true`)

### TC-SEC-001b: Foreign provider с обоими флагами разрешён
- **Type**: Security
- **Covers**: NFR-SEC-001
- **TM Ref**: TM-14
- **Priority**: P0
#### Steps
1. Given `allow_foreign_provider=True`, `acknowledge_152fz=True`
2. When `run_eval(model="openai_compat")`
3. Then прогон выполняется, `manifest.ack_source="cli_flags"`
#### Observability Assertions
- **Logs:** `provider.foreign.allowed{provider, run.id, ack_source="cli_flags", trace_id}`

### TC-SEC-002: PII recall ≥ 99%
- **Type**: Security
- **Covers**: NFR-SEC-002
- **TM Ref**: TM-02, TM-11
- **Priority**: P0
#### Steps
1. Given 100 записей с PII (по 10 на каждый тип: ФИО, ИНН, СНИЛС, паспорт, телефон, email, адрес)
2. When `redact()` на каждой
3. Then ≥ 99 записей без PII в исходящем тексте; исходный текст не покидает процесс
#### Observability Assertions
- **Logs:** `security.pii.redacted{field.name, run.id, trace_id}` — **без значений**
- **Metrics:** `pii.redaction.count{field.type}` ≥ 99
- **Security:** в логах/спанах нет PII (`pii_redacted=true`)

### TC-SEC-002b: PII в OTel-атрибутах дропается
- **Type**: Observability
- **Covers**: NFR-SEC-002
- **TM Ref**: TM-11
- **Priority**: P0
#### Steps
1. Given разработчик добавил PII-атрибут `question` в span
2. When `RedactingSpanProcessor.on_end`
3. Then атрибут удалён, `otel.attribute.dropped{name="question"}` = 1
#### Observability Assertions
- **Metrics:** `otel.attribute.dropped{name="question"}` = 1
- **Logs:** `otel.redaction.drop{attribute.name, run.id, trace_id}`
- **Security:** в экспортированном спане нет `question`

### TC-SEC-003: Prompt injection ≥ 95% блокировки
- **Type**: Security
- **Covers**: NFR-SEC-003
- **TM Ref**: TM-01
- **Priority**: P0
#### Steps
1. Given 50 инъекций в retrieved-документах
2. When `injection_filter.check()` на каждом
3. Then ≥ 48 заблокированы
#### Observability Assertions
- **Logs:** `injection.suspected{source, run.id, trace_id}` — **без содержимого документа**
- **Metrics:** `injection.blocked.count` ≥ 48

### TC-SEC-004: Secrets никогда не логируются
- **Type**: Security
- **Covers**: NFR-SEC-004
- **TM Ref**: TM-03
- **Priority**: P0
#### Steps
1. Given прогон с `YANDEXGPT_API_KEY` в env
2. When прогон завершён
3. Then ключ отсутствует в логах, отчётах, манифестах, спанах
#### Observability Assertions
- **Security:** grep по всем артефактам не находит значение ключа (только `***`)
- **Logs:** `adapter.init{provider, api_key="***", trace_id}`

### TC-SEC-005: Hash-цепочка аннотаций
- **Type**: Security
- **Covers**: NFR-SEC-005
- **TM Ref**: TM-09, TM-10
- **Priority**: P0
#### Steps
1. Given 10 аннотаций сохранены
2. When `verify_annotations(path)`
3. Then `valid=true`, `total=10`, `broken_at=null`
#### Observability Assertions
- **Logs:** `annotation.saved{record.id, hash, annotator.id, trace_id}` для каждой
- **Metrics:** `annotations.verify.result{valid="true"}` = 1

### TC-SEC-005b: Подмена аннотации обнаруживается
- **Type**: Security
- **Covers**: NFR-SEC-005
- **TM Ref**: TM-10
- **Priority**: P0
#### Steps
1. Given аннотация изменена вручную после сохранения
2. When `verify_annotations(path)`
3. Then `valid=false`, `broken_at=<record_id>`, exit code 6
#### Observability Assertions
- **Logs:** `annotation.tamper{record.id, expected, actual, trace_id}`
- **Metrics:** `annotation.tamper` > 0 → alert

---

## Observability Tests (NFR-OBS)

### TC-OBS-001: eval.run span с обязательными атрибутами
- **Type**: Observability
- **Covers**: NFR-OBS-001
- **Priority**: P0
#### Steps
1. Given `run_eval`
2. When прогон завершён
3. Then в Jaeger есть span `eval.run` с `run.id`, `dataset.version`, `model.name`, `trace_id`
#### Observability Assertions
- **Trace:** span `eval.run` существует, все обязательные атрибуты присутствуют

### TC-OBS-002: judge.evaluate span с обязательными атрибутами
- **Type**: Observability
- **Covers**: NFR-OBS-002
- **Priority**: P0
#### Steps
1. Given `judge.evaluate`
2. When оценка завершена
3. Then span `judge.evaluate` с `record.id`, `judge.model`, `judge.prompt.version`, `trace_id`

### TC-OBS-003: adapter.call span с обязательными атрибутами
- **Type**: Observability
- **Covers**: NFR-OBS-003
- **Priority**: P0
#### Steps
1. Given вызов адаптера
2. When завершён
3. Then span `adapter.call` с `llm.provider`, `llm.model`, `trace_id`

### TC-OBS-004: RedactingSpanProcessor дропает не-allowlist атрибуты
- **Type**: Observability
- **Covers**: NFR-OBS-001..005
- **TM Ref**: TM-11
- **Priority**: P0
#### Steps
1. Given span с атрибутом `question` (не в allowlist)
2. When `on_end`
3. Then атрибут удалён, `otel.attribute.dropped{name="question"}` = 1
#### Observability Assertions
- **Metrics:** `otel.attribute.dropped`
- **Security:** в экспортированном спане нет `question`

### TC-OBS-005: Корреляция traceparent CLI → adapter → LLM
- **Type**: Observability
- **Covers**: NFR-OBS-004
- **Priority**: P1
#### Steps
1. Given `run_eval`
2. When адаптер вызывает LLM
3. Then `traceparent` передан в HTTP-заголовке; `trace_id` совпадает в span `eval.run`, `adapter.call`, `judge.evaluate`
#### Observability Assertions
- **Trace:** все спаны в одном трейсе (`trace_id` одинаковый)
- **Correlation:** `traceparent` из Camunda/CLI присутствует в LLM-спане

### TC-OBS-006: Метрики в Prometheus
- **Type**: Observability
- **Covers**: NFR-OBS-001..005
- **Priority**: P0
#### Steps
1. Given прогон завершён
2. When `curl prometheus:9090/api/v1/query?query=eval_run_duration`
3. Then метрика `eval.run.duration` присутствует с атрибутами
#### Observability Assertions
- **Metrics:** все 6 метрик из Observability Contract присутствуют

### TC-OBS-007: Логи в Loki с trace_id
- **Type**: Observability
- **Covers**: NFR-OBS-001..005
- **Priority**: P0
#### Steps
1. Given прогон завершён
2. When `curl loki:3100/loki/api/v1/query?query={job="regulated-eval"}`
3. Then все 4 audit-лога присутствуют, каждый с `trace_id`
#### Observability Assertions
- **Logs:** `security.pii.redacted`, `injection.suspected`, `judge.conflict.resolved`, `ab.test.completed` — все с `trace_id`

### TC-OBS-008: SLO eval-run p95 ≤ 300s
- **Type**: Observability
- **Covers**: NFR-OBS-001
- **Priority**: P0
#### Steps
1. Given 100 прогонов
2. When агрегируется `eval.run.duration` p95
3. Then p95 ≤ 300s
#### Observability Assertions
- **Metrics:** `eval.run.duration{quantile="0.95"}` ≤ 300

### TC-OBS-009: SLO judge p95 ≤ 5000ms
- **Type**: Observability
- **Covers**: NFR-OBS-002
- **Priority**: P0
#### Steps
1. Given 100 вызовов judge
2. When агрегируется `llm.request.duration{role="judge"}` p95
3. Then p95 ≤ 5000ms

### TC-OBS-010: SLO availability ≥ 99.0%
- **Type**: Observability
- **Covers**: NFR-OBS-003
- **Priority**: P1
#### Steps
1. Given 1000 запусков
2. When агрегируется `eval.run.failed{reason="internal"}`
3. Then availability ≥ 99.0%

---

## Coverage Matrix

| Требование | Тесты | Покрытие |
|---|---|---|
| FR-001 | TC-001, TC-002 | ✅ |
| FR-002 | TC-003, TC-004 | ✅ |
| FR-003 | TC-005, TC-006 | ✅ |
| FR-004 | TC-007, TC-008 | ✅ |
| FR-005 | TC-009, TC-010 | ✅ |
| FR-006 | TC-011, TC-012 | ✅ |
| FR-007 | TC-013, TC-014 | ✅ |
| FR-008 | TC-015, TC-016 | ✅ |
| FR-009 | TC-017, TC-018 | ✅ |
| FR-010 | TC-019 | ✅ |
| FR-011 | TC-020 | ✅ |
| FR-012 | TC-003, TC-021, TC-022 | ✅ |
| FR-013 | TC-023, TC-024 | ✅ |
| FR-014 | TC-025 | ✅ |
| FR-015 | TC-026, TC-027 | ✅ |
| NFR-001 | TC-028, TC-029 | ✅ |
| NFR-002 | TC-030, TC-031 | ✅ |
| NFR-003 | TC-032, TC-033 | ✅ |
| NFR-004 | TC-034, TC-035 | ✅ |
| NFR-005 | TC-036, TC-037 | ✅ |
| NFR-006 | TC-038, TC-039 | ✅ |
| NFR-007 | TC-040, TC-041 | ✅ |
| NFR-008 | TC-006, TC-042, TC-043 | ✅ |
| NFR-009 | TC-044, TC-045 | ✅ |
| NFR-010 | TC-046, TC-047 | ✅ |
| NFR-SEC-001 | TC-SEC-001, TC-SEC-001b | ✅ |
| NFR-SEC-002 | TC-019, TC-SEC-002, TC-SEC-002b | ✅ |
| NFR-SEC-003 | TC-020, TC-SEC-003 | ✅ |
| NFR-SEC-004 | TC-023, TC-024, TC-SEC-004 | ✅ |
| NFR-SEC-005 | TC-013, TC-014, TC-SEC-005, TC-SEC-005b | ✅ |
| NFR-OBS-001..005 | TC-OBS-001..010 | ✅ |

## TM Coverage

| TM | Тесты | Покрытие |
|---|---|---|
| TM-01 | TC-020, TC-SEC-003 | ✅ |
| TM-02 | TC-019, TC-SEC-001, TC-SEC-002 | ✅ |
| TM-03 | TC-023, TC-024, TC-SEC-004 | ✅ |
| TM-04 | TC-008 | ✅ |
| TM-05 | TC-001, TC-002, TC-003 | ✅ |
| TM-06 | TC-SEC-001 | ✅ |
| TM-07 | TC-006, TC-030, TC-042 | ✅ |
| TM-08 | TC-SEC-001 | ✅ |
| TM-09 | TC-013, TC-SEC-005 | ✅ |
| TM-10 | TC-SEC-005, TC-SEC-005b | ✅ |
| TM-11 | TC-019, TC-SEC-002b, TC-OBS-004 | ✅ |
| TM-12 | TC-044 (CI pip-audit) | ⚠️ partial (добавить pip-audit в CI) |
| TM-13 | TC-009, TC-010 | ✅ |
| TM-14 | TC-SEC-001, TC-SEC-001b | ✅ |
| TM-15 | TC-034 | ✅ |

## Priority Summary

| Priority | Кол-во | Тесты |
|---|---|---|
| P0 | 24 | TC-001, 002, 003, 005, 007, 008, 009, 010, 011, 017, 019, 020, 023, 028, 030, 036, 044, SEC-001, SEC-001b, SEC-002, SEC-002b, SEC-003, SEC-004, SEC-005, SEC-005b, OBS-001..006, OBS-008, OBS-009 |
| P1 | 20 | TC-004, 006, 012, 013, 014, 015, 018, 021, 022, 024, 025, 026, 029, 031, 032, 033, 034, 037, 038, 039, 042, 043, 045, 046, OBS-005, OBS-010 |
| P2 | 6 | TC-016, 027, 035, 040, 041, 047 |