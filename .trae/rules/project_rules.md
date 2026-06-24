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

## 设计文档归档规范（`docs/archive/`）

已完成的设计规格、重构计划归档到 `docs/archive/`。该目录存放**已归档的历史设计记录**，仅供回溯演进过程，**当前代码不保证与其完全一致**。必须遵守以下格式：

### 1. 文件头 metadata

每个文件在标题后紧跟 metadata 块：

```markdown
# 文档标题

> 类型：Design / 已实现设计记录  
> 状态：已实现 / 已完成 / 阶段 X-Y 已完成...  
> 完成日期：YYYY-MM-DD  
> Git 参考：`commit_hash commit_message`

## 正文...
```

- `类型`：已完成设计用 `已实现设计记录`，已废弃用 `历史设计记录`
- `状态`：如实标注，如 `已实现`、`阶段 0-9 已完成，阶段 10 已移出主线`
- `完成日期`：最后一个阶段/功能完成的日期
- `Git 参考`：与本设计最相关的终态 commit（通常是 docs 归档或功能完成 commit）

### 2. 废弃文档标记

如果设计被后续方案取代，在 metadata 后追加红色警告：

```markdown
> ⚠️ **历史文档** — YYYY-MM-DD 起该方案已废弃。
>
> 保留供架构演进记录参考。
```

### 3. 归档时机

- 对应功能/重构已全部完成时即时归档
- 从 `docs/roadmap/` 移至 `docs/archive/`
- 移动前补全 metadata header（roadmap 阶段的文档可能没有）
- 不修改正文内容（保留完整演进记录）
