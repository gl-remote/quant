# Project Rules

## Python Environment

- Python commands (pytest, mypy, etc.): use `conda run -n quant_trading` prefix
- Example: `conda run -n quant_trading python -m pytest tests/`
- The system default Python and `.venv` do NOT have the required dependencies (pandas_ta, tqsdk, etc.)
- Python version: 3.12 (as specified in pyproject.toml)

## Lint & Type Check

- ruff is installed in base conda env, run directly: `ruff check strategies/ tests/strategies/`
- Run tests: `conda run -n quant_trading python -m pytest tests/strategies/ --tb=short`

## Code Style

- Line length: 120 (ruff)
- Quote style: double quotes
- Target Python version: 3.12
