# Proposal: Regulated LLM Eval Framework

## Why

LLM-продукты в regulated-доменах (налоги, бухгалтерия, право) несут высокий риск: галлюцинация в ответе про налоговый вычет или цитирование несуществующей статьи НК РФ приводит к финансовым потерям клиента и регуляторным последствиям. Продуктовые команды в финтехе/B2B SaaS для МСБ (в т.ч. «Моё Дело») вынуждены запускать LLM-фичи без системной оценки качества, полагаясь на демо и субъективные проверки. Это приводит к:
- релизам с непредсказуемым уровнем галлюцинаций;
- отсутствию трассируемости «промпт → качество → бизнес-метрика»;
- невозможности сравнивать модели/промпты объективно (YandexGPT vs GigaChat vs OpenAI);
- риску нарушения 152-ФЗ при передаче PII в LLM без контроля.

Существующие eval-фреймворки (Ragas, DeepEval, Promptfoo) не покрывают:
- **калибровку LLM-as-a-judge** против экспертов-людей (Cohen's kappa) как обязательный шаг;
- **regulated-специфику** (citation accuracy по НК РФ, refusal correctness);
- **российские LLM** (YandexGPT, GigaChat) из коробки;
- **human-in-the-loop** разметку бухгалтерами/юристами с разрешением конфликтов.

**Метрики успеха проекта:**
- Judge-expert agreement (Cohen's kappa) ≥ 0.6 на целевом датасете;
- Снижение hallucination rate на целевом продукте с baseline до ≤ 50% от исходного;
- Quickstart ≤ 5 минут от `pip install` до первого отчёта;
- ≥ 100 валидированных вопросов в golden set v1;
- ≥ 1 публичный A/B-отчёт с bootstrap CI.

## What Changes

- **Новый Python-пакет** `regulated-eval` с CLI (`typer`) и библиотечным API.
- **Модуль datasets**: загрузка, версионирование, валидация golden set (JSONL + Pydantic-схема).
- **Модуль judges**: LLM-as-a-judge с калибровкой (Cohen's kappa), few-shot, chain-of-thought, разрешение конфликтов.
- **Модуль metrics**: factual consistency, citation accuracy, hallucination rate, refusal correctness, judge-expert agreement.
- **Модуль human_loop**: Streamlit-интерфейс для экспертной разметки + CLI для разрешения конфликтов.
- **Модуль ab**: bootstrap-доверительные интервалы, p-value, размер эффекта для сравнения промптов/моделей.
- **Модуль adapters**: YandexGPT, GigaChat, OpenAI-совместимые API (с rate-limit и retry).
- **Модуль reports**: генерация Markdown/HTML-отчётов (Jinja2) с метриками, примерами ошибок, трендами.
- **Observability**: OTel-инструментация eval-run и judge-вызовов, экспорт в Collector.
- **PII-redaction**: фильтр перед отправкой в LLM (152-ФЗ), audit-лог redaction.
- **Документация**: README, PRD, methodology.md, case_study.md, quickstart.

## Impact

- **Затронутые capabilities:**
  - `eval-pipeline` (новый) — оркестрация прогонов
  - `judge-service` (новый) — калиброванный LLM-as-a-judge
  - `dataset-management` (новый) — golden set lifecycle
  - `human-annotation` (новый) — экспертная разметка
  - `reporting` (новый) — генерация отчётов
  - `llm-adapters` (новый) — интеграции с провайдерами

- **Затронутые команды:** Product (владелец метрик), AI/ML engineering (адаптеры, judge), Data (golden set), Security/Compliance (152-ФЗ, redaction), DevOps (OTel, CI).

- **Целевые метрики:**
  - Judge-expert kappa ≥ 0.6
  - Hallucination rate reduction ≥ 50% на пилотном продукте
  - Eval-run p95 ≤ 300s на датасете 150 вопросов
  - Judge-call p95 ≤ 5000ms
  - Availability CLI/API ≥ 99.0%

- **Security-профиль:** Регуляторика 152-ФЗ; AI-компоненты: LLM-as-a-judge, RAG-оценка, surface для prompt injection через retrieved docs и через golden set; активы: PII (в вопросах/ответах), golden set (интеллектуальная собственность), экспертные аннотации, API-ключи YandexGPT/GigaChat. Требуется PII-redaction перед LLM, allowlist для retrieved docs, secrets management для API-ключей.

- **Operability-профиль:** Стек OTel + Loki + Prometheus + Grafana. SLO: eval-run p95 ≤ 300s, judge p95 ≤ 5000ms, availability ≥ 99.0%. Уже есть `otel-sdk-python` — используем как базу. Ключевые сигналы: `eval.run.duration`, `llm.request.duration`, `judge.calibration.kappa`, `security.pii.redacted`, `eval.run.failed`.

## Operability Promise

> Как мы узнаем, что фича работает в production?

- **SLO:**
  - `eval.run.duration` p95 ≤ 300s (на golden set 150 вопросов)
  - `llm.request.duration` (judge) p95 ≤ 5000ms
  - `eval.run.failed` rate ≤ 1%
  - Availability CLI ≥ 99.0% (по успешным запускам)

- **Ключевые сигналы:**
  - **RED-метрики:** `eval.run.duration`, `eval.run.failed`, `llm.request.duration{provider,model}`
  - **Бизнес-метрики:** `judge.calibration.kappa`, `hallucination.rate{dataset,model}`, `citation_accuracy{dataset,model}`
  - **Критичные логи:** `security.pii.redacted` (audit), `judge.conflict.resolved`, `ab.test.completed`
  - **Traces:** span `eval.run`, span `judge.evaluate`, span `adapter.call{provider}` с `trace_id` во всех

- **Что НЕ покрыто наблюдаемостью:**
  - Качество самих экспертных аннотаций (только agreement-метрика, не «истина»)
  - Стоимость вызовов LLM в реальном времени (только пост-фактум агрегация токенов)
  - Дрейф качества модели провайдера между версиями (только при явном A/B)
  - Корректность юридической интерпретации эталонных ответов (ответственность эксперта, не системы)