# Case Study — Оценка LLM для налогового чат-бота

## Context

Продуктовая команда запускает LLM-чат-бот для МСБ-предпринимателей. Бот отвечает на вопросы по УСН, НДС, взносам, декларациям. Domain — regulated (налоги, бухгалтерия).

### Гипотеза

Использование YandexGPT с кастомным judge prompt даст hallucination_rate < 10% и citation_accuracy > 90% на golden set из 150 вопросов.

## Методология

### Dataset

- **tax_qa_v1** — 150 вопросов по УСН/НДС/взносам
- Semver: `0.1.0`
- Content hash: SHA-256 от JSONL
- Categories: `tax`, `accounting`, `legal`
- Difficulties: `easy`, `medium`, `hard`
- Expert validation: ≥ 80% (2 эксперта на record)

### Pipeline

```
load → redact PII → generate (YandexGPT) → judge → metrics → report
```

### Judge

- Модель: YandexGPT (та же, что generator — LLM-as-a-judge)
- Prompt: v1 (score 1-5, hallucination, wrong_citation, incorrect_refusal)
- Calibration: Cohen's kappa ≥ 0.6 против 50 экспертных аннотаций

### Metrics

- `hallucination_rate` — доля галлюцинаций
- `citation_accuracy` — точность цитирования НК РФ
- `refusal_correctness` — корректность отказов
- `factual_consistency` — фактическая согласованность

## Результаты

### Калибровка

```
Calibration status: PASS
Cohen's kappa: 0.72 [95% CI 0.61-0.83]
Agreement rate: 78%
Threshold: 0.6
```

Judge показал **хорошее** согласие с экспертами. Рекомендаций нет.

### Метрики (run #abc123)

| Метрика | Значение | Target | Статус |
|---------|----------|--------|--------|
| hallucination_rate | 8.2% | < 10% | ✅ |
| citation_accuracy | 91.3% | > 90% | ✅ |
| refusal_correctness | 96.7% | > 95% | ✅ |
| factual_consistency | 87.5% | — | — |
| judge.parse_error.rate | 3.1% | < 5% | ✅ |

### A/B-тест: промпт v1 vs v2

```
Model A mean score: 3.42 (n=150)
Model B mean score: 3.58 (n=150)
Delta (B-A): +0.16
95% CI: [0.02, 0.30]
P-value: 0.028
Cohen's d: +0.21
Significant: true
Winner: B
```

Промпт v2 дал **статистически значимое** улучшение (+0.16, p=0.028), но эффект **малый** (Cohen's d=0.21). Рекомендация: принять v2, продолжить итерации.

### Delta-отчёт: v1 vs v2

```
Delta vs run abc123:
  Hallucination rate: -2.1%
  Citation accuracy: +1.8%
```

### Observability

- `eval.run.duration` p95: 245s (SLO ≤ 300s) ✅
- `llm.request.duration{role=judge}` p95: 3200ms (SLO ≤ 5000ms) ✅
- PII redacted: 12 fields (ИНН×8, СНИЛС×4)
- Injection blocked: 0 случаев
- Foreign provider: 0 случаев

## Выводы

1. **Релиз можно** — все метрики в target, калибровка PASS.
2. **Промпт v2 лучше v1** — статистически значимое улучшение.
3. **PII-redaction работает** — 12 полей удалено до отправки в LLM.
4. **SLO соблюдены** — p95 latencies в target.
5. **Reproducibility** — replay прошёл с tolerance 1%.

## Next Steps

- [ ] Расширить calibration dataset до 100 records
- [ ] Добавить GigaChat в A/B-тест
- [ ] Настроить Grafana-дашборд для SLO-мониторинга
- [ ] Добавить human-in-the-loop UI для экспертов
