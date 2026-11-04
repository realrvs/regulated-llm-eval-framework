# ADR-005: Хеш-цепочка аннотаций (собственная реализация)

## Статус
Accepted

## Контекст

NFR-SEC-005 требует целостности экспертных аннотаций: неизменяемый audit-лог (`annotator_id`, `timestamp`, `hash`), защита от подмены. Threat model выявил:
- TM-09 (Risk 9 — Repudiation: эксперт отрицает, что разметил запись);
- TM-10 (Risk 9 — Tampering: подмена аннотации или манифеста).

Аннотации хранятся в JSONL-файлах (`human_loop/annotation_store.py`), версионируются в git. Нужно:
1. Гарантировать, что после сохранения аннотацию нельзя изменить без следа.
2. Дать возможность проверить целостность (`regulated-eval annotations verify`).
3. Не тянуть тяжёлые зависимости (blockchain, append-only DB).

Альтернативы:
1. **Собственная hash-цепочка:** каждая аннотация = `sha256(annotation + annotator_id + timestamp + prev_hash)`, `prev_hash` — хеш предыдущей записи. Просто, дёшево, проверяемо.
2. **Merkle tree:** эффективнее для проверки больших наборов, но сложнее в реализации и понимании.
3. **Append-only log (например, Trillian, immudb):** надёжно, но тяжёлая зависимость и инфраструктура.
4. **Git-хуки + подпись коммитов:** работает, но требует настройки у каждого эксперта, не покрывает случаи без git.
5. **Blockchain:** избыточно, дорого, не для локального CLI.

## Решение

Выбираем **вариант 1: собственная hash-цепочка**:

- `human_loop/annotation_store.py::save(annotation)`:
  - `prev_hash = last_record.hash if exists else "0"*64`,
  - `payload = canonical_json(annotation) + annotator_id + timestamp + prev_hash`,
  - `hash = sha256(payload).hexdigest()`,
  - запись сохраняется в JSONL: `{..., "hash": hash, "prev_hash": prev_hash}`.
- `human_loop/annotation_store.py::verify(chain)`:
  - проходит по цепочке, проверяет `hash == sha256(...)` и `prev_hash == предыдущий.hash`,
  - при расхождении — `annotation.tamper{record.id, expected, actual}` в audit-лог,
  - возвращает `(valid: bool, broken_at: record_id | None)`.
- **CLI:** `regulated-eval annotations verify --path annotations.jsonl` → exit code 0/1.
- **Audit-лог:** `annotation.saved{record.id, hash, annotator.id, trace_id}` и `annotation.tamper{record.id, expected, actual, trace_id}`.
- **При старте прогона:** автоматическая проверка целостности аннотаций; при tamper — прогон падает с `AnnotationTampered`.

**Дополнительно (TM-09, TM-10):**
- `annotator_id` — обязательное поле, не может быть пустым.
- `timestamp` — ISO 8601 UTC, монотонно возрастает (проверка при verify).
- Canonical JSON (sorted keys, no whitespace) — для детерминированности хеша.
- Манифест прогона (`RunManifest`) тоже включает `hash` и `prev_hash` — та же схема, защита от подмены манифеста (TM-10).

## Последствия

**Плюсы:**
- Дёшево, без тяжёлых зависимостей (только `hashlib`).
- Проверяемо (`annotations verify`), прозрачно.
- Покрывает TM-09, TM-10 → NFR-SEC-005.
- Работает локально и в CI.

**Минусы:**
- Hash-цепочка линейна: verify O(n). Для 10k аннотаций — ~1s. Приемлемо.
- При компрометации последней записи можно «обрезать» цепочку и переписать. Митигация: периодическая публикация `latest_hash` в audit-лог (Loki) — независимая копия.
- Не защищает от компрометации всей цепочки (злоумышленник с доступом к файлу может переписать всё). Митигация: v2 — подпись Ed25519 организационным ключом, публикация хеша в внешний audit-лог.

**Риски:**
- Эксперт редактирует аннотацию через файл → tamper. → **Митигация:** `annotations verify` при старте прогона, падение при tamper, alert.
- Потеря файла аннотаций → нельзя восстановить. → **Митигация:** бэкап в git + периодическая публикация `latest_hash` в Loki.
- Canonical JSON — нужно реализовать корректно (sorted keys, ensure_ascii=False, separators). → **Митигация:** unit-тест на canonical-json с эталонным хешем.

**Влияние на наблюдаемость:**
- Audit-логи `annotation.saved{record.id, hash, annotator.id}` и `annotation.tamper{record.id, expected, actual}`.
- Метрика `annotations.verify.result{valid: true|false}` (gauge).
- Алерт `annotation.tamper > 0` — немедленно.

## Альтернативы

| Альтернатива | Отклонена | Причина |
|---|---|---|
| Merkle tree | Да | Сложнее, эффект не оправдан для 10k записей |
| Append-only log (Trillian, immudb) | Да | Тяжёлая инфраструктура для локального CLI |
| Git-хуки + подпись коммитов | Да | Требует настройки у каждого эксперта, не покрывает все случаи |
| Blockchain | Да | Избыточно, дорого |
| Без hash-цепочки (только audit-лог) | Да | Не покрывает TM-10 (tampering) |