# PRD — Regulated LLM Eval Framework

## Problem

Продуктовые команды в финтехе, B2B SaaS для МСБ и юридических сервисах запускают LLM-фичи (чат-боты, генерация ответов, RAG) без системной оценки качества. Оценка сводится к демо и субъективным проверкам, что приводит к:

- **галлюцинациям** в ответах про налоговые вычеты, ставки, статьи НК РФ;
- **неверным цитированиям** нормативных актов;
- **утечкам ПИД** (ФИО, ИНН, СНИЛС) в логи и промпты;
- **невозможности доказать** качество перед регулятором или аудитором;
- **отсутствию воспроизводимости** прогонов — результат меняется от запуска к запуску.

Существующие eval-фреймворки (Ragas, DeepEval, Promptfoo) не покрывают:
- калибровку judge против экспертов-людей;
- regulated-специфику (citation accuracy, refusal correctness);
- российские LLM (YandexGPT, GigaChat) из коробки;
- human-in-the-loop разметку с hash-цепочкой;
- PII-redaction под 152-ФЗ.

## Users

| Роль | Задача | Как eval помогает |
|------|--------|-------------------|
| **Продакт** | Решить «можно ли релизить?» | Калибровка judge (kappa ≥ 0.6) + метрики ниже baseline |
| **ML-инженер** | Сравнить промпты/модели | A/B-тесты с bootstrap CI и p-value |
| **Эксперт** (бухгалтер/юрист) | Разметитьgolden set, разрешить конфликты | Streamlit UI + hash-цепочка аннотаций |
| **Security-инженер** | Проверить 152-ФЗ compliance | PII-redaction audit-log, provider allowlist |
| **Data Engineer** | Настроить pipeline и observability | OTel-спаны, SLO-метрики, Grafana-дашборды |

## Scope (v1)

**Включено:**
- Golden set management (JSONL, semver, content hash)
- LLM-as-a-judge с калибровкой (Cohen's kappa + CI)
- Метрики: hallucination_rate, citation_accuracy, refusal_correctness
- Human-in-the-loop (Streamlit UI, hash-chain annotations)
- A/B-тесты (Wilcoxon, bootstrap CI, Cohen's d)
- Адаптеры: YandexGPT, GigaChat, OpenAI-compatible (opt-in)
- PII-redaction (Presidio + regex для РФ)
- Prompt-injection filter
- OTel-инструментация (spans, metrics, audit-logs)
- Markdown/HTML отчёты с delta-сравнением
- CLI + Library API

**Не включено (v1):**
- Web UI (только Streamlit для human-in-the-loop)
- Multi-modal LLM (только text)
- Fine-tuning pipeline
- Real-time eval (batch-only)

## Metrics

| Метрика | Цель | Как измеряется |
|---------|------|----------------|
| `judge.calibration.kappa` | ≥ 0.6 | Cohen's kappa (judge vs эксперт) |
| `hallucination_rate` | Ниже baseline на ≥ 50% | LLM-judge + экспертный сэмпл |
| `citation_accuracy` | ≥ 0.9 | Точное/частичное совпадение + judge |
| `judge.parse_error.rate` | ≤ 5% | Доля невалидных JSON |
| `eval.run.duration` p95 | ≤ 300s | Histogram (150 вопросов) |
| `llm.request.duration{role=judge}` p95 | ≤ 5s | Histogram |

## Success Criteria (v1 release)

1. Все 96 задач из `tasks.md` реализованы
2. ≥ 80% test coverage (pytest --cov)
3. Все CI-пайплайны зелёные (lint, test, matrix, docs)
4. Observability Contract: 13 сигналов верифицированы
5. 152-ФЗ compliance: PII-redaction recall ≥ 99%
6. Документация: README quickstart ≤ 5 минут
