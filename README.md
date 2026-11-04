# regulated-llm-eval

> Eval-фреймворк для LLM в regulated-доменах (налоги, бухгалтерия, право).
> Калиброванный LLM-as-a-judge, метрики галлюцинаций и citation accuracy, A/B-тесты промптов, PII-redaction под 152-ФЗ, поддержка YandexGPT и GigaChat.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenSpec v1.x](https://img.shields.io/badge/OpenSpec-v1.x-green.svg)](docs/PRD.md)

---

## Зачем это нужно

LLM-продукты в regulated-доменах несут высокий риск: галлюцинация в ответе про налоговый вычет или цитирование несуществующей статьи НК РФ приводит к финансовым потерям клиента и регуляторным последствиям (152-ФЗ). Продуктовые команды в финтехе/B2B SaaS для МСБ запускают LLM-фичи без системной оценки качества — полагаясь на демо и субъективные проверки.

Существующие eval-фреймворки (Ragas, DeepEval, Promptfoo) не покрывают:
- **калибровку LLM-as-a-judge** против экспертов-людей (Cohen's kappa) как обязательный шаг;
- **regulated-специфику** (citation accuracy по НК РФ, refusal correctness);
- **российские LLM** (YandexGPT, GigaChat) из коробки;
- **human-in-the-loop** разметку бухгалтерами/юристами с разрешением конфликтов;
- **PII-redaction под 152-ФЗ** до отправки в LLM.

`regulated-llm-eval` закрывает эти пробелы.

## Что внутри

| Возможность | Что даёт |
|---|---|
| **Golden set management** | JSONL + Pydantic-схема, semver + content hash, воспроизводимость прогонов |
| **LLM-as-a-judge с калибровкой** | Score 1–5 + бинарные флаги (hallucination, wrong citation, incorrect refusal), Cohen's kappa с CI, repair-retry на невалидный JSON |
| **Метрики** | `hallucination_rate`, `citation_accuracy`, `refusal_correctness`, `factual_consistency`, агрегация по category/difficulty/model |
| **Human-in-the-loop** | Streamlit UI для экспертов, hash-цепочка аннотаций (защита от подмены), CLI для разрешения конфликтов |
| **A/B-тесты** | Bootstrap CI, Wilcoxon, Cohen's d, интерпретация `not_significant` |
| **Адаптеры LLM** | YandexGPT, GigaChat, OpenAI-compatible (с явным opt-in под 152-ФЗ) |
| **PII-redaction** | Presidio + кастомные regex для РФ (ИНН, СНИЛС, паспорт, телефон, адрес), audit-лог без значений |
| **Prompt-injection фильтр** | Allowlist доменов + эвристики для retrieved-документов (RAG) |
| **Observability** | OTel-инструментация (spans, metrics, audit-logs) с redaction-middleware, SLO: eval-run p95 ≤ 300s, judge p95 ≤ 5000ms |
| **Отчёты** | Markdown / HTML с метриками, top-N ошибок, delta между прогонами |
| **CLI + Library API** | Typer CLI и Python API — одинаковый функционал |

## Quickstart (≤ 5 минут)

### 1. Установка

```bash
pip install regulated-eval

# С полным стеком PII (Presidio + spaCy ru):
pip install "regulated-eval[ru-ner]"
```

### 2. API-ключ провайдера

```bash
# YandexGPT (российский, соответствует 152-ФЗ)
export YANDEXGPT_API_KEY="your-key"

# GigaChat (российский, соответствует 152-ФЗ)
export GIGACHAT_API_KEY="your-key"

# OpenAI-compatible — только с явным opt-in (см. раздел 152-ФЗ)
```

### 3. Первый прогон

```bash
# Загрузка sample golden set (20 вопросов по УСН/НДС/взносам)
regulated-eval dataset load --path datasets/tax_qa_v1/sample.jsonl --version 0.1.0

# Прогон через YandexGPT + judge
regulated-eval run \
  --dataset tax_qa_v1@0.1.0 \
  --model yandexgpt \
  --judge-model yandexgpt \
  --report md

# Отчёт: reports/<run_id>.md
```

### 4. Калибровка (обязательно перед публикацией отчёта)

```bash
regulated-eval calibrate \
  --dataset calibration_v1 \
  --judge-model yandexgpt \
  --threshold 0.6
# → PASS (kappa ≥ 0.6) или FAIL + рекомендации
```

### 5. A/B-сравнение промптов

```bash
regulated-eval ab \
  --prompt-a prompts/judge_v1.md \
  --prompt-b prompts/judge_v2.md \
  --dataset tax_qa_v1@0.1.0 \
  --model yandexgpt
```

## Как это связано с продуктом

Этот фреймворк — инструмент для **продуктовой команды**, запускающей LLM-фичи в regulated-домене. Он отвечает на вопросы:

- **«Можно ли релизить?»** → калибровка judge (kappa ≥ 0.6) + `judge.parse_error.rate` ≤ 5% + `hallucination_rate` ниже baseline.
- **«Стало ли лучше?»** → A/B-отчёт с bootstrap CI и p-value, а не «мне кажется».
- **«Не нарушаем ли 152-ФЗ?»** → PII-redaction audit-лог, provider allowlist, тест `TC-SEC-002` с recall ≥ 99%.
- **«Сколько это стоит?»** → `tokens_input`, `tokens_output`, `estimated_cost_rub` в манифесте каждого прогона.
- **«Что если провайдер деградировал?»** → SLO `judge.p95 ≤ 5s`, alert `rate_limit.high`, статус `degraded` в отчёте.

## Архитектура

```mermaid
flowchart LR
    CLI[CLI typer] --> Orch[EvalOrchestrator]
    Lib[Library API] --> Orch
    Orch --> DS[datasets<br/>loader + versioning]
    Orch --> Sec[security<br/>pii_redactor + injection_filter]
    Orch --> Ad[adapters<br/>yandexgpt / gigachat / openai]
    Orch --> J[judges<br/>judge + calibration]
    Orch --> M[metrics<br/>hallucination + citation]
    Orch --> R[reports<br/>markdown + html]
    J --> Sec
    Ad --> Sec
    Orch --> Obs[observability<br/>otel + redaction]
    Human[Streamlit UI] --> J
    Human --> Ann[annotation_store<br/>hash-chain]
    Ann --> Orch
```

**Ключевые точки:**
- **TB-03 (PII redactor → LLM)** — PII редактируется до отправки в провайдера, audit-лог без значений.
- **TB-05 (LLM output → judge)** — Pydantic strict + repair-retry, защита от prototype pollution и DoS.
- **TB-08 (Application → OTel)** — `RedactingSpanProcessor` дропает не-allowlist атрибуты, PII не попадает в телеметрию.

Полная архитектура — в [`design/design.md`](design/design.md), threat model — в [`threat-model/threat-model.md`](threat-model/threat-model.md).

## 152-ФЗ и foreign providers

По умолчанию разрешены **только российские провайдеры** (YandexGPT, GigaChat) — они соответствуют 152-ФЗ. Для OpenAI-compatible требуется **двойной opt-in**:

```bash
regulated-eval run \
  --dataset tax_qa_v1@0.1.0 \
  --model openai_compat \
  --allow-foreign-provider \
  --i-understand-152fz
```

Или через env (для CI, с предупреждением в stderr):

```bash
export REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER=true
export REGULATED_EVAL_ACK_152FZ=true
```

Каждое разрешение фиксируется в audit-логе `provider.foreign.allowed{ack_source}`. Подробнее — в [`docs/152fz.md`](docs/152fz.md).

## Метрики качества

| Метрика | Как считается | Целевое значение |
|---|---|---|
| `judge.calibration.kappa` | Cohen's kappa (judge vs эксперт) | ≥ 0.6 |
| `hallucination_rate` | LLM-judge + экспертный сэмпл | ниже baseline на ≥ 50% |
| `citation_accuracy` | Точное/частичное совпадение + judge | ≥ 0.9 для regulated-домена |
| `refusal_correctness` | Бинарная классификация | ≥ 0.95 |
| `judge.parse_error.rate` | Доля невалидных JSON от judge | ≤ 5% |
| `eval.run.duration` p95 | Histogram | ≤ 300s (150 вопросов) |
| `llm.request.duration{role=judge}` p95 | Histogram | ≤ 5000ms |

Полная методология — в [`docs/methodology.md`](docs/methodology.md).

## Структура репозитория

```
regulated-llm-eval/
├── README.md                    # этот файл
├── proposal.md                  # OpenSpec: why / what / impact
├── context.md                   # Traceability Matrix, принятые ADR
├── specs/eval-pipeline/spec.md  # FR/NFR + Observability Contract
├── design/design.md             # архитектура, потоки, точки инструментирования
├── threat-model/threat-model.md # STRIDE + OWASP LLM, 15 угроз, 9 Trust Boundaries
├── adr/                         # 5 ADR (PII, allowlist, judge, OTel, hash-chain)
├── api/api-contract.yaml        # CLI + Library API + JSON Schema
├── test-specs/eval-pipeline/tests.md  # 64 теста, coverage matrix
├── tasks/tasks.md               # 96 задач, ~191 SP
├── apply/apply.md               # миграции, feature flags, observability verification
├── docs/
│   ├── PRD.md
│   ├── methodology.md
│   ├── case_study.md
│   └── 152fz.md
├── scripts/                     # PowerShell-скрипты для генерации артефактов
├── datasets/
│   ├── tax_qa_v1/
│   └── calibration_v1/
└── src/regulated_eval/          # (реализация — по tasks.md)
```

## Разработка

### Требования

- Python 3.11+
- Git
- (опционально) GitHub CLI для push

### Установка для разработки

```bash
git clone https://github.com/realrvs/regulated-llm-eval-framework.git
cd regulated-llm-eval-framework

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e ".[dev,ru-ner]"
pre-commit install
```

### Тесты

```bash
pytest --cov=regulated_eval --cov-report=term-missing
# Целевое покрытие: ≥ 80% для judges, metrics, ab, datasets
```

### Линтеры

```bash
ruff check .
mypy src/regulated_eval
```

## Roadmap

- [x] OpenSpec pipeline (proposal → specs → design → threat-model → adr → api-contract → test-specs → tasks → apply)
- [ ] Phase 0: Foundation (T-001..T-009)
- [ ] Phase 1: Datasets (T-101..T-105)
- [ ] Phase 2: Adapters (T-201..T-208)
- [ ] Phase 3: Security (T-301..T-306)
- [ ] Phase 4: Judges (T-401..T-407)
- [ ] Phase 5: Metrics (T-501..T-505)
- [ ] Phase 6: Human-in-the-loop (T-601..T-603)
- [ ] Phase 7: A/B (T-701..T-703)
- [ ] Phase 8: Reports (T-801..T-803)
- [ ] Phase 9: Observability (T-901..T-907)
- [ ] Phase 10: Pipeline (T-1001..T-1003)
- [ ] Phase 11: Tests (T-1101..T-1114)
- [ ] Phase 12: CI (T-1201..T-1205)
- [ ] Phase 13: Docs (T-1301..T-1305)
- [ ] Phase 14: Apply (T-1401..T-1403)
- [ ] v1.0.0 release (PyPI)

Полный план — в [`tasks/tasks.md`](tasks/tasks.md).

## Почему OpenSpec

Проект использует [OpenSpec v1.x](https://github.com/realrvs/openspec) — методологию, где каждый артефакт (proposal → specs → design → threat-model → adr → api-contract → test-specs → tasks → apply) создаётся последовательно, с обязательным threat modeling и Observability by Design. Это даёт:

- **Трассируемость:** каждое требование (FR/NFR/NFR-SEC/NFR-OBS) → задача → тест → verify method.
- **Безопасность с первого дня:** threat model до ADR, а не после.
- **Наблюдаемость как артефакт проектирования:** 13 сигналов зафиксированы в spec, проверяются в test-specs, верифицируются в apply.
- **Воспроизводимость:** `context.md` содержит Traceability Matrix, по которой можно восстановить любое решение.

## Contributing

1. Fork → branch → PR.
2. Убедитесь, что `pytest --cov` ≥ 80% и `ruff check` / `mypy` зелёные.
3. Для security-изменений — обновите `threat-model.md` и добавьте тест с `TM Ref`.
4. Для observability-изменений — обновите Observability Contract в `spec.md` и `test-specs`.

## License

MIT — см. [LICENSE](LICENSE).
