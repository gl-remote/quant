# 回测链路分阶段重构计划

## 背景

近期为了修复回测数据采集、参数优化页、日志落盘、前端报告生成等问题，临时把较多编排逻辑集中到了 `cli/commands/backtest.py`。当前功能可以跑通，但模块边界已经变得混乱：

- CLI 同时承担命令解析、回测编排、持久化、日志、报告构建。
- backtest 执行层开始依赖 `DataManager`、run_id、Optuna study 关联。
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

## 目标边界

```text
cli/
  只负责参数解析和调用应用服务。

application/
  负责 run 级编排、生命周期、finalize、跨模块协调。

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
conda run -n quant_trading python -m mypy cli/commands/backtest.py backtest/vnpy_backtest_engine.py
conda run -n quant_trading python -m pytest tests/strategies/ --tb=short
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
- 记录最新 run_id。
- 检查所有前端 JSON 文件是否生成。
- 检查 `optuna.json` 是否包含：
  - `study_name`
  - `trial_count`
  - `trial_nums`
  - `trial_values`
  - `best_params`
- 检查 `logs.json` 是否包含回测执行、持久化、报告构建日志。

### 验收标准

- 自动化验证通过。
- 最新 run 前端页面可打开。
- 参数优化、交易记录、收益曲线、运行日志均可查看。

## 阶段 0.5：建立最小 JSON 契约测试

### 目标

先建立前端 JSON 数据契约护栏，再开始拆模块。避免阶段 1～后续重构中无声破坏前端数据。

### 当前问题

前端依赖的 JSON 文件名和字段结构是隐式契约，Python 侧没有测试保护：

- `run.json`
- `summary.json`
- `backtests.json`
- `equity.json`
- `optuna.json`
- `trades.json`
- `logs.json`
- `nav.json`

### 计划改动

新增最小契约测试，优先验证真实 run 输出或 fixture 输出：

- 文件存在。
- JSON 可解析。
- `logs.json` 是字符串。
- `summary.json` 是数组。
- `backtests.json` 是数组，元素包含 `id/symbol/params/daily`。
- `equity.json` 中每个 symbol 包含 `dates/equity/drawdown`。
- 搜索模式下 `optuna.json` 包含 `study_name/trial_count/trial_nums/trial_values/best_params`。
- `trades.json` 保持前端可消费的分组结构。

### 验收标准

- 契约测试能在不启动前端的情况下运行。
- 后续字段遗漏或文件缺失会触发测试失败。
- 静态验证和真实回测验证通过。

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

### 计划改动

新增路径布局对象，例如：

```text
application/run_paths.py
```

或：

```text
report/output_layout.py
```

包含：

- `run_dir(run_id)`
- `run_data_dir(run_id)`
- `run_log_path(run_id)`
- `logs_json_path(run_id)`
- `global_data_dir()`
- `nav_json_path()`

### 边界要求

- 日志服务、finalizer、report writer 通过统一路径对象获取路径。
- 不在业务逻辑中手写 `Path("output") / f"r{run_id}" / "data"`。

### 验收标准

- 现有 JSON 输出路径不变。
- 真实回测输出文件完整。
- 静态验证和真实回测验证通过。

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

新增运行生命周期服务，例如：

```text
application/run_lifecycle.py
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

## 阶段 3：抽出 BacktestRunService 应用编排层

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

新增应用服务，例如：

```text
application/backtest_run_service.py
```

包含：

- `BacktestRunService.run(args)` 或更明确的请求对象。
- `run_search(...)`
- `run_walk_forward(...)`
- 统一异常路径。
- 统一调用 RunLogService、RunFinalizer、Persister。

CLI 最终只负责：

```python
service = BacktestRunService(...)
service.run(args)
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

新增持久化服务，例如：

```text
application/backtest_persistence.py
```

或：

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

由应用层负责：

- 创建 run。
- 生成 study_name。
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

## 阶段 6：拆出 OptunaStudyService / OptunaQueryService

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

新增服务，例如：

```text
application/optuna_study_service.py
report/optuna_query.py
```

包含：

- `OptunaStudyService`
  - `make_study_name(strategy, engine, run_id)`
  - `link_run_study(run_id, study_name)`
  - `study_db_url()`
- `OptunaQueryService`
  - `get_optuna_data(run_id)`
  - `get_best_trial_index(run_id)`
  - 封装所有 Optuna 内部 SQL。

### 边界要求

- 应用层负责创建/关联 study。
- backtest 层只接收 `study_name` / `study_db_path`。
- report 层只通过 query service 获取优化展示数据。
- Optuna 内部表结构只在一个模块中出现。

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
- 同一个 backtest_id 重复插入 daily/trades 是否重复？
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
阶段 3：BacktestRunService 应用编排层
验证
阶段 4：结果持久化服务
验证
阶段 5：清理 runners 对 data 层依赖
验证
阶段 6：OptunaStudyService / OptunaQueryService
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
5. 阶段 3：BacktestRunService 应用编排层。
6. 阶段 4：结果持久化服务。

可后置但不能遗漏：

- 阶段 6：Optuna 边界独立封装。
- 阶段 9：幂等性和重跑策略。
- 阶段 10：统一 TqSdk 生命周期。

## 每阶段完成记录模板

每完成一个阶段，在本文档末尾追加记录：

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
