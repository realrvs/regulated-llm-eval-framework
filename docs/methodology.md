# Methodology — Методология оценки LLM

## Overview

Методология определяет, как считаются метрики качества, как проводится калибровка judge, как интерпретируются A/B-тесты.

## 1. LLM-as-a-Judge

### Prompt

Judge получает:
- Вопрос из golden set
- Reference answer (ответ эксперта)
- Model answer (ответ LLM-провайдера)
- Citations (список статей НК РФ из reference)

Judge оценивает по 4 критериям:
1. **Factual Accuracy** — правильно ли ответ решает вопрос?
2. **Citation Accuracy** — корректны ли ссылки на НК РФ?
3. **Hallucination** — не выдуманы ли факты/статьи/числа?
4. **Refusal Correctness** — корректен ли отказ, если он был?

### Output

```json
{
  "score": 4,
  "hallucination": false,
  "wrong_citation": false,
  "incorrect_refusal": false,
  "rationale": "..."
}
```

### Repair-retry

Если JSON невалиден — retry с repair-prompt (max 2 попытки). После — `judge_status: "parse_error"`.

## 2. Калибровка (Cohen's Kappa)

### Процедура

1. Загружаем calibration dataset (экспертные аннотации).
2. Запускаем judge на calibration records.
3. Считаем Cohen's kappa между judge и экспертами.
4. Строим 95% CI (bootstrap, 1000 итераций).
5. Сравниваем с threshold (по умолчанию 0.6).

### Интерпретация

| Kappa | Согласие | Рекомендация |
|-------|----------|--------------|
| < 0.20 | Poor | Переписать judge prompt, добавить few-shot |
| 0.20–0.39 | Fair | Добавить calibration data |
| 0.40–0.59 | Moderate | Принять с оговоркой |
| 0.60–0.79 | Good | ✅ Pass |
| 0.80–1.00 | Excellent | ✅ Pass |

### Exit criteria

- `kappa ≥ threshold` → PASS
- `kappa < threshold` → FAIL + рекомендации (переписать prompt, добавить data, escalate)

## 3. Метрики

### hallucination_rate

```
hallucination_rate = count(hallucination=True) / total_judge_results
```

- Считается для всех records с `judge_status == "ok"`
- Агрегируется по category, difficulty, model

### citation_accuracy

```
citation_accuracy = count(citation_correct) / total_judge_results
```

- `citation_correct` = true если score ≥ 3 И wrong_citation == false
- Агрегируется по category, model

### refusal_correctness

```
refusal_correctness = count(incorrect_refusal=False) / total_judge_results
```

- Только для records, где reference_answer содержит refusal
- Целевое значение: ≥ 0.95

### factual_consistency

```
factual_consistency = count(score ≥ 3) / total_judge_results
```

- Бинарная: ответ "good" или "poor"
- Агрегируется по category, difficulty

## 4. A/B-тесты

### Статистика

- **Wilcoxon signed-rank test** — непараметрический тест для парных выборок
- **Bootstrap CI** — 1000 итераций, 95% confidence interval
- **Cohen's d** — размер эффекта

### Интерпретация

| p-value | |delta| | Результат |
|---------|---------|-----------|
| ≥ 0.05 | — | `not_significant` |
| < 0.05 | < 0.2 | `small_effect` |
| < 0.05 | 0.2–0.5 | `medium_effect` |
| < 0.05 | > 0.5 | `large_effect` |

### Winner

- `winner = "A"` если `delta < 0` и `significant` (higher_is_better = true)
- `winner = "B"` если `delta > 0` и `significant`
- `winner = "none"` если `not_significant`

## 5. Reproducibility (Replay)

### Процедура

1. Загружаем manifest предыдущего run.
2. Запускаем pipeline с теми же параметрами (dataset_version, seed, model).
3. Сравниваем metrics с tolerance (по умолчанию 1%).

### Exit criteria

- `|delta| ≤ tolerance` для всех метрик → `reproducible = true`
- Иначе → `reproducible = false`

> **Примечание:** replay может не пройти, если LLM-провайдер возвращает разные ответы при одинаковом seed (temperature > 0).

## 6. Observability Contract

### SLO

| Сигнал | Метрика | Target |
|--------|---------|--------|
| Eval run p95 | `eval.run.duration` | ≤ 300s (150 вопросов) |
| Judge p95 | `llm.request.duration{role=judge}` | ≤ 5000ms |
| Availability | — | 99.0% |

### Spans

- `eval.run` — весь pipeline
- `judge.evaluate` — один вызов judge
- `adapter.call` — один вызов LLM-провайдера

### Audit-логи

- `security.pii.redacted` — PII было удалено
- `injection.suspected` — обнаружена инъекция
- `judge.conflict.resolved` — конфликт judge vs эксперт
- `ab.test.completed` — A/B тест завершён
- `provider.foreign.allowed` — foreign provider использован
