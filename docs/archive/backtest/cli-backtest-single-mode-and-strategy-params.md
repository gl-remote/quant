# CLI backtest 缺少显式单次回测模式和固定参数覆盖入口

> 类型：CLI 功能缺口 / 实验复现能力
> 状态：已验证
> 发现日期：2026-06-27
> 修复提交 hash：96f2869
> 发现分支：experiment/low-validation-cost-r2-bollinger-retest
> 关联实验：[`low-validation-cost-r2-bollinger-retest`](../strategy-research/2026-06-27-low-validation-cost/low-validation-cost-r2-bollinger-retest.md)
> 相关代码：[`workspace/cli/commands/backtest.py`](../../../workspace/cli/commands/backtest.py)、[`workspace/cli/workflows/backtests_run.py`](../../../workspace/cli/workflows/backtests_run.py)

## 背景

在 `low-validation-cost-r2-bollinger-retest` 实验中，需要对同一策略做固定参数对照：

```text
stop_widen_multiplier = 1.0 / 1.2 / 1.5
```

期望通过 CLI 直接表达：

```text
uv run python main.py backtest \
  --env backtest \
  --engine vnpy \
  --mode single \
  --strategy ma \
  --symbol DCE.m2601 \
  --strategy-params '{"sma_short":5}'
```

但当前 CLI 无法直接做到这件事。

## 已确认现状

### 1. 没有显式 `single` 模式

当前 `backtest` 命令的 `--mode` 只支持：

```text
search / walk-forward
```

见 [`backtest.py`](../../../workspace/cli/commands/backtest.py)。

实际存在“单次回测”能力，但入口是：

```text
--mode search --no-search
```

其含义是：先进入 `run_vnpy_search`，再在 workflow 内因 `--no-search` 降级到 `_run_single_backtest`。

也就是说：

```text
单次回测能力存在，但入口语义隐藏在 search 模式下，不直观。
```

### 2. 没有 CLI 级策略参数覆盖入口

当前 `backtest` 命令没有类似以下参数：

```text
--strategy-params '{...}'
--strategy-params-file path/to/params.json
--param key=value
```

workflow 内部策略参数来自：

```text
ConfigManager.get_strategy_config(strategy_name)
```

再通过 `_strategy_params()` 过滤得到。

因此临时实验参数只能通过：

1. 修改配置文件；
2. 新建临时配置覆盖文件并传 `--config`；
3. 或绕过 CLI，直接在 Python 中调用 `VnpyBacktestEngine`。

本次 r2 实验采用了第 3 种方式，导致命令行复现性较差。

## 影响

1. 固定参数实验不易通过单条命令复现；
2. workbench 中记录的实验结果需要贴 Python 调用方式，而不是标准 CLI；
3. 对短期策略研究不友好，因为每轮都需要快速比较少量固定参数，不适合进入 Optuna 搜索；
4. `--no-search` 已经实现单次回测，但用户不容易从 `--mode search` 理解这是单次实验入口；
5. 临时参数覆盖如果依赖改配置文件，容易污染长期配置或引入未提交本地状态。

## 最小复现方向

运行：

```text
uv run python main.py backtest \
  --env backtest \
  --strategy ma \
  --symbol DCE.m2601 \
  --mode single
```

当前会失败，因为 `single` 不是合法 mode。

运行：

```text
uv run python main.py backtest \
  --env backtest \
  --strategy ma \
  --symbol DCE.m2601 \
  --no-search \
  --strategy-params '{"sma_short":5}'
```

当前会失败，因为没有 `--strategy-params` 参数。

## 建议实现

### 方案 A：最小改动

保留现有 workflow 结构，只增强 CLI：

1. `--mode` 增加 `single`；
2. `--mode single` 内部路由到现有 `run_vnpy_search`，并强制 `no_search=True`；
3. 新增 `--strategy-params`，接收 JSON object；
4. CLI 将 JSON 参数合并到配置策略参数上，优先级高于配置文件；
5. `VnpySearchRequest` 增加 `strategy_param_overrides: dict[str, Any]`。

参数优先级建议：

```text
--strategy-params > --config / conf.local.toml > conf.toml > 策略 dataclass 默认值
```

### 方案 B：更清晰的结构改动

新增独立请求和 workflow：

```text
VnpySingleRequest
BacktestRunWorkflow.run_vnpy_single(req)
```

`--mode single` 直接路由到 `run_vnpy_single`，不再借道 search。

优点是语义清楚；缺点是改动稍大，需要复用 run lifecycle、持久化和报告构建逻辑。

## 当前处理结果

已实现方案 A：

1. `backtest --mode` 增加 `single`；
2. `--mode single` 复用现有 `run_vnpy_search` 路径，并强制 `no_search=True`；
3. 新增 `--strategy-params`，接收 JSON object；
4. CLI JSON 参数合并覆盖配置策略参数；
5. `VnpySearchRequest` 增加 `strategy_param_overrides`；
6. `walk-forward` 和 `tqsdk` 路径暂不支持 `--strategy-params`，会给出清晰错误。

验证命令：

```text
uv run python main.py backtest \
  --env backtest \
  --engine vnpy \
  --mode single \
  --strategy ma \
  --symbol DCE.m2601 \
  --strategy-params '{"sma_short":5,"sma_long":20}'
```

验证结果：

```text
回测完成: 1/1 成功
报告构建成功
```

补充验证：

```text
ruff check workspace/cli/commands/backtest.py workspace/cli/workflows/backtests_run.py workspace/tests/cli/test_commands_backtest_routing.py
uv run pytest workspace/tests/cli/test_commands_backtest_routing.py --tb=short
```

结果：

```text
All checks passed
18 passed
```
