---
name: quant-dev
description: >
  This skill should be used when working with the quant trading system project 
  (Python 3.10+, vnpy + tqsdk + Optuna). It provides project architecture, data flow, 
  symbol format conventions, config hierarchy, and common debug patterns.
  Trigger when: debugging backtest/optimizer/data issues, adding CLI args, fixing 
  type errors, running shell scripts, or understanding how modules connect.
---

# Quant Dev Skill

## Purpose

Provide instant access to the quant project's architecture and conventions so debugging
and feature development contexts are immediately available without re-exploring the codebase.

## When to Use

- Any time working in `/Users/REDACTED_API_KEY/Documents/src/quant/`
- Debugging backtest, optimizer, data, config, or CLI issues
- Adding new CLI arguments or config fields
- Understanding how data flows from CSV through vnpy to SQLite
- Fixing symbol format or vnpy Exchange enumeration errors

## How to Use

Read the relevant reference files from `.memory/` based on the task:

### Architecture & Module Map
Read `.memory/architecture.md` when:
- Need to locate which module handles what responsibility
- First encountering the project or after context reset
- Planning a cross-module change

### Data Flow Debugging
Read `.memory/data-flow.md` when:
- Backtest results not landing in SQLite
- Understanding the CSV → DataFrame → BarData → SQLite pipeline
- Optimizer result persistence questions
- Need to know which tables store what data

### Symbol Format Issues
Read `.memory/symbol-format.md` when:
- Seeing `ValueError: 'xxx' is not a valid Exchange`
- Working with vnpy BarData conversion
- Handling `DCE.m2509` vs `m2509.DCE` format mismatches

### Config Hierarchy
Read `.memory/config-topology.md` when:
- Adding a new CLI argument
- Understanding TOML → Pydantic → CLI override priority
- Need to know which config fields have CLI overrides

### Debug Patterns
Read `.memory/debug-patterns.md` when:
- argparse "unrecognized arguments" errors
- SQLite "no such table" errors
- pyright type checking failures
- Needing testing or database inspection commands

## Key Conventions

1. **Symbol format:** Project uses `EXCHANGE.SYMBOL` (e.g. `DCE.m2509`), vnpy uses `SYMBOL.EXCHANGE` (e.g. `m2509.DCE`). Never re-parse a vnpy-formatted string.

2. **Config override:** CLI args > TOML config > Pydantic defaults. Use `value = cli_arg if cli_arg else config.field` pattern.

3. **Python env:** Uses `quant_trading` conda environment at `/usr/local/Caskroom/miniconda/base/envs/quant_trading/bin/python`.

4. **Testing:** 283 tests via `python -m pytest tests/ -q`. Always run after any code change.

5. **pyright:** Strict mode in pyproject.toml. Third-party imports without stubs use `# pyright: ignore[reportMissingImports]` or `Any` annotation.

6. **Data dir:** CSV files in `.quant_shared_data/csv/`, SQLite in `.quant_shared_data/quant_shared.db`.

## Quick Reference

| Task | Command |
|------|---------|
| Run tests | `python -m pytest tests/ -q` |
| Full-chain test | `bash test-ma.sh` |
| List backtests | `python main.py report --limit 10` |
| View backtest | `python main.py report --id <ID>` |
| Check SQLite | `sqlite3 .quant_shared_data/quant_shared.db ".tables"` |
| lint check | `read_lints` on changed files |
