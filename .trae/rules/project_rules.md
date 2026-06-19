# Project Rules

## ⚠️ Environment 铁则

本仓库使用 `uv` 管理 Python 环境（`.venv` 在仓库根）。

**任何 Python 命令必须以 `uv run` 开头**，不允许直接调用裸 `python`/`pytest`/`pip`。

- ✅ `uv run python script.py`
- ✅ `uv run pytest tests/ --tb=short`
- ✅ `uv run mypy strategies/`
- ❌ `python script.py`     # 缺前缀，会用错环境
- ❌ `pytest tests/`         # 缺前缀
- ❌ `pip install xxx`       # 不要用 pip，依赖只通过 `pyproject.toml` 声明，再 `uv sync`

例外：`ruff` 是独立 CLI（项目已声明在 dev 组），可直接调用 `ruff check ...`，也可以 `uv run ruff check ...`。

## Setup（新机器一次性）

```bash
brew install ta-lib              # ta-lib 需要本机 C 库
uv sync --all-groups             # 安装项目本体 + 所有 dependency-groups
```

## 常用命令

- Lint: `ruff check strategies/ tests/strategies/`（直接调用）
- Tests: `uv run pytest tests/strategies/ --tb=short`
- 添加依赖: 编辑 `pyproject.toml` 的 `dependencies` 或 `dependency-groups.dev`，再 `uv sync`
- Python 3.12

## Principles

- **Modularity**: Reuse in `common`/`strategies.utils`, cross-cutting in `strategies.strategy_aspects`
- **Clean code**: <40 lines/function, no duplicates, no magic numbers, no inline scattered conditionals
- **Types & docs**: Full mypy-compatible type hints, docstrings for public APIs
- **Style**: Imports (stdlib → third-party → internal), line ≤120, double quotes
- **Deliverable**: Pass ruff + mypy, include tests
