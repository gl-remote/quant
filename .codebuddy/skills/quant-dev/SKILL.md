---
name: quant-dev
description: >
  This skill should be used when working with the quant trading system project
  (Python, vnpy + tqsdk + Optuna). It provides project architecture, data flow,
  symbol format conventions, config hierarchy, environment rules, and common debug patterns.
  Trigger when: debugging backtest/optimizer/data issues, adding CLI args, fixing
  type errors, running shell scripts, or understanding how modules connect.
---

# Quant Dev Skill

## Purpose

Provide instant access to the quant project's architecture and conventions so debugging
and feature development contexts are immediately available without re-exploring the codebase.

## When to Use

- Any time working in `/Users/gaolei/Documents/src/quant/`
- Debugging backtest, optimizer, data, config, report, or CLI issues
- Adding new CLI arguments or config fields
- Understanding how data flows from CSV through vnpy to SQLite and report JSON
- Fixing symbol format or vnpy Exchange enumeration errors

## Key Conventions

1. **Python env:** This repository uses `uv` and the root `.venv`. All Python commands must start with `uv run`.

2. **Symbol format:** Project uses `EXCHANGE.SYMBOL` (e.g. `DCE.m2601`), vnpy uses `SYMBOL.EXCHANGE` (e.g. `m2601.DCE`). Never re-parse a vnpy-formatted string.

3. **Config override:** CLI args > `workspace/config/conf.local.toml` > `workspace/config/conf.toml` > Pydantic defaults. Use `value = cli_arg if cli_arg else config.field` pattern.

4. **Local data root:** `project_data/` is the only current local artifact root.
   - CSV: `project_data/market_data/csv/`
   - SQLite: `project_data/database/quant_shared.db`
   - Reports: `project_data/reports/`
   - Raw logs: `project_data/logs/`
   - Caches: `project_data/cache/`
   - Profiles: `project_data/profiles/`
   - Coverage: `project_data/coverage/`

5. **Path rules:** Use `workspace/data/output_paths.py` and `workspace/report/output_paths.py`. Do not hardcode local artifact paths.

6. **Typing/lint:** Strict mode in `pyproject.toml`. Third-party imports without stubs use `# pyright: ignore[reportMissingImports]` or `Any` annotation only when needed.

## Quick Reference

| Task | Command |
|------|---------|
| Run tests | `uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short` |
| Lint check | `ruff check workspace/ scripts/ main.py` |
| Type check | `uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report` |
| Full-chain MA backtest | `bash scripts/tools/backtest-ma.sh` |
| List backtests | `uv run python main.py report --limit 10` |
| View backtest | `uv run python main.py report --id <ID>` |
| Build report | `uv run python main.py report --build` |
| Check SQLite | `sqlite3 project_data/database/quant_shared.db ".tables"` |
| Export data | `uv run python main.py export --symbol DCE.m2601 --start 2025-01-01` |
| Backtest | `uv run python main.py backtest --pattern "DCE\\.m" --strategy ma --mode search` |

## Debug Patterns

- `unrecognized arguments`: check CLI argument registration and workflow request models.
- `not a valid Exchange`: check `EXCHANGE.SYMBOL` vs `SYMBOL.EXCHANGE` format mixing.
- `no such table`: check `project_data/database/quant_shared.db` exists and migrations ran.
- If report data is missing: inspect `project_data/reports/runs/rN/data/*.json` and `project_data/reports/data/nav.json`.
