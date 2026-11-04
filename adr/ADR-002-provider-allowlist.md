# ADR-002: Provider allowlist и opt-in для foreign provider

## Статус
Accepted

## Контекст

NFR-SEC-001 требует, чтобы PII не передавался в LLM-провайдеров, не соответствующих 152-ФЗ. Threat model выявил:
- TM-02 (Risk 16, Critical) — PII утекает в LLM;
- TM-06 (Risk 8) — excessive agency адаптеров;
- TM-08 (Risk 10) — spoofing / MITM;
- TM-14 (Risk 12, High) — EoP через `--allow-foreign-provider`: пользователь передаёт флаг без понимания последствий, PII уходит за рубеж.

Нужен механизм, который:
1. По умолчанию разрешает только YandexGPT и GigaChat (российские, соответствуют 152-ФЗ).
2. Для OpenAI-compatible требует **явного** opt-in с предупреждением.
3. Логирует решение в audit-лог (для TM-14).
4. Работает и в CLI, и в library API.

Альтернативы:
1. **Только env-флаг** (`ALLOW_FOREIGN_PROVIDER=true`) — неявно, пользователь может не заметить; плохо для TM-14.
2. **Один CLI-флаг** `--allow-foreign-provider` — явно, но легко передать «на автомате».
3. **Два флага** `--allow-foreign-provider` + `--i-understand-152fz` — явное двойное подтверждение; хорошо для TM-14, но громоздко.
4. **Интерактивное подтверждение** (y/N в CLI) — хорошо для интерактивного режима, ломает CI.
5. **Комбинация: флаг + env + интерактивное подтверждение при TTY** — гибко, но сложно.

## Решение

Выбираем **вариант 3 с элементами варианта 4**:

- **CLI:** для foreign provider требуется **оба** флага: `--allow-foreign-provider` **и** `--i-understand-152fz`. Без них — ошибка `ForeignProviderNotAllowed` с подсказкой.
- **Library API:** параметр `allow_foreign_provider: bool = False` + `acknowledge_152fz: bool = False`; оба должны быть `True`.
- **Env fallback:** `REGULATED_EVAL_ALLOW_FOREIGN_PROVIDER=true` + `REGULATED_EVAL_ACK_152FZ=true` — для CI, но с предупреждением в stderr при использовании env вместо флагов.
- **Интерактивное подтверждение:** если TTY и флаги не заданы, CLI спрашивает `y/N` с явным предупреждением (не работает в CI — там только флаги/env).
- **Audit-лог:** `provider.foreign.allowed{provider, run.id, trace_id, ack_source: "cli_flags"|"env"|"interactive"}` — для TM-14.
- **Allowlist:** `yandexgpt`, `gigachat` — всегда разрешены; `openai_compat` — только при двойном opt-in.

**Дополнительно (TM-06, TM-08):**
- Запрет tool-calling в v1 для всех адаптеров (least-privilege).
- HTTPS + allowlist доменов провайдеров (`api.yandex.cloud`, `gigachat.devices.sberbank.ru`, `api.openai.com` — конфигурируемо).
- Pinning публичного ключа провайдера — где возможно (v1: только для YandexGPT, т.к. есть стабильный CA).

## Последствия

**Плюсы:**
- Явное двойное подтверждение снижает риск случайной утечки PII за рубеж (TM-14).
- Audit-лог фиксирует решение → трассируемость.
- Работает в CI (env fallback) и интерактивно (TTY-подтверждение).
- Покрывает TM-02, TM-06, TM-08, TM-14 → NFR-SEC-001.

**Минусы:**
- Два флага — UX-трение. Митигация: `--help` объясняет, почему; в README — явный раздел «152-ФЗ и foreign providers».
- Env fallback может быть установлен «навсегда» в CI и забыт. Митигация: предупреждение в stderr при каждом запуске с env, audit-лог `ack_source=env` → мониторинг.
- Интерактивное подтверждение ломает скрипты. Митигация: только при TTY; в не-TTY — ошибка с подсказкой про флаги.

**Риски:**
- Пользователь передаёт оба флага «на автомате» → PII уходит за рубеж. → **Митигация:** audit-лог + еженедельный отчёт `foreign_provider.usage` (владельцу продукта); в v2 — approval-workflow.
- Env-переменные утекают в CI-логи. → **Митигация:** маскирование в CI (GitHub Actions secrets), тест TC-SEC-004 (secrets never logged) покрывает и это.

**Влияние на наблюдаемость:**
- Новый audit-лог `provider.foreign.allowed{provider, run.id, trace_id, ack_source}`.
- Метрика `foreign_provider.usage{provider, ack_source}` (для мониторинга).
- Алерт `foreign_provider.usage > threshold` — еженедельно владельцу продукта.

## Альтернативы

| Альтернатива | Отклонена | Причина |
|---|---|---|
| Только env-флаг | Да | Неявно, плохо для TM-14 |
| Один CLI-флаг | Да | Легко передать «на автомате» |
| Только интерактивное подтверждение | Да | Ломает CI |
| Полный запрет foreign provider | Да | Ограничивает сравнение моделей (A/B), нужно для исследования |
| Approval-workflow (v2) | Отложено | Избыточно для v1, добавим в v2 при enterprise-использовании |