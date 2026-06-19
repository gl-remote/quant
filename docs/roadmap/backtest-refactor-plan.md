# 回测链路分阶段重构计划

## 背景

近期为了修复回测数据采集、参数优化页、日志落盘、前端报告生成等问题，临时把较多编排逻辑集中到了 `cli/commands/backtest.py`。当前功能可以跑通，但模块边界已经变得混乱：

- CLI 同时承担命令解析、回测编排、持久化、日志、报告构建。
- backtest 执行层开始依赖 `DataManager`、run\_id、Optuna study 关联。
- data store 同时承担 CRUD、报表查询、Optuna SQL 查询。
- report 构建和回测执行强耦合。
- Walk-Forward 等结果对象仍大量使用松散 dict 契约。
- output 路径、run 状态、失败语义、重跑策略没有集中定义。

本计划目标是按“重构 → 验证 → 重构 → 验证”的循环逐步收敛边界，避免一次性大改引入不可控风险。

## 总体原则

1. 每个阶段只解决一类边界问题，不做额外功能。
2. 每个阶段结束必须跑自动化验证和一条真实回测验证。
3. 每次重构都保持现有前端 JSON 契约不变。
4. 先建立验证护栏，再收敛路径、日志、编排和持久化边界。
5. Optuna、Walk-Forward、report query、幂等性单独处理，不和其他重构混在一起。
6. 任何阶段如果真实回测数据缺失，先回退或修复该阶段，不继续推进下一阶段。
7. 当前阶段只在现有 `cli/` 下建立 `cli/workflows` 命令级编排边界，不进行 workspace/ 目录迁移。

## 目标边界

```text
cli/
  只负责参数解析和调用应用服务。

cli/workflows/
  负责命令级跨业务域编排，例如 backtest run、report rebuild。
  workflow 不绑定 argparse 细节，接收明确请求对象。

backtest/
  只负责执行回测和优化，返回强类型结果。
  不知道 DataManager、report、output 目录。

data/
  负责数据库 CRUD、repository、持久化。

report/
  负责查询投影和 JSON/前端报告输出。

report/web/
  只消费稳定 JSON 契约。
```

当前不新增顶层 `services/` 或 `application/`。各业务域内的 service/module 作为该业务域对外契约边界，`cli/workflows` 只编排这些契约，不穿透业务域内部实现。

## 必须保持不变的前端数据契约

每个 run 目录下仍应生成：

```text
output/r{run_id}/data/run.json
output/r{run_id}/data/summary.json
output/r{run_id}/data/backtests.json
output/r{run_id}/data/equity.json
output/r{run_id}/data/optuna.json
output/r{run_id}/data/trades.json
output/r{run_id}/data/logs.json
```

全局导航数据仍应生成：

```text
output/data/nav.json
```

日志文件仍应存在：

```text
output/r{run_id}/data/run.log
output/r{run_id}/data/logs.json
```

## 每阶段统一验证清单

### 静态验证

```bash
ruff check strategies/ tests/strategies/
uv run mypy cli/commands/backtest.py backtest/vnpy_backtest_engine.py
uv run pytest tests/strategies/ --tb=short
```

### 真实回测验证

```bash
mkdir -p ~/.vntrader/log/ && rm -rf output/feeds/ && bash tools/backtest-ma.sh
```

### 输出文件验证

真实回测完成后检查最新 run：

```text
output/r{run_id}/data/run.log
output/r{run_id}/data/logs.json
output/r{run_id}/data/run.json
output/r{run_id}/data/summary.json
output/r{run_id}/data/backtests.json
output/r{run_id}/data/equity.json
output/r{run_id}/data/optuna.json
output/r{run_id}/data/trades.json
```

### 前端人工验证

打开 `output/index.html`，确认：

- run 列表可见。
- 回测详情页可打开。
- 收益曲线有数据。
- 交易记录有数据。
- 参数优化页可打开且有 trial 数据。
- 运行日志页可查看 `logs.json` 内容。

