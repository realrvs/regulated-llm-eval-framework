# Contributing Guide

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/regulated-llm-eval-framework.git`
3. Create a feature branch: `git checkout -b feature/my-feature`
4. Make changes and commit
5. Push to your fork: `git push origin feature/my-feature`
6. Open a Pull Request

## Development Setup

```bash
git clone https://github.com/realrvs/regulated-llm-eval-framework.git
cd regulated-llm-eval-framework

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
pytest -q

# With coverage
pytest --cov=src/regulated_eval --cov-report=term-missing

# Target coverage: ≥ 80% for judges, metrics, ab, datasets
```

## Code Style

```bash
# Lint
ruff check .

# Format
ruff format .

# Type checking
mypy src/regulated_eval
```

All checks must pass before PR merge.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cli): add calibrate command
fix(pipeline): handle empty results
docs: update PRD
test(security): add hash-chain tests
ci: add GitHub Actions workflows
```

Types: `feat`, `fix`, `docs`, `test`, `ci`, `refactor`, `chore`

## Pull Request Checklist

- [ ] Tests pass (`pytest -q`)
- [ ] Coverage ≥ 80% for changed modules
- [ ] `ruff check` and `ruff format` clean
- [ ] `mypy` passes
- [ ] Commit message follows Conventional Commits
- [ ] Updated documentation if API changed
- [ ] For security changes: updated `threat-model.md` and added `TM Ref` in tests

## Security Contributions

For security-related changes:

1. Update `threat-model/threat-model.md` with new threat analysis
2. Add test with `TM Ref` in docstring
3. Update `docs/152fz.md` if 152-FZ compliance affected
4. No secrets in code or tests

## Questions?

Open an issue or use GitHub Discussions.
