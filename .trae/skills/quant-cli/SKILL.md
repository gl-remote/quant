---
name: "quant-cli"
description: "Provides quant CLI command and validation rules. Invoke when running backtest, report, export, or CLI diagnostics."
---

# Quant CLI

本 skill 记录 quant 项目 CLI 命令、回测、导出、报告和验证规则。

## 基础规则

- Python 命令必须使用 `uv run`。
- 显式单次固定参数回测优先使用 `--mode single`。
- 不要再把单次实验隐藏在 search 模式里。
- `--strategy-params` 接收 JSON object；推荐外层单引号、内部双引号。

## Backtest 命令

参数搜索：

```bash
uv run python main.py backtest --pattern "DCE\\.m" --strategy ma --mode search
```

显式单次固定参数回测：

```bash
uv run python main.py backtest \
  --env backtest \
  --engine vnpy \
  --mode single \
  --strategy ma \
  --symbol DCE.m2601 \
  --strategy-params '{"sma_short":5,"sma_long":20}'
```

旧兼容入口：

```bash
uv run python main.py backtest --mode search --no-search ...
```

## `--strategy-params`

- 接收 JSON object。
- 只支持 vnpy search/single 路径。
- 不支持 walk-forward / tqsdk 路径。
- 非法 JSON 或顶层非 object 应报错。

优先级：

```text
--strategy-params > --config / conf.local.toml > conf.toml > 策略 dataclass 默认值
```

## Report / Export / Database 命令

查看回测列表：

```bash
uv run python main.py report --limit 10
```

查看回测详情：

```bash
uv run python main.py report --id <ID>
```

构建报告：

```bash
uv run python main.py report --build
```

导出数据：

```bash
uv run python main.py export --symbol DCE.m2601 --start 2025-01-01
```

检查数据库：

```bash
sqlite3 project_data/database/quant_shared.db ".tables"
```

## 验证命令

全量常用：

```bash
ruff check workspace/ scripts/ main.py
ruff format --check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

局部 CLI 改动：

```bash
ruff check workspace/cli/commands/backtest.py workspace/cli/workflows/backtests_run.py workspace/tests/cli/test_commands_backtest_routing.py
ruff format --check workspace/cli/commands/backtest.py workspace/cli/workflows/backtests_run.py workspace/tests/cli/test_commands_backtest_routing.py
uv run pytest workspace/tests/cli/test_commands_backtest_routing.py --tb=short
uv run mypy workspace/cli
```

## 常见问题

- `unrecognized arguments`：检查 CLI 参数注册与 workflow request 字段。
- `--mode single` 不存在或 `--strategy-params` 不识别：检查是否在包含 single backtest parameter overrides 的提交之后。
- `--strategy-params` JSON 报错：检查 shell 引号。
- `not a valid Exchange`：检查项目格式 `EXCHANGE.SYMBOL` 与 vnpy 格式 `SYMBOL.EXCHANGE` 是否混用。
- `no such table`：检查 `project_data/database/quant_shared.db` 是否存在、迁移是否完成。