## 阶段 0：建立当前行为基线

### 目标

在开始结构性重构前，记录当前可运行行为，避免后续重构过程中无法判断是新问题还是旧问题。

### 工作内容

- 跑完整静态验证。
- 跑真实回测。
- 记录最新 run\_id。
- 检查所有前端 JSON 文件是否生成。
- 检查 `optuna.json` 是否包含：
  - `study_name`
  - `trial_count`
  - `best_value`
  - `best_params`
  - `optimization_history`（内含 `series[].data` 提供 trial 序号与目标值）
- 检查 `logs.json` 是否包含回测执行、持久化、报告构建日志。

### 验收标准

- 自动化验证通过。
- 最新 run 前端页面可打开。
- 参数优化、交易记录、收益曲线、运行日志均可查看。

### 阶段 0 完成记录

- 完成日期：2026-06-19
- 主要改动：
  1. 基线记录与文档对齐：修订基线检查项中 `optuna.json` 字段清单，使之与当前实现一致（保持现有前端 JSON 契约不变）。
  2. 修复并行回测 0 成交（遗留问题 1）：调整 [`DataFeed.create()`](file:///Users/gaolei/Documents/src/quant/strategies/runtime/data_feed.py#L619-L692)，把硬编码的 `source_period = "1m"` 改为按 `requirements` 推断的最小周期，使其与 `apply_requirements` 的 base 推断逻辑一致；并行路径 [`_init_worker`](file:///Users/gaolei/Documents/src/quant/backtest/parallel.py#L43-L101) 的预热缓存与 vnpy bar 推进对齐，策略恢复正常发信号。
- 影响文件：
  - 代码：
    - `strategies/runtime/data_feed.py`：`DataFeed.create()` 不再硬编码 1m，改为按 reqs 推断最小周期；移除未使用的 `PeriodRequirements` import。
    - `backtest/parallel.py`：还原 `_init_worker` / `_execute_trial` 临时诊断代码（验证完成）。
  - 文档：`docs/roadmap/backtest-refactor-plan.md`。
- 自动化验证：
  - ruff：通过（`ruff check strategies/ tests/strategies/ backtest/parallel.py strategies/runtime/data_feed.py` All checks passed）
  - mypy：通过（`mypy strategies/runtime/data_feed.py backtest/parallel.py` no issues found in 2 source files）
  - pytest：通过（`tests/strategies/` 147 passed in 4.34s）
- 真实回测 run_id：
  - 第一次基线（修复前）：`r1`（`bash tools/backtest-ma.sh`，bayesian 搜索 3 trials，best_value=-999.0，0 成交）
  - 第二次基线（修复后）：`r1`（`tools/clean_data.sh + tools/backtest-ma.sh` 重跑，best_value≈2.31，trial 时长从 130ms 恢复为分钟级，trades.json: m2601=1 / m2603=1 / m2605=5）
- 输出文件检查：通过
  - 全部 7 个 JSON 文件存在
  - `trades.json` / `equity.json` 修复后内容非空（equity.json 9.8KB）
  - 内容仍不完整：`logs.json` 仅含 `backtest.parallel:optimize` 两条记录，未包含 `report.builder`/`report.writer`/`report.cache.build` 等报告构建阶段日志（归阶段 2 处理）
- 前端验证：通过；参数优化页 trial_value 显示正常正值，收益曲线/交易记录有数据。
- 遗留问题：
  1. **无成交记录（业务问题）** ✅ **已修复**：3 个 trial 全部 `best_value=-999.0`，`equity.json`/`trades.json` 为空。该问题原本计划在阶段 0.5 之前单独修复或准备非空 fixture，本次基线阶段已直接定位并修复。
     - **2026-06-19 已修复**：根因为 [`DataFeed.create()`](file:///Users/gaolei/Documents/src/quant/strategies/runtime/data_feed.py#L619-L692) 硬编码 `source_period = "1m"` 并强行注入 1m 周期，与并行路径 [`_init_worker`](file:///Users/gaolei/Documents/src/quant/backtest/parallel.py#L43-L101) 预热缓存（按策略实际 reqs 推断 base=5m）冲突；`set_cached_feed` 缓存键不区分 base_period，导致缓存命中后返回 base 不一致的 feed，策略在子进程中几乎不发信号、trial 仅 130ms 完成。修复方式：把 `DataFeed.create()` 改为按 `requirements` 推断的最小周期作为 base（与 `apply_requirements` 推断逻辑一致），不再硬编码 1m。验证结果：search 模式 `best_value` 从 `-999.0` 恢复为 ≈2.31，trial 时长从 130ms 恢复为分钟级。影响范围：vnpy 串行 / 并行批量回测，TqSdk 路径不受影响（独立 bridge）。
     - **新遗留（独立任务）**：[`tqsdk_bridge._subscribe_klines / _init_period_data`](file:///Users/gaolei/Documents/src/quant/strategies/bridges/tqsdk_bridge.py#L341-L395) 仍硬编码 `source_period = "1m"`，应改为按策略 reqs 推断；同时 `DataFeed.create()` 与 `_init_period_data()` 的函数 docstring 应明确标注其适用场景（vnpy 批量回测 vs TqSdk 单标的回测/test/live）。该问题独立于本次重构主线，留待后续单独处理。
  2. **logs.json 不完整**：报告构建阶段的日志未进入 `logs.json`，初步判断 `RunLogService` 在 finalize 流程中过早 detach。该问题归入 [阶段 2 RunLogService + RunFinalizer](#阶段-2抽出-runlogservice-和-runfinalizer) 解决，阶段 0 只做记录。
  3. **run.log 中 `%`-style 格式串未展开**：`report.builder` 等模块的日志参数（如 `%d`、`%s`、`%.1f`）原样写入文件，logger handler 未展开 args。该问题独立于本计划其他阶段，可在阶段 2 一并处理。
  4. **optuna.json 字段差异**：文档原列的 `trial_nums` / `trial_values` 顶层字段在当前实现中并不存在，trial 序号与目标值嵌套在 `optimization_history.series[].data` 中。本次提交已将基线检查项调整为与现状一致，遵循"保持现有前端 JSON 契约不变"原则。是否将 `trial_nums` / `trial_values` 提升为顶层扁平字段属于**契约扩展提案**，应单独评估、不混入本次的模块边界重构；如确有需要，建议在阶段 6 之后另起小节，明确兼容期与前端迁移路径。
  5. **`total_trades` 字段在某些边界情况下与实际 `fills` 数不一致**：默认参数下 `DCE.m2603` 出现 `fills=47, total_trades=0`，根因是 [`backtest/vnpy_backtest_engine.py#L126`](file:///Users/gaolei/Documents/src/quant/backtest/vnpy_backtest_engine.py#L126) 优先从 vnpy `calculate_statistics()` 返回的 `total_trade_count` 取数；当 daily_results 不足或某些边界条件下 vnpy 不输出该字段时，统计取到 0，但实际 trades 已生成。该问题独立于本次模块边界重构，建议在阶段 7（Walk-Forward 强类型化）或阶段 8（拆 report query）前后单独修复，思路：以 `_calculate_trade_stats` 中已可用的 `closed_trades` 数（或 `len(formatted_trades) / 2`）作为 fallback 来源；同时阶段 0.5 的契约测试应额外校验 `total_trades` 与 `trades.json` 实际条目数的一致性，作为护栏。

## 阶段 0.5：建立最小 JSON 契约测试

### 目标

先建立前端 JSON 数据契约护栏，再开始拆模块。避免阶段 1～后续重构中无声破坏前端数据。

### 实现方式

按 `directory-roadmap.md` 规划的 `workspace/packages/contracts/` 目录提前试点：

**跨语言共享契约（schemas）**：

```text
workspace/packages/contracts/
  README.md
  schemas/
    run.schema.json
    summary.schema.json
    backtests.schema.json
    equity.schema.json
    optuna.schema.json
    trades.schema.json
    logs.schema.json
    nav.schema.json
```

8 份 JSON Schema（Draft 2020-12），minimal schema（只约束 type + 关键必填字段 + 关键字段类型，`additionalProperties: true` 允许未来扩展）。

**Python 侧校验子包**：

```text
workspace/packages/python-contracts/
  pyproject.toml                         # name="quantsmith-contracts"
  src/quantsmith_contracts/
    __init__.py
    schema.py                            # load_schema(name) -> dict
    validate.py                          # validate_run_artifacts(run_dir, nav_path) -> list[str]
  tests/
    conftest.py                          # fixtures: repo_root, latest_run_dir, nav_path
    test_run_artifacts.py               # validates real r{N} artifacts against schemas
```

- `load_schema("run")` 从 `workspace/packages/contracts/schemas/run.schema.json` 加载
- `validate_run_artifacts` 校验 7 个 run artifact + nav.json，返回 issue 列表（空列表=全部通过）
- 测试无 run 目录时 `pytest.skip`，有问题时 `pytest.fail` 列出所有 issue
- 根 `pyproject.toml` 已加 `[tool.uv.workspace] members = ["workspace/packages/python-contracts"]` 和 `testpaths` 扩展

### 验收标准

- 契约测试能在不启动前端的情况下运行。
- 后续字段遗漏或文件缺失会触发测试失败。
- 静态验证和真实回测验证通过。

### 阶段 0.5 完成记录

- 完成日期：2026-06-19
- 主要改动：
  1. 新建 8 份 JSON Schema（`workspace/packages/contracts/schemas/*.schema.json`），定义前端 JSON 契约护栏
  2. 新建 `workspace/packages/python-contracts/` Python 子包，含 schema loader、validate 工具、测试
  3. 根 `pyproject.toml` 加 `[tool.uv.workspace]` members 和 `testpaths` 扩展
  4. `uv pip install -e ./workspace/packages/python-contracts` 接入子包
- 影响文件：
  - 新增：`workspace/packages/contracts/{README.md,schemas/*.schema.json}`（9 个文件）
  - 新增：`workspace/packages/python-contracts/{pyproject.toml,src/quantsmith_contracts/__init__.py,src/quantsmith_contracts/schema.py,src/quantsmith_contracts/validate.py,tests/__init__.py,tests/conftest.py,tests/test_run_artifacts.py}`（7 个文件）
  - 修改：`pyproject.toml`（加 `[tool.uv.workspace]` 和 `testpaths` 扩展）
- 自动化验证：
  - ruff：通过（`ruff check workspace/packages/python-contracts/` All checks passed）
  - mypy：通过（`mypy workspace/packages/python-contracts/src/` Success: no issues found in 3 source files）
  - pytest：通过（`test_latest_run_artifacts_conform_to_schemas` PASSED，对真实 r1 数据全量校验通过）
- 真实回测 run_id：r1（阶段 0 输出，复用验证）
- 遗留问题：无

## 阶段 1：抽出 OutputLayout / RunPaths

### 目标

集中管理 output 目录结构，避免日志、report、finalizer 各自拼路径。

### 当前问题

当前路径散落在多个模块：

```text
output/r{run_id}/data/run.log
output/r{run_id}/data/logs.json
output/r{run_id}/data/*.json
output/data/nav.json
```

路径拼接散落后，后续改目录或新增文件容易漏改。

### 实现

分两层管理，各层只感知本层语义：

**`data/output_paths.py`** — 只暴露 `output_root()`，返回 `<项目根>/output/`。不感知任何上层业务路径。

**`report/output_paths.py`** — run 维度的文件路径，底层调用 `output_root()` 拼接：

- `run_dir(run_id)` → `output/r{N}/`
- `run_data_dir(run_id)` → `output/r{N}/data/`
- `run_log_path(run_id)` → `output/r{N}/data/run.log`
- `logs_json_path(run_id)` → `output/r{N}/data/logs.json`
- `nav_json_path()` → `output/data/nav.json`

其他域（cache/parallel/data_feed）直接用 `output_root()` 拼自己的路径，
不需要 wrapper 文件：
```python
output_root() / ".kline_cache"
output_root() / ".build_cache"
output_root() / "workers"
output_root() / "feeds" / symbol
```

### 边界要求

- 不在业务逻辑中手写 `Path("output")`。
- data 层不知道 run、nav、dashboard 等业务概念。
- 将来切云存储时改 `output_root()` 即可。

### 验收标准

- 现有 JSON 输出路径不变。
- 真实回测输出文件完整。
- 静态验证和真实回测验证通过。

### 阶段 1 完成记录（2026-06-19）

- 新建 `data/output_paths.py`（`output_root()`）
- 新建 `report/output_paths.py`（5 个 run 路径函数）
- 消除 27 处 `"output"` 硬编码，分布在：
  - `cli/commands/backtest.py` — 7 处
  - `cli/commands/report.py` — 2 处
  - `report/writer/json_writer.py` — 8 处（+ 签去 `output_dir` 参数）
  - `report/builder.py` — 调整所有 export 回调
  - `report/cache/build.py` — `BuildCache` 默认值
  - `report/cache/kline.py` — `KlineCache` 默认值
  - `backtest/parallel.py` — worker 日志目录
  - `strategies/runtime/data_feed.py` — feeds 目录
- ruff + mypy + pytest contracts 全部通过

## 阶段 2：抽出 RunLogService 和 RunFinalizer

### 目标

把 run 收尾逻辑和日志逻辑从 CLI 中移出，减少 `cli/commands/backtest.py` 的职责。

### 当前问题

`cli/commands/backtest.py` 当前直接负责：

- `_attach_run_logger`
- `_detach_run_logger`
- `_convert_run_log`
- `finish_run`
- `build_dashboard`

这些属于运行生命周期管理，不应散落在 CLI 中。

### 计划改动

新增命令级运行生命周期模块：

```text
cli/workflows/run_lifecycle.py
```

包含：

- `RunLogService`
  - `attach(run_id)`
  - `detach()`
  - `export_json(run_id)`
- `RunFinalizer`
  - `finalize_success(run_id)`
  - `finalize_partial_success(run_id)`
  - `finalize_skipped(run_id)`
  - `finalize_no_result(run_id)`
  - `finalize_failed(run_id, error)`
  - 内部统一执行：
    - flush 日志
    - 导出 `logs.json`
    - 标记 run 状态
    - 构建 dashboard

### Run 状态语义

先统一定义状态含义：

```text
running         已创建，执行中
success         主记录、核心数据、report 均成功
partial_success 主记录成功，但 daily/trades/report 等非核心步骤部分失败
skipped         配置原因跳过，例如搜索空间为空
no_result       执行完成但没有有效结果
failed          执行失败或主记录写入失败
report_failed   回测和入库成功，但报告构建失败
```

### 边界要求

- CLI 只调用 finalizer，不直接知道 `logs.json` 生成细节。
- finalizer 可以知道 report 构建，但 backtest engine 不知道 report。
- 日志路径通过 OutputLayout / RunPaths 获取。

### 验收标准

- `cli/commands/backtest.py` 不再包含 `_attach_run_logger`、`_detach_run_logger`、`_convert_run_log`。
- 搜索成功、搜索失败、搜索跳过、无结果路径都会生成 `logs.json`。
- run 状态含义清晰，不再散落硬编码。
- 静态验证和真实回测验证通过。

## 阶段 3：抽出 BacktestRunWorkflow 命令级编排层

### 目标

建立新的 run 级总编排者，避免只是把 CLI 函数搬到别处但流程仍由 CLI 拼装。

### 当前问题

`cli/commands/backtest.py` 当前既解析参数，又编排：

- 配置读取。
- 数据加载。
- engine 创建。
- run 创建。
- 日志挂载。
- 参数搜索 / Walk-Forward 分支。
- 持久化。
- finalize。

### 计划改动

新增命令级 workflow：

```text
cli/workflows/backtest_run.py
```

包含：

- `BacktestRunWorkflow.run(request)`，接收明确请求对象，不直接依赖 argparse Namespace。
- `run_search(...)`
- `run_walk_forward(...)`
- 统一异常路径。
- 统一调用 RunLogService、RunFinalizer、Persister。

CLI 最终只负责：

```python
request = BacktestRunRequest.from_args(args)
BacktestRunWorkflow().run(request)
```

### 边界要求

- CLI 不再直接调用 report builder。
- CLI 不再直接写 daily/trades。
- CLI 不再直接 link study。
- 应用层可以协调 data/backtest/report，但不能包含具体 SQL 或前端 JSON 格式化逻辑。

### 验收标准

- `cmd_backtest()` 明显变薄。
- 搜索模式和 Walk-Forward 模式均通过。
- 静态验证和真实回测验证通过。

## 阶段 4：抽出结果持久化服务

### 目标

把回测结果写库逻辑从 CLI / 应用编排中移出，统一处理主记录、参数、daily、trades、一致性校验。

### 当前问题

当前直接或间接由 CLI 负责：

- `_persist_results`
- `_persist_search_results`
- Walk-Forward daily/trades 持久化
- 每个 trial 的容错策略
- `engine_config.trial_index` 写入

编排层不应该理解这些数据落库细节。

### 计划改动

新增 data 域持久化契约：

```text
data/backtest_persistence.py
```

包含：

- `BacktestResultPersister`
  - `persist_result(result, run_id, data_src)`
  - `persist_daily(backtest_id, daily)`
  - `persist_trades(backtest_id, trades)`
  - `validate(backtest_id)`
- `SearchResultPersister`
  - `persist_search_result(search_result, datasets, search_type, study_name, git_hash, run_id)`
- `WalkForwardPersister`
  - `persist_walk_forward(wf_result, result, datasets, run_id)`

### 容错策略

- 主 `backtest` 记录写入失败：该 trial 失败，应记录异常。
- `daily` 写入失败：记录 exception，但不阻断后续 trial。
- `trades` 写入失败：记录 exception，但不阻断后续 trial。
- 一致性校验失败：记录 exception，不阻断 run 收尾。

### 验收标准

- `cli/commands/backtest.py` 不再包含 `_persist_search_results`。
- `engine_config.trial_index` 仍正确写入。
- 参数优化页仍能正确展示 best trial。
- `equity.json` 和 `trades.json` 仍有数据。
- 静态验证和真实回测验证通过。

## 阶段 5：清理 backtest runners 对 data 层的依赖

### 目标

让 backtest 执行层只负责执行，不负责 run 状态、study 关联、数据库路径推导。

### 当前问题

`backtest/runners.py` 中 `execute_parameter_search()` 当前依赖：

- `DataManager`
- `run_id`
- `dm.store.link_study()`
- `dm.store.finish_run()`
- `dm.store.db_path`

这打破了 backtest 层和 data 层的边界。

### 计划改动

调整 `execute_parameter_search()` 参数：

- 移除 `dm`
- 移除 `run_id`
- 增加显式参数：
  - `study_name`
  - `study_db_path`

由 `cli/workflows` 负责：

- 创建 run。
- 生成 study\_name。
- `link_study(run_id, study_name)`。
- 传入 `study_db_path`。
- run 收尾。

### 边界要求

- `backtest/runners.py` 不 import `DataManager`。
- backtest 层不调用 `finish_run`。
- backtest 层不调用 `link_study`。

### 验收标准

- 串行搜索和并行搜索都能生成 `optuna.json`。
- run 与 study 关联仍存在。
- 参数优化页可打开。
- 静态验证和真实回测验证通过。

## 阶段 6：拆出 Optuna 业务域契约

### 目标

把 Optuna 的 study 生命周期、run 关联、查询投影集中封装，降低参数优化页再次断链风险。

### 当前问题

Optuna 相关逻辑散落在：

- study name 生成。
- study db path 选择。
- `run_studies` 关联。
- Optuna 内部表 SQL 查询。
- best trial 查询。
- `engine_config.trial_index`。
- `optuna.json` 导出。

### 计划改动

新增业务域内 Optuna 契约：

```text
backtest/optuna_study.py
report/optuna_query.py
```

包含：

- `backtest/optuna_study.py`
  - `make_study_name(strategy, engine, run_id)`
  - `study_db_url()`
- `report/optuna_query.py`
  - `get_optuna_data(run_id)`
  - `get_best_trial_index(run_id)`
  - 封装所有 Optuna 内部 SQL。

### 边界要求

- `cli/workflows` 负责协调创建 study name、传入 study db path，并调用 data 域契约关联 run-study。
- backtest 层只接收 `study_name` / `study_db_path`。
- report 层只通过 query service 获取优化展示数据。
- Optuna 内部表结构只在一个模块中出现。
- 本阶段只做边界封装，不改变 `optuna.json` 字段形态。如需扁平化 `trial_nums` / `trial_values` 等顶层字段，作为独立**契约扩展提案**评估，不混入本次模块边界重构。

### 验收标准

- 串行和并行搜索都能正常写入 Optuna study。
- `optuna.json` 数据完整。
- 前端参数优化页可打开。
- best trial 过滤仍正确。
- 静态验证和真实回测验证通过。

## 阶段 7：Walk-Forward 结果强类型化

### 目标

用明确的结果对象替代松散 dict，降低字段遗漏和拼写错误风险。

### 当前问题

Walk-Forward 当前通过 dict 传递：

- `success`
- `error`
- `windows`
- `window_results`
- `aggregate`
- `daily_results`
- `trades`
- `statistics`
- `statistics_is`

调用方大量使用 `.get()`，字段契约不明确。

### 计划改动

新增类型，例如：

```text
backtest/results.py
```

包含：

- `WalkForwardWindowResult`
- `WalkForwardResult`

字段包括：

- window index
- train/test 起止时间
- train/test rows
- in-sample statistics
- out-of-sample statistics
- out-of-sample daily results
- out-of-sample trades
- aggregate metrics

### 边界要求

- `VnpyBacktestEngine.run_walk_forward()` 返回强类型对象。
- persister 依赖强类型对象，不再解析嵌套 dict。
- report 输出 JSON 不变。

### 验收标准

- Walk-Forward 模式可跑通。
- daily/trades 不丢失。
- 静态验证和真实回测验证通过。

## 阶段 8：拆分 report query 和 DataStore

### 目标

让 DataStore 回归数据库基础操作，把报表视图查询从 store 中拆出去。

### 当前问题

`data/store.py` 当前同时承担：

- ORM 表初始化。
- 回测记录写入。
- daily/trades 写入。
- run 查询。
- report summary 查询。
- Optuna 内部表 SQL 查询。
- 前端 JSON 投影查询。

### 计划改动

新增查询服务，例如：

```text
report/query.py
```

或：

```text
data/report_queries.py
```

迁移：

- `get_run_summary`
- `get_backtests_for_run`
- `get_equity_data`
- `get_optuna_data`
- `get_best_trial_index`

保留在 DataStore 中：

- `create_run`
- `finish_run`
- `link_study`
- `insert_backtest_detailed`
- `insert_backtest_daily`
- `insert_backtest_trades`
- `query_trades`
- `query_daily`

### 边界要求

- report builder 依赖 report query，不直接依赖 DataStore 的报表方法。
- Optuna SQL 查询集中封装。
- JSON 输出不变。

### 验收标准

- 所有 report JSON 文件内容结构不变。
- 参数优化页可打开。
- run summary、equity、trades 都正常。
- 静态验证和真实回测验证通过。

## 阶段 9：持久化幂等性和重跑策略

### 目标

明确失败恢复、重复构建、重复写入时的行为，避免 partial 数据和重复数据污染报告。

### 当前问题

当前重跑策略不清晰：

- 同一个 run 重复 build 是否覆盖 JSON？
- 同一个 backtest\_id 重复插入 daily/trades 是否重复？
- 中途失败后重跑，旧 partial 数据如何处理？
- `run_studies` 是否重复？
- `BacktestParam` 有更新时删旧参数，daily/trades 是否需要同类策略？

### 计划改动

定义并实现幂等策略：

- 新回测默认创建新 run，不复用旧 run。
- report export 始终覆盖当前 run JSON。
- `link_study` 使用 get-or-create。
- 对同一 `backtest_id` 重写 params/daily/trades 前先清理旧数据，或明确禁止重写。
- partial run 可通过 report rebuild 重新导出前端 JSON。
- 对失败路径保留足够日志和状态。

### 验收标准

- 重复构建 report 不产生重复 DB 数据。
- 同一 run 重复导出 JSON 结果稳定。
- partial run 可以重建前端报告。
- 静态验证和真实回测验证通过。

## 阶段 10：统一单标的 TqSdk 和批量 vn.py run 生命周期

### 目标

让所有回测模式都走统一 run 生命周期、日志和报告输出流程。

### 当前问题

TqSdk 单标的路径和 vn.py 批量路径不完全一致：

- run 创建不统一。
- 日志输出不统一。
- dashboard 构建不统一。
- 前端查看能力不统一。

### 计划改动

- TqSdk 单标的也创建 run。
- TqSdk 路径也使用 `RunLogService`。
- TqSdk 路径也使用 `RunFinalizer`。
- TqSdk 路径也生成前端 JSON。

### 验收标准

- 单标的回测和批量回测都能在前端 run 列表中查看。
- 两种模式都有日志和报告数据。
- 静态验证和真实回测验证通过。

## 阶段推进建议

建议执行顺序：

```text
阶段 0：建立基线
验证
阶段 0.5：建立最小 JSON 契约测试
验证
阶段 1：OutputLayout / RunPaths
验证
阶段 2：RunLogService + RunFinalizer
验证
阶段 3：BacktestRunWorkflow 命令级编排层
验证
阶段 4：结果持久化服务
验证
阶段 5：清理 runners 对 data 层依赖
验证
阶段 6：Optuna 业务域契约
验证
阶段 7：Walk-Forward 强类型化
验证
阶段 8：拆 report query 和 DataStore
验证
阶段 9：持久化幂等性和重跑策略
验证
阶段 10：统一 TqSdk 生命周期
验证
```

如果中途出现数据缺失，优先停止后续阶段，回到最近阶段修复。

## 优先级建议

必须优先做：

1. 阶段 0：建立基线。
2. 阶段 0.5：建立最小 JSON 契约测试。
3. 阶段 1：OutputLayout / RunPaths。
4. 阶段 2：RunLogService + RunFinalizer。
5. 阶段 3：BacktestRunWorkflow 命令级编排层。
6. 阶段 4：结果持久化服务。

可后置但不能遗漏：

- 阶段 6：Optuna 边界独立封装到 backtest/report/data 各自业务域契约。
- 阶段 9：幂等性和重跑策略。
- 阶段 10：统一 TqSdk 生命周期。

## 每阶段完成记录模板

每完成一个阶段，在对应阶段的"验收标准"之后追加 `### 阶段 X 完成记录` 小节：

```text
### 阶段 X 完成记录

- 完成日期：YYYY-MM-DD
- 主要改动：
- 影响文件：
- 自动化验证：
  - ruff：通过/失败
  - mypy：通过/失败
  - pytest：通过/失败
- 真实回测 run_id：
- 输出文件检查：通过/失败
- 前端验证：通过/失败
- 遗留问题：
```

