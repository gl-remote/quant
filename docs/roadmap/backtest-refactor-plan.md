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
output_root() / "feeds" / symbol
```
worker 日志路径为 `workers_dir(run_id)`，已在 `report/output_paths.py` 中定义（阶段 2 落地）。

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

## 阶段 2：抽出 RunLogHelper 和 RunFinalizer ✅ 已完成

### 目标

把 run 收尾逻辑和日志逻辑从 CLI 中移出，减少 `cli/commands/backtest.py` 的职责。

同时修复阶段 0 基线发现的三个日志问题。

### 当前问题

`cli/commands/backtest.py` 当前直接负责：

- `_attach_run_logger`
- `_detach_run_logger`
- `_convert_run_log`
- `finish_run`
- `build_dashboard`

这些属于运行生命周期管理，不应散落在 CLI 中。

另外阶段 0 基线记录了三个日志 bug：

1. **logs.json 不完整**：`_convert_run_log` 在 `build_dashboard` 之前调用，report 构建阶段的日志（`report.builder`/`report.writer`/`report.cache.build`）丢失。
2. **`%`-style 格式串未展开**：`report.builder` 等模块使用 `logger.info("→ 导出 %s", name)`，loguru 的 `{}`-style file sink 不展开 `%` 占位符。
3. **并行 worker 日志未采集**：worker 日志写入 `output/workers/worker_{pid}.log`，不进入 `logs.json`，前端看不到。

### 已落地实现

新建命令级运行生命周期模块 `cli/workflows/backtests_lifecycle.py`，包含：

- `RunLogHelper`
  - `attach(run_id)` — 开 file sink → `output/r{run_id}/data/run.log`
  - `detach()` — 关 sink（幂等，重复调用安全）
  - `export_json(run_id)` — 收集 run.log + `r{run_id}/workers/*.log` 合并写入 logs.json
- `RunFinalizer`
  - `finish_success(run_id)` / `finish_skipped(run_id)` / `finish_no_result(run_id)` / `finish_failed(run_id, error)`
  - `_finalize` 内部时序（关键）：
    1. `finish_run`（DB 状态标记，让 build_dashboard 读到最新 status）
    2. `build_dashboard`（report 日志进入 run.log，run.json 写入正确 status）
    3. `detach`（停止写 run.log，避免后续日志污染已生成的 logs.json）
    4. `export_json`（读 run.log + worker 日志 → logs.json）
    5. `write_entry_html`（logs.json 落盘后重写入口 HTML，将其注入 `window.__DATA__` 预加载）

### 实施中发现并修复的额外问题

1. **worker 日志目录归属**：原 `output/workers/` 是全局目录，多 run 并发会混淆。改为 `output/r{run_id}/workers/`，新增 `report.output_paths.workers_dir(run_id)`，`run_id` 经 `run_param_search_parallel` → `ParallelBacktestOptimizer` → `_init_worker` 传递。
2. **`%`-style 残留范围超出预期**：实际有 36 处分布在 `report/`（builder/cache/writer/optimizer）、`cli/commands/backtest.py`、`data/schema.py`，全部改为 `{}`-style。
3. **`run.json` status 始终为 `running`**：最初 `_finalize` 把 `finish_run` 放在 `build_dashboard` 之后，导致 builder 导出 run.json 时读到的仍是旧状态。修复为 `finish_run` 先行。
4. **web 端运行日志空白**：`logs.json` 由 builder 之外生成，而 `build_dashboard` 内部的 `write_entry_html` 用 glob 快照预加载数据，此时 logs.json 尚未落盘 → 前端 `window.__DATA__` 缺失该键 → 显示空白。修复为 finalize 末尾追加一次 `write_entry_html`。

### Run 状态语义

当前 `runs` 表实际使用的 4 种状态：

```text
running       已创建，执行中
success       主记录、核心数据、report 均成功
skipped       配置原因跳过，例如搜索空间为空
no_result     执行完成但没有有效结果
```

失败由异常处理路径通过 `failed` 写入 `backtests` 表（非 runs 表）。

### 边界要求

- CLI 只调用 finalizer，不直接知道 `logs.json` 生成细节。
- finalizer 可以知道 report 构建，但 backtest engine 不知道 report。
- 日志路径通过 output_paths 获取。

### 遗留的设计味道（移交阶段 2.5）

`_finalize` 中出现了**两次 `write_entry_html` 调用**——一次在 `build_dashboard` 内部，一次在 finalize 末尾补打包。这两次调用语义不同（一次是 builder 内部环节，一次是 logs.json 落盘后的补丁），但代码形态相同，容易让人/AI 误读时序。

根因：`build_dashboard` 是「导出数据 + 构建前端 + 打包 HTML」的黑箱组合体，无法在「数据全部就绪后只打包一次」。这是阶段 2.5 拆解 builder 要消除的核心问题，详见阶段 2.5。

### 验收标准（已全部通过）

- ✅ `cli/commands/backtest.py` 不再包含 `_attach_run_logger`、`_detach_run_logger`、`_convert_run_log`。
- ✅ 搜索成功、搜索跳过、无结果路径都会生成 `logs.json`。
- ✅ `logs.json` 包含 report 构建阶段日志（`report.builder`/`report.writer`/`report.cache`）。
- ✅ `logs.json` 包含并行 worker 日志（`r{run_id}/workers/*.log`）。
- ✅ `run.log` / `logs.json` 中 `%`-style 格式串正确展开（全项目 0 残留）。
- ✅ `run.json` status 正确写入 `success`。
- ✅ web 端运行日志面板正常显示（`index.html` 含 `r1/data/logs.json` 预加载）。
- ✅ 静态验证（ruff + mypy）和真实回测验证通过。

### 阶段 2 完成记录

- 完成日期：2026-06-20
- 主要改动：
  - 新建 `cli/workflows/backtests_lifecycle.py`（`RunLogHelper` + `RunFinalizer`）。
  - 从 `cli/commands/backtest.py` 删除 `_attach_run_logger` / `_detach_run_logger` / `_convert_run_log`，改由 lifecycle 类承担。
  - worker 日志目录由全局 `output/workers/` 改为 `output/r{run_id}/workers/`，新增 `report.output_paths.workers_dir`。
  - 全项目 36 处 `%`-style 日志格式串改为 `{}`-style。
  - 修复 `run.json` status 始终为 `running` 的时序 bug、web 端运行日志空白 bug。
- 影响文件：`cli/workflows/backtests_lifecycle.py`、`cli/commands/backtest.py`、`backtest/parallel.py`、`report/output_paths.py`、`report/__init__.py`、`report/builder.py`、`report/cache/build.py`、`report/writer/json_writer.py`、`report/reporter/optimizer.py`、`data/schema.py`。
- 自动化验证：
  - ruff：通过
  - mypy：通过
  - pytest：通过（strategies + contracts，148 passed）
- 真实回测 run_id：1
- 输出文件检查：通过（run.json status=success，logs.json 951 行含 report/worker 日志，0 处 `%`-style 残留）
- 前端验证：通过（index.html 含 `r1/data/logs.json` 预加载）
- 遗留问题：`build_dashboard` 黑箱 + 两次 `write_entry_html` 的设计味道，移交阶段 2.5 根治。

## 阶段 2.5：拆解 build_dashboard 黑箱 ✅ 已完成

### 目标

把 `report.builder.build_all`（即 CLI 中别名 `build_dashboard`）从「导出数据 + 构建前端 + 打包 HTML」的黑箱组合体，拆成三个职责单一、可独立调用的环节，消除阶段 2 遗留的「两次 `write_entry_html`」补丁。

### 当前问题

`build_all(output_dir, run_id, incremental)` 内部串联了三件事：

1. **导出数据 JSON**（run/summary/backtests/equity/kline/optuna/trades/nav）——增量构建，关心数据变更。
2. **构建前端 bundle**（`build_frontend`：npm lint + tsc + vite build）。
3. **打包入口 HTML**（`write_entry_html`：glob `output/r*/data/*.json` 做快照 → 注入 `window.__DATA__`）。

问题在于这三件事的「完成时机」错位：

- 步骤 3 用 glob 快照所有 JSON，但 `logs.json` 由 `RunLogHelper.export_json` 在 builder **之外**生成。
- 因此 builder 跑完时 `logs.json` 还没落盘，步骤 3 的快照漏掉它。
- 阶段 2 的补救是：builder 跑完 → 写 logs.json → **再调一次 `write_entry_html`**。

于是 `_finalize` 里出现两次 `write_entry_html`，形态相同语义不同，是误读时序的根源（参见阶段 2「遗留的设计味道」）。

### 已落地实现

把原 `report/builder.py`（单文件）拆成 `report/builder/` 子包，每个模块职责单一：

```text
report/builder/
  __init__.py        # 导出 build_all/run_data_exports/build_frontend/write_entry_html，re-export write_nav_json
  data_exports.py    # run_data_exports(output_dir, run_id, incremental, dm) → 只导出数据 JSON + 指纹增量检查
  frontend.py        # build_frontend(output_dir) → 只构建前端 bundle（缓存可跳过）
  entry_html.py      # write_entry_html(output_dir) → 只打包入口 HTML（纯快照，调用前数据须就绪）
  orchestrator.py    # build_all(...) 薄封装，按 data_exports → frontend → entry_html 顺序调用
```

`build_all` 保留为薄封装（向后兼容 `cli/commands/report.py` 的手动重建）。`report/__init__.py` 的 `from .builder import build_all, write_nav_json` 经由子包 `__init__` 无缝转发，外部引用零改动。

### finalize 线性化

拆解后，`RunFinalizer._finalize` 改为单调线性、无重复调用：

```python
finish_run(run_id, status)
run_data_exports(output_dir, run_id)   # 导出业务数据 JSON
build_frontend(output_dir)             # 构建前端（增量可跳过）
helper.detach()                        # 停止写 run.log
helper.export_json(run_id)             # run.log + worker 日志 → logs.json
write_entry_html(output_dir)           # 最后一步：此时所有 JSON（含 logs.json）都已就绪，只打包一次
```

每一步只做一件事，时序即字面顺序，不再有「看起来重复但实际不同」的调用。

### 边界要求

- `write_entry_html()` 语义纯粹为「快照打包」，不负责生成任何数据；调用方保证调用前所有 JSON 已就绪。
- `data_exports` 不感知前端，`frontend` 不感知数据内容，`entry_html` 只读文件系统快照。
- 前端数据契约（`window.__DATA__` 的 key 结构、各 JSON schema）保持不变。

### 验收标准（已全部通过）

- ✅ `RunFinalizer._finalize` 中不再出现两次 `write_entry_html`。
- ✅ `build_all` 行为对 `cli/commands/report.py` 保持兼容（手动重建报告仍正常）。
- ✅ `logs.json` 仍被正确注入入口 HTML 预加载。
- ✅ web 端运行日志、各数据页均正常。
- ✅ 静态验证和真实回测验证通过。
- ✅ 额外收益：拆解后构建期日志（「报告构建结束」「入口 HTML 已生成」）不再混入 `logs.json`，日志更干净。

### 阶段 2.5 完成记录

- 完成日期：2026-06-20
- 主要改动：
  - 将 `report/builder.py` 拆为 `report/builder/` 子包（`data_exports` / `frontend` / `entry_html` / `orchestrator`）。
  - `RunFinalizer._finalize` 改为 6 步单调线性流程，消除两次 `write_entry_html`。
  - `finish_failed` 同步改用 `write_entry_html`（异常路径不构建前端）。
- 影响文件：新增 `report/builder/{__init__,data_exports,frontend,entry_html,orchestrator}.py`；删除 `report/builder.py`；修改 `cli/workflows/backtests_lifecycle.py`。
- 自动化验证：ruff 通过 / mypy 通过 / pytest 148 passed。
- 真实回测 run_id：1
- 输出文件检查：通过（run.json status=success，logs.json 959 行含 report/worker 日志且无构建期噪音，0 处 `%`-style 残留）
- 前端验证：通过（index.html 含 `r1/data/logs.json` 预加载）
- 遗留问题：`report/writer/` 单文件子包（仅 `json_writer.py`）可在未来扩展时考虑合并，本阶段不动。

## 阶段 3：抽出 BacktestRunWorkflow 命令级编排层

### 目标

建立新的 run 级总编排者，避免只是把 CLI 函数搬到别处但流程仍由 CLI 拼装。同时把"引擎选择"从隐式推断改为显式开关，让 CLI 参数语义清晰。

### 当前问题

阶段 2 已把日志和收尾逻辑收进 `RunFinalizer`，但 `cli/commands/backtest.py` 仍既解析参数，又编排：

- 配置读取。
- 数据加载。
- engine 创建。
- run 创建。
- 日志挂载（现在通过 `RunLogHelper`，但仍由 CLI 显式 attach/detach）。
- 参数搜索 / Walk-Forward 分支（`_execute_search_mode` / `_execute_walk_forward_mode`）。
- 持久化（`_persist_search_results`）。
- finalize（现在通过 `RunFinalizer`，但 CLI 负责把它传进各分支）。

另外，引擎选择当前由 `cmd_backtest` 通过 `--symbol`/`--pattern` 自动推断（单标走 TqSdk、批量走 vnpy），存在两个问题：

- `--symbol` 同时承载"标的过滤"和"引擎选择"两层语义，调用方难以单独表达"用 vnpy 跑单标的"的意图。
- `--gui` 实际只在 TqSdk 路径下有效，但参数定义里没有约束，其他引擎下静默忽略。

### 计划改动

#### 1. 引擎选择显式化（CLI 接口）

`cli/main.py` 中 `backtest` 子命令调整：

- 新增 `--engine`，`choices=["vnpy", "tqsdk"]`，默认 `vnpy`。
- `--symbol` 与引擎选择**完全解耦**，仅表示标的过滤（与 `--pattern` 互斥的语义保持不变）。
- `--gui` 仅在 `--engine tqsdk` 下生效；TqSdk 路径下不再默认开启 GUI，由用户显式指定 `--gui`。
- 其他 engine 下若传 `--gui`，给 warning 后忽略，不报错。

调用形态示意：

```bash
# 默认 vnpy（即便指定 --symbol 也走 vnpy 单标的批量路径）
python main.py backtest --strategy ma --symbol DCE.m2509

# 显式 vnpy
python main.py backtest --engine vnpy --strategy ma --pattern "DCE\\.m"

# 显式 tqsdk（GUI 不再默认开）
python main.py backtest --engine tqsdk --strategy ma --symbol DCE.m2509 --gui
```

#### 2. 命令级 workflow 下沉

新增：

```text
cli/workflows/backtests_run.py
```

包含：

- `BacktestRunRequest`：明确请求对象，不直接依赖 `argparse.Namespace`，由 `from_args(args)` 构造。
- `BacktestRunWorkflow`：业务编排者，提供两个公开入口：
  - `run_vnpy(request)`：vnpy 批量路径（参数搜索 / Walk-Forward）
  - `run_tqsdk(request)`：TqSdk 单标的路径
- TqSdk 路径只做搬迁，不与 vnpy 路径统一生命周期（统一接入 `RunLogHelper`/`RunFinalizer`/前端 JSON 留到阶段 10）。
- 统一异常路径。
- workflow 自持 `RunLogHelper`、`RunFinalizer`，CLI 不再手动 attach/detach 或传递 finalizer。

**职责边界（commands ↔ workflow）**：

| 职责 | 归属 | 说明 |
|---|---|---|
| `argparse` Namespace → `BacktestRunRequest` | commands | 解耦 CLI 框架 |
| 跨字段参数校验（`--gui` 引擎兼容性、tqsdk 必填） | commands | `argparse` 不能表达的约束 |
| 引擎路由（按 `--engine` 选择 `run_vnpy` / `run_tqsdk`） | commands | 命令级路由，workflow 不感知 engine 字段 |
| 用户交互层友好错误（`ValueError` / warn） | commands | 直接面向用户 |
| 数据加载、引擎初始化、run 生命周期、持久化 | workflow | 业务编排 |

CLI 最终只负责（约 50 行）：

```python
def cmd_backtest(args):
    request = BacktestRunRequest.from_args(args)
    _validate_request(request)
    workflow = BacktestRunWorkflow()
    if request.engine == "vnpy":
        workflow.run_vnpy(request)
    elif request.engine == "tqsdk":
        workflow.run_tqsdk(request)
    else:
        raise ValueError(...)
```

### 边界要求

- CLI 不再直接调用 report builder。
- CLI 不再直接写 daily/trades。
- CLI 不再直接 link study。
- 应用层可以协调 data/backtest/report，但不能包含具体 SQL 或前端 JSON 格式化逻辑。
- 本阶段**不**触碰：
  - `_persist_search_results` 拆分（阶段 4）
  - `engine.set_run_id` / `set_git_hash` 状态注入清理（阶段 5）
  - 串行/并行 engine 创建路径双轨统一（阶段 5）
  - Optuna 边界封装（阶段 6）
  - Walk-Forward 强类型化（阶段 7）
  - TqSdk 路径与 vnpy 路径生命周期统一（阶段 10）
- "待评估任务清单"第 1 条 `tqsdk_bridge` 硬编码 `1m`，本阶段不动，仍归阶段 10。

### 验收标准

- `cmd_backtest()` 明显变薄，仅剩请求构造 + workflow 调用。
- 引擎选择全部由 `--engine` 决定，`--symbol` 不再触发 TqSdk。
- `--gui` 在 `--engine tqsdk` 下生效；其他 engine 下传 `--gui` 给出 warning 但不报错。
- 三条命令行路径均验证通过：
  - `python main.py backtest --strategy ma --pattern "DCE\\.m"`（默认 vnpy 批量，**完整验证**：前端 JSON 契约 + run 维度文件）
  - `python main.py backtest --engine vnpy --strategy ma --symbol DCE.m2509`（vnpy 单标的，**完整验证**：前端 JSON 契约 + run 维度文件）
  - `python main.py backtest --engine tqsdk --strategy ma --symbol DCE.m2509 --gui`（显式 TqSdk + GUI，**仅冒烟验证**：能跑通、写入 `backtests` 表即可，前端 JSON / run 生命周期完整性留到阶段 10 验证）
- 搜索模式和 Walk-Forward 模式均通过。
- 前端 JSON 契约不变（阶段 0.5 契约测试在两条 vnpy 命令产出的 run 上通过）。
- 静态验证（ruff + mypy）和 pytest 通过。

### 阶段 3 完成记录

- 完成日期：2026-06-20
- 主要改动：
  1. **CLI 接口改造**：`cli/main.py` 新增 `--engine choices=[vnpy, tqsdk] default=vnpy`；`--symbol` 与引擎选择完全解耦；`--gui` 帮助文本明确仅 `tqsdk` 生效；其他 engine 下 `--gui` 给 warning 后忽略。
  2. **新增命令级 workflow**：`cli/workflows/backtests_run.py` 提供 `BacktestRunRequest`（dataclass，from_args 构造）和 `BacktestRunWorkflow`（按 `request.engine` 分发到 vnpy 批量 / TqSdk 单标的两条路径）。
  3. **整体搬迁**：原 `cli/commands/backtest.py` 中的 7 个函数（`_run_batch_backtest` / `_run_tq_backtest` / `_persist_tq_backtest_result` / `_tq_backtest_gui_loop` / `_execute_walk_forward_mode` / `_execute_search_mode` / `_persist_search_results` / `_persist_results` / `_prepare_backtest_config` / `get_git_hash` / `_calc_total_days`）整体迁入 workflow，**不改语义**。
  4. **CLI 收敛 + 职责对称**：`cli/commands/backtest.py` 从 793 行 → 27 行（一度只剩 2 行薄壳）→ 64 行（commands 收回应承担的能力，与 export/report/tqsdk 形态对齐）。
     - **commands 层** 承担：argparse → request、跨字段校验（`--gui` 兼容、tqsdk 必填）、引擎路由（`run_vnpy` / `run_tqsdk`）。
     - **workflow 层** 承担：数据加载、engine 初始化、run 生命周期、持久化。
     - workflow 公开接口由原 `run(request)` 拆为 `run_vnpy(request)` + `run_tqsdk(request)`，workflow 不再感知 engine 字段。
  5. **顺手修复 2 处潜在 bug**（详见下方"实施中发现的问题"）。
- 影响文件：
  - 修改：`cli/main.py`、`cli/commands/backtest.py`、`cli/workflows/__init__.py`
  - 新增：`cli/workflows/backtests_run.py`
- 自动化验证：
  - ruff：通过（`ruff check cli/ tests/` All checks passed）
  - mypy：通过（`mypy cli/commands/backtest.py cli/workflows/backtests_run.py` Success: no issues found in 2 source files）
  - pytest：通过（`tests/strategies/` + `workspace/packages/python-contracts/tests/` 148 passed in 6.41s）
- 真实回测 run_id：
  - r1：默认 vnpy 批量 + bayesian 并行（`bash tools/backtest-ma.sh`），best_value≈2.31，trial 时长分钟级，9 个 backtest_id；前端 JSON 7 份齐全。
  - r2：显式 vnpy 单标的 + grid 串行（`--engine vnpy --symbol DCE.m2601 --optimizer grid --trials 2`），2 个 backtest_id（10/11），增量构建跳过前端 vite，data_exports 增量写入 nav/equity/trades/optuna 等。
- TqSdk 冒烟验证：
  - `--engine tqsdk` 缺 `--symbol` → 抛 `ValueError: --engine tqsdk 必须指定 --symbol` ✅
  - `--engine tqsdk` 缺 `--start/--end` → 抛 `ValueError: --engine tqsdk 必须显式指定 --start / --end` ✅
  - 完整 TqSdk 跑通 / 接入 run 生命周期 / 生成前端 JSON 留到阶段 10 验证。
- `--gui` 兼容性验证：
  - `--engine vnpy` + `--gui` → 输出 warning `--gui 仅在 --engine tqsdk 下生效，已忽略当前 --gui 标志` ✅
- 前端 JSON 契约：未触动，r1/r2 都通过阶段 0.5 契约测试（运行时直接打开 `output/index.html` 可见 run 列表、参数优化、收益曲线、交易记录、运行日志均正常）。

### 实施中发现的问题（顺手修复 / 留作遗留）

#### A. 顺手修复（2 处）

1. **TqSdk 路径 `capital=None` 时报告生成 / 入库会崩**
   - 原 `_persist_tq_backtest_result` 中 `f"初始资金: {capital_arg:,.2f}"` 在 `capital_arg=None` 时抛 `TypeError`；`end_balance=capital_arg + total_profit if capital_arg else 0` 当 capital 为 None 时直接写 0，与 `initial_capital=request.capital or bc.initial_capital` 不一致。
   - 修复：在 workflow 中提前算出 `effective_capital = float(request.capital) if request.capital else float(bc.initial_capital)`，统一用于报告字符串、`end_balance`、`initial_capital`，三者一致。
2. **TqSdk 入口必填校验缺失**
   - 原代码假定 `args.symbol` / `args.start` / `args.end` 都已提供；当 TqSdk 用户漏传时会在 `datetime.strptime("", ...)` 处抛不友好的 `ValueError`。
   - 修复：workflow 入口显式抛 `ValueError("--engine tqsdk 必须指定 --symbol")` / `ValueError("--engine tqsdk 必须显式指定 --start / --end")`。

#### B. 已识别但留待后续阶段

1. **`_run_batch_backtest` 旧版的 try/except/finally 变量作用域 bug（已通过搬迁规避）**
   - 原 [`_run_batch_backtest`](file:///Users/gaolei/Documents/src/quant/cli/commands/backtest.py) 中 `run_id` / `finalizer` / `log_helper` 都在 try 块内定义，若 `_prepare_backtest_config` / `_load_datasets` 等前置步骤抛错，except 块引用 `finalizer.finish_failed(run_id, ...)` 会再抛 `UnboundLocalError`。本次搬迁后，前置步骤 `_prepare_backtest_config` / `_load_datasets` 移出 try/except，进入 try 之前已确保 engine、run_id、log_helper、finalizer 都已就绪，从作用域上消除了该 bug。
2. **`_persist_tq_backtest_result` 写入 `engine_config={"type": "tqsdk", "gui": False}` 永远是 False**
   - 原代码硬编码，没有从 args 读取实际 gui 标志。本次搬迁未修（保持搬迁不改语义原则），归阶段 10 处理。
3. **TqSdk 路径数据一致性**：阶段 0 / 阶段 2 已发现 `total_trades` 与 `fills` 不一致问题，搬迁后 vnpy 单标的回测在前端报告中再次复现（示例：bt=10/11，`total_trades=0` 但 `fills=125`），与阶段 7 待评估任务清单第 2 条吻合，仍归阶段 7 前后修复。
4. **ConfigManager / DataManager 在 workflow 构造时即建连**：当前 `BacktestRunWorkflow.__init__` 立即创建 `ConfigManager` 和 `DataManager`。这在 CLI 单次入口下没问题，但若未来被 API / scheduler 复用，可能希望注入而非内置。本阶段未引入抽象（避免过度设计），留待真实需要时再改。
5. **`_persist_search_results` 中 `engine_config["study_db"]` 与 search_type / study_name 仍由本函数手拼**：阶段 4 拆 `SearchResultPersister` 时再统一。

## 阶段 3.5：CLI 分层职责对齐与命令文件解耦

### 背景

阶段 3 完成后，code review 中暴露出三个分层错位问题，本质都是"args 的定义和消费没有放在同一个文件里"造成的认知断层：

#### 问题 1：args 定义在 main，消费在 workflow，commands 只是信使

```text
cli/main.py                         ← p.add_argument("--engine"), p.add_argument("--symbol"), ...
   ↓ args
cli/commands/backtest.py            ← BacktestRunRequest.from_args(args) 仅做透传
   ↓ args
cli/workflows/backtests_run.py      ← getattr(args, "engine"), getattr(args, "symbol"), ...
```

字段在 main 出生、在 workflow 死亡，commands 既看不到字段定义、也看不到字段消费——commands 名义上承担了"参数路由"，但**实际既没翻译、也没校验**，是个空壳。

#### 问题 2：`BacktestRunRequest` 是伪共性

当前 dataclass 字段杂糅了三种互不相关工作流的输入：

| 工作流 | 必需字段 | 不相关字段（None / False） |
|---|---|---|
| vnpy + search | strategy, capital, contract_size, symbol/pattern, optimizer, trials, parallel, workers | gui |
| vnpy + walk-forward | strategy, capital, contract_size, symbol/pattern | optimizer, trials, parallel, workers, gui |
| tqsdk | strategy, **symbol（必需）**, **start（必需）**, **end（必需）**, capital, gui | pattern, optimizer, trials, parallel, mode, contract_size |

它们**唯一共性是"跑回测、写库、可能写报告"**——这是水平复用（lifecycle / helper），不是接口共性。当前一个 dataclass 强行装下所有字段，导致：

- workflow 内部出现 `assert request.symbol is not None` 类型收窄；
- 调用方有歧义（"传了 `gui` 但走 vnpy 时会被忽略"，要看 commands 校验才知道）；
- 阶段 7 给 walk-forward 加窗口参数时，会污染另外两个工作流的 dataclass。

#### 问题 3：`cli/commands/tqsdk.py` 一个文件装两个命令

`cmd_test`（实时数据 + 不下单）与 `cmd_live`（实时数据 + 下单）是两个独立命令，但被合并在同一文件中，违反「一个文件一个命令」原则；同时它们的共性（接 TqApi、桥接策略、跑事件循环）没有抽到 workflow 层，导致后续若要加新的"实时数据驱动"命令（例如纸面跟单）必须复制粘贴。

### 目标

让 args **定义、校验、路由、消费**在同一文件内（commands），workflow 只接收**纯净的业务请求对象**，每个工作流字段最小化、类型自洽。

### 计划改动

#### A. args 定义下沉到 commands（适用于所有命令）

引入 `register(subparsers) -> None` 模式：

```text
cli/commands/{export,test,live,backtest,report}.py
  - register(subparsers): 调用 add_parser + add_argument，把本命令所有 argparse 选项定义在此
  - cmd_xxx(args): 消费 args + 跨字段校验 + 路由 + 构造 *Request + 调 workflow
```

`cli/main.py` 改为：

```python
from cli.commands import backtest, export, live, report, test

def main():
    parser = argparse.ArgumentParser(...)
    sub = parser.add_subparsers(dest="command", title="子命令", required=True)

    backtest.register(sub)
    export.register(sub)
    test.register(sub)
    live.register(sub)
    report.register(sub)

    args = parser.parse_args()
    handlers = {
        "backtest": backtest.cmd_backtest,
        "export":   export.cmd_export,
        "test":     test.cmd_test,
        "live":     live.cmd_live,
        "report":   report.cmd_report,
    }
    handlers[args.command](args)
```

main 不再写一行 `add_argument`。

**范围**：
- `backtest`、`export`、`test`、`live`、`report` 全部命令都迁到 register 模式。
- `report` 仅迁 args 定义下沉，**不**做 Request / workflow 拆分（业务层拆分留给阶段 8）。

#### B. backtest 工作流多入口拆分（消除伪共性）

**workflow 暴露 3 个明确入口**：

```python
class BacktestRunWorkflow:
    def run_vnpy_search(self, req: VnpySearchRequest) -> None: ...
    def run_vnpy_walk_forward(self, req: VnpyWalkForwardRequest) -> None: ...
    def run_tqsdk(self, req: TqsdkRequest) -> None: ...
```

**3 个 dataclass 字段最小化**：

```python
@dataclass(frozen=True)
class VnpySearchRequest:
    strategy: str
    capital: float | None
    contract_size: int | None
    symbol: str | None              # 标的过滤
    pattern: str | None             # 标的过滤
    start: str | None
    end: str | None
    optimizer: str | None
    trials: int | None
    parallel: bool
    workers: int | None

@dataclass(frozen=True)
class VnpyWalkForwardRequest:
    strategy: str
    capital: float | None
    contract_size: int | None
    symbol: str | None
    pattern: str | None
    start: str | None
    end: str | None
    # 阶段 7 在此扩展窗口参数

@dataclass(frozen=True)
class TqsdkRequest:
    strategy: str
    symbol: str                     # 必需，由 commands 校验后传入
    start: str                      # 必需
    end: str                        # 必需
    capital: float | None
    gui: bool
```

**commands 接管完整路由**：

```python
def cmd_backtest(args):
    if args.gui and args.engine != "tqsdk":
        logger.warning("--gui 仅在 --engine tqsdk 下生效，已忽略")

    workflow = BacktestRunWorkflow()
    if args.engine == "vnpy":
        if args.mode == "walk-forward":
            workflow.run_vnpy_walk_forward(_build_vnpy_wf_request(args))
        else:
            workflow.run_vnpy_search(_build_vnpy_search_request(args))
    elif args.engine == "tqsdk":
        _validate_tqsdk_args(args)              # 校验 symbol/start/end 必填
        workflow.run_tqsdk(_build_tqsdk_request(args))
    else:
        raise ValueError(f"未知引擎: {args.engine!r}")
```

workflow 层不再感知 `engine` / `mode` 字段——这两个本就是 CLI 概念，不是业务概念。

#### C. tqsdk.py 拆分为 test.py + live.py

```text
cli/commands/tqsdk.py            （删除）
  ↓
cli/commands/test.py             cmd_test + register
cli/commands/live.py             cmd_live + register
```

#### D. 抽取 `cli/workflows/realtime.py`

`test` 和 `live` 的共性是「连 TqApi → 桥接策略 → 订阅行情 → 跑事件循环」。差异是「策略下不下单」。

```python
# cli/workflows/realtime.py
class TqsdkRealtimeWorkflow:
    def run(self, req: TqsdkRealtimeRequest, bridge_factory) -> None:
        """
        bridge_factory: 由 commands 决定生成 SignalBridge（不下单，test 用）
                        或 LiveBridge（下单，live 用）
        """
```

commands 各自决定使用哪种 bridge 工厂，workflow 不持有"是否下单"开关。这一层让"加新的实时数据驱动命令"只需写新 commands 文件 + 选 bridge，不用改 workflow。

### 边界要求

- 本阶段**不**触碰：
  - 任何业务逻辑（`run_vnpy_search` / `run_vnpy_walk_forward` / `run_tqsdk` 内部仍调用同样的 `_load_datasets` / engine 创建 / persist）
  - 持久化拆分（阶段 4）
  - engine 状态注入清理（阶段 5）
  - report 业务层拆分（阶段 8）
  - TqSdk 接入 run 生命周期（阶段 10）
- workflow 模块**不**直接读 `argparse.Namespace`，所有字段由 commands 翻译为 *Request 后传入。
- commands 不再透传 args 给 workflow；commands 是 args 的最后消费者。

### 落地步骤

按 commit 边界分 3 步：

1. **commit A — args 定义下沉（register 模式）**：所有命令引入 `register(subparsers)`，main 改为调 register；commands 内部仍用旧的 `BacktestRunRequest`，**业务行为零变化**。
2. **commit B — backtest 工作流多入口拆分**：拆 3 个 *Request、workflow 暴露 3 个公开入口、commands 完整接管路由；删除旧 `BacktestRunRequest`。
3. **commit C — tqsdk 命令文件拆分 + realtime workflow**：拆 `tqsdk.py` → `test.py` + `live.py`，新增 `cli/workflows/realtime.py`，commands 各自选 bridge factory。

每步独立 ruff + mypy + pytest 验证，B 步加真实回测验证。

### 验收标准

- `cli/main.py` 不再包含任何 `add_argument` 调用。
- `cli/commands/{backtest,export,test,live,report}.py` 各自包含 `register` 与 `cmd_*`。
- `cli/workflows/backtests_run.py` 暴露 `run_vnpy_search` / `run_vnpy_walk_forward` / `run_tqsdk` 三个入口；不存在 `BacktestRunRequest` 这种伪共性 dataclass。
- `cli/workflows/backtests_run.py` 不直接 import `argparse`，不直接读 `args`。
- `cli/commands/tqsdk.py` 文件不存在；`cli/commands/test.py` + `cli/commands/live.py` 各自存在。
- 三条命令行路径仍通过：
  - `python main.py backtest --strategy ma --pattern "DCE\\.m"`（默认 vnpy 批量）
  - `python main.py backtest --engine vnpy --strategy ma --symbol DCE.m2509`（vnpy 单标的）
  - `python main.py backtest --engine tqsdk --strategy ma --symbol DCE.m2509 --gui`（显式 TqSdk + GUI）
- 前端 JSON 契约不变（阶段 0.5 契约测试通过）。
- 静态验证（ruff + mypy）和 pytest 通过。

### 阶段 3.5 完成记录

**完成日期**: 2026-06-20

**3 个 commit**:

- `a784f1a` — Commit A：args 定义下沉（register 模式）。`cli/main.py` 不再包含任何 `add_argument` 调用，所有命令 subparser 定义由各命令模块的 `register(subparsers)` 负责。
- `f56e530` — Commit B：backtest 工作流多入口拆分。建立 `VnpySearchRequest` / `VnpyWalkForwardRequest` / `TqsdkRequest` 三个字段最小化的 dataclass，`BacktestRunWorkflow` 暴露 `run_vnpy_search` / `run_vnpy_walk_forward` / `run_tqsdk` 三个公开入口。commands 完整接管 argparse → 校验 → 路由 → 构造 request 的全流程，workflow 不再感知 `engine` / `mode` 字段。新增 7 个路由与验证单测。
- `3659e3f` — Commit C：拆 `tqsdk.py` 为 `test.py` + `live.py`，抽取 `cli/workflows/realtime.py`（`TqsdkRealtimeWorkflow` + `TqsdkRealtimeRequest`）。每个命令文件拥有自己的 argparse 定义，所有 Namespace → Request 翻译发生在 commands 层。

**最终分层形态**:

```text
cli/main.py                          ← 子命令注册 + handler 分发（无 add_argument）
  ↓
cli/commands/{backtest,export,test,live,report}.py
                                     ← 自定义 argparse + 跨字段校验 + 路由 + 构造 *Request
  ↓ 纯净 Request 对象
cli/workflows/{backtests_run,realtime,backtests_lifecycle}.py
                                     ← 业务编排，不感知 argparse
```

**关键设计决策**:

1. **依赖方向单向**：commands → workflows，workflows 不反向依赖 commands。
2. **每个 dataclass 字段最小化**：`TqsdkRequest.symbol: str`（非 `str | None`），调用方传入即可直接使用，无需 assert。
3. **report 不动业务层**：report 仅迁 args 下沉（register 模式），不做 Request / workflow 拆分（阶段 8）。
4. **TqSdk 实时工作流不持"是否下单"开关**：`TqsdkRealtimeWorkflow.run()` 接收 `trade` booelan 参数，由 commands 层决定并传入——未来加新命令只需写新 commands + 选参数组合。

**实施中发现的问题**（留给后续阶段）:

- report 命令的 args 定义已下沉，但 `cmd_report` 内部仍直接调 `DataManager`、`format_*_report`——业务编排仍散落在 commands 层，阶段 8 需要类似 backtest 的 Request + Workflow 拆分。
- `_persist_search_results` 中的 `engine_config["study_db"]` 与 search_type/study_name 手拼（阶段 4 + 阶段 6）。
- `engine.set_run_id` / `set_git_hash` 状态注入（阶段 5）。
- `total_trades` 与 `fills` 不一致（阶段 7 待评估任务 #2）。

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

### 边界要求

- 本阶段只处理 vnpy 路径（批量回测、Walk-Forward、并行搜索）的持久化拆分。
- TqSdk 单标的的 `_persist_tq_backtest_result` 本阶段**不动**，与 TqSdk 路径一并留到阶段 10 接入 `BacktestResultPersister`。

### 验收标准

- `cli/commands/backtest.py` 不再包含 `_persist_search_results`。
- `engine_config.trial_index` 仍正确写入。
- 参数优化页仍能正确展示 best trial。
- `equity.json` 和 `trades.json` 仍有数据。
- 静态验证和真实回测验证通过。

## 阶段 5：清理 backtest runners 对 data 层的依赖

### 目标

让 backtest 执行层只负责执行，不负责 run 状态、study 关联、数据库路径推导。同时让 engine 退化为纯执行器，统一串行/并行两条路径的 engine 创建形态。

### 当前问题

`backtest/runners.py` 中 `execute_parameter_search()` 当前依赖：

- `DataManager`
- `run_id`
- `dm.store.link_study()`
- `dm.store.finish_run()`
- `dm.store.db_path`

这打破了 backtest 层和 data 层的边界。

同时 `runners.py` 还面临以下问题：

- **`execute_parameter_search` 参数膨胀**：当前 12 个参数（`engine`, `strategy_name`, `strategy_params`, `capital`, `contract_size`, `datasets`, `n_trials`, `optimizer_cfg`, `cm`, `optimizer_arg`, `git_hash`, `dm`, `run_id`），其中 `cm`, `git_hash`, `dm`, `run_id` 属于编排层关切，不应出现在这里。阶段 5 将这些移除后可减少到 7-8 个。
- **`execute_parameter_search` 与 `execute_walk_forward` 无代码共享**：两者唯一共同点是接收 `engine` + `datasets`，但 search 要自己读配置/拼 study_name/调 optimizer，WF 只是简单调 `engine.run_walk_forward()`。没有共享接口或基类的必要，但当前放在同一个文件里制造了"它们有关系"的错觉。
- **方法名易混淆**：`runners.py` 的 `execute_parameter_search` 是"编排函数"（含配置读取+校验+study 生命周期），而 `optimizer.py` 的 `run_param_search` 是"执行函数"（纯调 optimizer）。名字上 `execute_` vs `run_` 区别不够明显，调用方容易走错入口。

另外，`VnpyBacktestEngine` 当前被当作"长期注入容器"，由调用方手动注入运行期状态：

- `engine.set_run_id(run_id)`
- `engine.set_git_hash(git_hash)`
- 构造时持有 `dm` 引用

这导致串行路径和并行路径形态不一致：

- **串行路径**：CLI 创建 `VnpyBacktestEngine(bc, dm)` → 注入 `run_id`/`git_hash` → 透传给 `execute_parameter_search` / `execute_walk_forward`。
- **并行路径**：worker 子进程内自行 `VnpyBacktestEngine(ctx["backtest_config"], dm=None)`，不接受任何状态注入，CLI 创建的 engine 实例**不**进入并行路径。

阶段 3 已把这些注入和分发动作集中到 workflow 内，但形态本身没改。

### 计划改动

**runners 接口收敛**：调整 `execute_parameter_search()` 参数：

- 移除 `dm`
- 移除 `run_id`
- 增加显式参数：
  - `study_name`
  - `study_db_path`

**engine 退化为纯执行器**：

- 移除 `engine.set_run_id` / `engine.set_git_hash`，改为执行时通过参数显式传入（或在持久化阶段补全 `git_hash` 字段）。
- engine 不再持有 `dm` 引用。
- 串行/并行两条路径下 engine 创建形态统一为 `VnpyBacktestEngine(bc)`（无运行期状态、无 dm）。

**职责回收到 workflow**：由 `cli/workflows` 负责：

- 创建 run。
- 生成 study\_name。
- `link_study(run_id, study_name)`。
- 传入 `study_db_path`。
- run 收尾。
- 把 `git_hash`、`run_id` 在持久化阶段补全到结果对象（不通过 engine 传递）。

### 边界要求

- `backtest/runners.py` 不 import `DataManager`。
- backtest 层不调用 `finish_run`。
- backtest 层不调用 `link_study`。
- `VnpyBacktestEngine` 构造和方法签名不再接受 `run_id` / `git_hash` 等运行期元数据。
- 串行和并行路径下 engine 实例的创建参数形态一致。

### 验收标准

- 串行搜索和并行搜索都能生成 `optuna.json`。
- run 与 study 关联仍存在。
- 参数优化页可打开。
- `engine_config.trial_index` / `git_hash` 仍正确写入到 `backtests` 表。
- `execute_parameter_search` 参数从 12 减至 7-8，不再接收 `dm` / `run_id` / `cm` / `git_hash`。
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

此外，**`OptunaOptimizer` 与 `ParallelBacktestOptimizer` 之间存在两处重复代码**：

1. **`_create_grid_space` 各写一遍**：[`optimizer.py#L143-L162`](file:///Users/gaolei/Documents/src/quant/backtest/optimizer.py#L143-L162) 与 [`parallel.py#L230-L247`](file:///Users/gaolei/Documents/src/quant/backtest/parallel.py#L230-L247) 逻辑完全一样（遍历 search_space → 按 type 生成值列表）。
2. **storage 标准化三份重复**：`sqlite:///` 前缀校验 + `os.path.abspath` + `os.makedirs` 的代码在 `OptunaOptimizer.optimize()`（[L213-L219](file:///Users/gaolei/Documents/src/quant/backtest/optimizer.py#L213-L219)）、`ParallelBacktestOptimizer.optimize()`（[L259-L266](file:///Users/gaolei/Documents/src/quant/backtest/parallel.py#L259-L266)）各写一遍，workbench 路径也可能有第三份。

另外，**`SearchResult` 转换有两处**：

- [`optimizer.py#L349-L356`](file:///Users/gaolei/Documents/src/quant/backtest/optimizer.py#L349-L356) `run_param_search` 内 `OptunaResult` → `SearchResult`
- [`parallel.py#L474-L481`](file:///Users/gaolei/Documents/src/quant/backtest/parallel.py#L474-L481) `run_param_search_parallel` 内同样的转换

转换逻辑几乎一样，但各自独立。

**方法名混淆风险**（与阶段 5 交叉）：

- `optimizer.py::run_param_search`——纯执行函数，接收已拼好的参数，直接调 `OptunaOptimizer`。
- `runners.py::execute_parameter_search`——编排函数，含配置读取、study 生命周期、**再调** `run_param_search`。
- 调用方如果不仔细读签名，可能误走 `run_param_search` 导致缺失 study name / link_study 等步骤。

阶段 6 目标是把"怎么拼 study_name/study_db_path"统一封装后，自然消除两处重复，并让 `execute_parameter_search` 退化成简单的 `optimizer = ...; return optimizer.optimize()` 形态。

### 计划改动

新增业务域内 Optuna 契约：

```text
backtest/optuna_study.py
report/optuna_query.py
```

包含：

- `backtest/optuna_study.py`
  - `make_study_name(strategy, engine, run_id)`
  - `make_study_url(db_path)` — 统一 `sqlite:///` 标准化（替代三份重复代码）
  - `create_grid_space(search_space)` — 从 search_space 配置生成 grid 字典（替代两处重复）
  - `optuna_result_to_search_result(opt_result, study_name)` — 统一 `OptunaResult` → `SearchResult` 转换
  - `get_study(db_path, study_name, sampler, direction)` — 统一 `optuna.create_study` 调用
- `report/optuna_query.py`
  - `get_optuna_data(run_id)`
  - `get_best_trial_index(run_id)`
  - 封装所有 Optuna 内部 SQL。

**`OptunaOptimizer` 与 `ParallelBacktestOptimizer` 重构**：两者都改为通过 `optuna_study.py` 的工具函数获取 grid space 和 study url，消除各自重复的 `_create_grid_space` 和 storage 标准化。不再需要各自维护校验逻辑。

### 边界要求

- `cli/workflows` 负责协调创建 study name、传入 study db path，并调用 data 域契约关联 run-study。
- backtest 层只接收 `study_name` / `study_db_path`。
- report 层只通过 query service 获取优化展示数据。
- Optuna 内部表结构只在一个模块中出现。
- `OptunaOptimizer` 和 `ParallelBacktestOptimizer` 不再各自维护 `_create_grid_space` 和 storage 标准化逻辑，改为引入公用工具函数。
- `SearchResult` 类型保留，但 `OptunaResult` → `SearchResult` 的转换逻辑由 `optuna_result_to_search_result()` 统一处理。
- 本阶段只做边界封装，不改变 `optuna.json` 字段形态。如需扁平化 `trial_nums` / `trial_values` 等顶层字段，作为独立**契约扩展提案**评估，不混入本次模块边界重构。

### 验收标准

- 串行和并行搜索都能正常写入 Optuna study。
- `optuna.json` 数据完整。
- 前端参数优化页可打开。
- best trial 过滤仍正确。
- `_create_grid_space` 和 storage 标准化不再有重复代码。
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

让 DataStore 回归数据库基础操作，把报表视图查询从 store 中拆出去。同时建立统一的 `ReportWorkflow`，让 `cmd_report` 和 `RunFinalizer` 复用同一套报表生成入口，消除当前"相同底层函数、不同编排方式"的双轨局面。

### 设计约束（阶段 3.5 确立的分层规则）

**报表 HTML 生成通过 `ReportWorkflow` 统一入口**：

```text
cmd_report --build          RunFinalizer.finish_success
       │                           │
       └─────────┬─────────────────┘
                 │ ReportBuildRequest
                 ▼
          ReportWorkflow.build()
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
data_exports  frontend  entry_html
```

- `RunFinalizer` 在 finish 序列中调 `ReportWorkflow.build()`（工作流间调用）。
- `cmd_report --build` 也调 `ReportWorkflow.build()`（commands → workflow 单向）。
- `report/builder/orchestrator.py::build_all()` 被 `ReportWorkflow.build()` 替代后可以删除。

**工作流间调用规则**：

| 调用方向 | 允许 | 说明 |
|---|---|---|
| commands → workflows | 是 | 正常路由 |
| workflows → workflows | 是 | 委托子任务（如 `RunFinalizer` → `ReportWorkflow`） |
| workflows → commands | 否 | 依赖反转 |
| workflows → argparse | 否 | 已消除 |

核心判断：workflow 可以委托另一个 workflow 完成子任务，只要被调用方不反向依赖 commands 层。`ReportWorkflow` 只关心"给定 run_id，生成报表"，不关心调用方是 CLI 还是其他 workflow。

**与阶段 3.5 的衔**：

- report 命令的 args 定义已在阶段 3.5 下沉到 `register(subparsers)`。
- 本阶段补齐业务层拆分：`cmd_report` 内部不再直接调 `DataManager` / `format_*_report`，改为构造 `ReportRequest` 后调 `ReportWorkflow` 对应方法。
- 拆 `DataStore` 的 query 方法与建 `ReportWorkflow` 在本阶段一并完成，不分两个阶段。

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

**A. 新增 `ReportWorkflow`**：

```text
cli/workflows/report.py
```

- `ReportWorkflow.build(request: ReportBuildRequest)` — 串联 data_exports → frontend → entry_html
- `ReportWorkflow.get_summary(request)` — 查询 DB + 格式化摘要
- `ReportWorkflow.get_detail(request)` — 查询单条回测详情
- `ReportWorkflow.delete_backtest(request)` — 硬删除回测及关联数据

`cmd_report` 和 `RunFinalizer` 都通过 `ReportWorkflow` 生成报表，消除双轨编排。

**B. 新增查询服务**：

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
- TqSdk 路径也使用 `RunLogHelper`。
- TqSdk 路径也使用 `RunFinalizer`。
- TqSdk 路径也通过阶段 4 的 `BacktestResultPersister` / `WalkForwardPersister` 持久化（`_persist_tq_backtest_result` 整体接入持久化服务）。
- TqSdk 路径也生成前端 JSON。
- 顺带处理"待评估任务清单"第 1 条：修复 [`tqsdk_bridge._subscribe_klines / _init_period_data`](file:///Users/gaolei/Documents/src/quant/strategies/bridges/tqsdk_bridge.py#L341-L395) 硬编码 `source_period = "1m"`，改为按策略 reqs 推断最小周期；同时统一 `DataFeed.create()` 与 `_init_period_data()` 的 docstring，标注各自适用场景（vnpy 批量回测 vs TqSdk 单标的回测/test/live）。

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
阶段 2：RunLogHelper + RunFinalizer
验证
阶段 2.5：拆解 build_dashboard 黑箱
验证
阶段 3：BacktestRunWorkflow 命令级编排层
验证
阶段 3.5：CLI 分层职责对齐与命令文件解耦
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
4. 阶段 2：RunLogHelper + RunFinalizer。
5. 阶段 2.5：拆解 build_dashboard 黑箱。
6. 阶段 3：BacktestRunWorkflow 命令级编排层。
7. 阶段 3.5：CLI 分层职责对齐与命令文件解耦。
8. 阶段 4：结果持久化服务。

可后置但不能遗漏：

- 阶段 6：Optuna 边界独立封装到 backtest/report/data 各自业务域契约。
- 阶段 9：幂等性和重跑策略。
- 阶段 10：统一 TqSdk 生命周期。

## 待评估任务清单（重构完成后统一决策）

以下任务**独立于模块边界重构主线**，已明确不混入当前阶段。待全部重构阶段完成后，再根据实际需求逐条评估"做 / 不做 / 何时做"。

### 真实问题（有明确技术缺陷，建议修）

1. **tqsdk_bridge 硬编码 `source_period = "1m"`**
   - 位置：[`tqsdk_bridge._subscribe_klines / _init_period_data`](file:///Users/gaolei/Documents/src/quant/strategies/bridges/tqsdk_bridge.py#L341-L395)
   - 与阶段 0 已修复的 `DataFeed.create()` 同源（硬编码 1m，应按策略 reqs 推断最小周期），但在 TqSdk 单标的路径上仍未修。
   - 建议落点：**阶段 10（统一 TqSdk 生命周期）**，顺带统一 `DataFeed.create()` 与 `_init_period_data()` 的 docstring，标注各自适用场景（vnpy 批量回测 vs TqSdk 单标的回测/test/live）。

2. **`total_trades` 与实际 `fills` 数不一致**
   - 位置：[`backtest/vnpy_backtest_engine.py#L126`](file:///Users/gaolei/Documents/src/quant/backtest/vnpy_backtest_engine.py#L126)
   - 现象：默认参数下 `DCE.m2603` 出现 `fills=47, total_trades=0`。根因是优先取 vnpy `calculate_statistics()` 的 `total_trade_count`，边界条件下该字段为 0 但实际已有成交。
   - 建议落点：**阶段 7（Walk-Forward 强类型化）前后**。修复思路：以 `_calculate_trade_stats` 的 `closed_trades` 数（或 `len(formatted_trades) / 2`）作为 fallback；同时在阶段 0.5 契约测试中增加 `total_trades` 与 `trades.json` 条目数一致性校验作为护栏。

3. **OptunaCharts.tsx 前端代码质量问题**
   - 位置：[`OptunaCharts.tsx`](file:///Users/gaolei/Documents/src/quant/report/web/src/components/charts/OptunaCharts.tsx#L79-L91)
   - 两处：(a) 第 79/87 行有 `console.log` 调试残留；(b) 第 80-81 行在 render 阶段直接调用 `setXParam`/`setYParam`，是 React 反模式，应改用惰性初始化或 `useEffect`。
   - 建议落点：前端独立小任务，不挂后端重构主线。

### 架构说明（非缺陷，仅记录，默认不动）

4. **optuna.json 双架构并存**
   - `optimization_history` / `param_importances` / `parallel_coordinate` 三个图表是**后端驱动 UI**：后端直接产出完整 ECharts spec，前端透传渲染（数据嵌套在 `series[].data`）。
   - `contour`（等高线）是**前端驱动**：后端只给原始 `trials: [{params, value}]`，前端 `buildContourOption` 按用户选择的 X/Y 参数轴动态组装。原因是等高线需要交互式切换参数，无法预生成所有组合。
   - 这是合理权衡（静态图后端驱动、交互图前端驱动），**非 bug**。
   - 文档早期设想的把 `trial_nums` / `trial_values` 提为顶层扁平字段的"扁平化提案"——本质是把 server-driven-UI 改为前端组装，属架构方向转变，**无实际消费需求，默认不做**。

5. **report/writer 单文件子包**
   - 当前 `report/writer/` 仅含 `json_writer.py`。本阶段不动。
   - 未来若 builder 扩展（如 Python 生成图表内嵌、新增 `chart_writer.py` 等），多文件子包即合理，届时再评估是否合并入 `report/builder/`。


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

