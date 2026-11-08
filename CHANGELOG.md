# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-08

### Added
- **Core Framework**
  - Golden set management (JSONL, Pydantic validation, semver, content hash)
  - LLM-as-a-judge with calibration (Cohen's kappa + bootstrap CI)
  - Metrics: hallucination_rate, citation_accuracy, refusal_correctness, factual_consistency
  - Human-in-the-loop (Streamlit UI, hash-chain annotations)
  - A/B testing (Wilcoxon, bootstrap CI, Cohen's d)
  - Adapters: YandexGPT, GigaChat, OpenAI-compatible (opt-in)
  - PII redaction (Presidio + regex for RU: ИНН, СНИЛС, passport, phone, address)
  - Prompt-injection filter (allowlist + heuristics)
  - OTel instrumentation (spans, metrics, audit-logs) with redaction middleware
  - Markdown/HTML reports with delta comparison
  - CLI + Library API (Typer + Python API)

- **Observability**
  - Spans: `eval.run`, `judge.evaluate`, `adapter.call`
  - Metrics: `eval.run.duration`, `eval.run.failed`, `llm.request.duration`, `judge.calibration.kappa`, `hallucination.rate`, `citation_accuracy`
  - Audit logs: `pii_redacted`, `injection_suspected`, `conflict_resolved`, `ab_test_completed`
  - SLO: eval.run p95 ≤ 300s, judge p95 ≤ 5000ms, availability 99.0%

- **CI/CD**
  - GitHub Actions: lint, test, matrix (ubuntu/macos/windows × py3.11/3.12), docs-check
  - Coverage target: ≥ 80%

- **Documentation**
  - PRD, methodology, case_study, 152fz compliance guide
  - OpenSpec artifacts: proposal, specs, design, threat-model, ADR, API contract, test-specs, tasks, apply
  - Traceability matrix, 15 threat models, 5 ADRs

- **Tests**
  - 211 tests: unit, integration, E2E, performance, observability
  - Security tests: secrets, hash-chain, PII, injection, provider allowlist

### Security
- Default provider allowlist: Russian providers only (YandexGPT, GigaChat)
- Foreign provider double opt-in (`--allow-foreign-provider` + `--i-understand-152fz`)
- PII redaction before LLM submission (recall ≥ 99%)
- Audit logging without PII values
- OTel attribute redaction via `RedactingSpanProcessor`
- Hash-chain annotations for tamper detection
