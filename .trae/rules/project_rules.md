# Project Rules

## Environment

- All Python commands: `conda run -n quant_trading <command>`
- Lint: `ruff check strategies/ tests/strategies/` (run directly)
- Tests: `conda run -n quant_trading python -m pytest tests/strategies/ --tb=short`
- Python 3.12

## Principles

- **Modularity**: Reuse in `common`/`strategies.utils`, cross-cutting in `strategies.strategy_aspects`
- **Clean code**: <40 lines/function, no duplicates, no magic numbers, no inline scattered conditionals
- **Types & docs**: Full mypy-compatible type hints, docstrings for public APIs
- **Style**: Imports (stdlib → third-party → internal), line ≤120, double quotes
- **Deliverable**: Pass ruff + mypy, include tests
