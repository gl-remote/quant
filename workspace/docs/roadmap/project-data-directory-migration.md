# project_data 目录迁移计划

> 类型：Roadmap / 迁移计划  
> 状态：规划中  
> 目标：将项目运行数据、报告产物、日志、缓存、测试产物统一收敛到显式可发现的 `project_data/` 目录，替代隐藏目录 `.quant_shared_data/` 与混杂的 `output/`。

## 背景

当前项目本地文件分散在两个主要位置：

- `.quant_shared_data/`：隐藏目录，存放 CSV K 线数据与 SQLite 主库。
- `output/`：混合存放 report 产物、前端 bundle、K 线 JSON 缓存、DataFeed parquet 缓存、worker 日志、coverage、profile 等。

存在的问题：

- `.quant_shared_data/` 是隐藏目录，AI、IDE、人工巡检都不容易主动发现。
- `output/` 同时承载最终报告、缓存、日志、测试覆盖率、性能 profile，边界不清。
- 生产日志既是运行产物，也是 report 构建输入，不能简单当成临时文件清掉。
- `workspace/packages/contracts/` 已经定义 report JSON schema，目录迁移必须同步 contract 验证路径。

本迁移目标是建立一个专业、显式、易发现、易被 AI 理解的统一文件管理根目录。

## 目标目录结构

```text
project_data/
├── market_data/
│   └── csv/
│       └── DCE.m2601.tqsdk.1m.csv
├── database/
│   └── quant_shared.db
├── reports/
│   ├── index.html
│   ├── assets/
│   ├── data/
│   │   └── nav.json
│   └── runs/
│       └── r1/
│           └── data/
│               ├── run.json
│               ├── summary.json
│               ├── backtests.json
│               ├── equity.json
│               ├── trades.json
│               ├── optuna.json
│               ├── kline_*.json
│               └── logs.json
├── logs/
│   └── runs/
│       └── r1/
│           ├── run.log
│           └── workers/
│               └── worker_*.log
├── cache/
│   ├── report_build/
│   ├── kline_json/
│   └── datafeed/
├── profiles/
└── coverage/
```

## 目录职责

| 目录 | 职责 | 是否可删除 | 说明 |
|---|---|---:|---|
| `project_data/market_data/csv/` | 外部拉取或搜集的 K 线 CSV | 否 | 回测数据源，默认保留 |
| `project_data/database/` | SQLite 主库 | 否 | 存放 export metadata、runs、backtests、Optuna 表 |
| `project_data/reports/` | 可打开、可分享、可 contract 验证的报告产物 | 是 | 可由 DB、CSV、日志重建 |
| `project_data/logs/` | 原始运行日志 | 谨慎 | report 的 `logs.json` 来源，默认不随意清 |
| `project_data/cache/` | 可重建缓存 | 是 | report build、K 线 JSON、DataFeed parquet |
| `project_data/profiles/` | 性能分析文件 | 是 | debug/profile 产物 |
| `project_data/coverage/` | 测试覆盖率 HTML | 是 | pytest coverage 产物 |

## 日志与 report 的关系

日志不能简单归类为临时文件。当前 report 构建链路依赖日志：

```text
project_data/logs/runs/rN/run.log
project_data/logs/runs/rN/workers/*.log
        ↓ export_json
project_data/reports/runs/rN/data/logs.json
        ↓ write_entry_html
project_data/reports/index.html
```

迁移后的原则：

- raw log 是运行证据，放 `project_data/logs/`。
- `logs.json` 是 report contract 产物，放 `project_data/reports/runs/rN/data/`。
- `index.html` 只消费 report data，不直接读取 raw log。
- 清理 report 时不默认删除 raw log，除非执行明确的日志清理命令。

## contracts 约束

`workspace/packages/contracts/` 定义 report JSON schema，`workspace/packages/python-contracts/` 验证真实生成物。

迁移后 contract 验证目标从：

```text
output/rN/data/*.json
output/data/nav.json
```

改为：

```text
project_data/reports/runs/rN/data/*.json
project_data/reports/data/nav.json
```

需要同步更新：

- `workspace/packages/contracts/README.md`
- `workspace/packages/python-contracts/src/quantsmith_contracts/validate.py`
- `workspace/packages/python-contracts/tests/conftest.py`
- `workspace/packages/python-contracts/tests/test_run_artifacts.py`

## 临时迁移护栏测试

迁移前先新增一批带 `directory_migration` 标记的临时测试，用来固定目标结构。

建议覆盖：

| 测试方向 | 验证点 |
|---|---|
| 配置路径解析 | `base_dir`、`export_dir`、`db_path` 解析到 `project_data/...` |
| report 路径 | run 级 JSON 写入 `project_data/reports/runs/rN/data/` |
| 日志路径 | raw log 写入 `project_data/logs/runs/rN/`，`logs.json` 写入 report data |
| contract fixture | latest run 从 `project_data/reports/runs/rN` 查找 |
| 禁止旧路径 | 新代码不再硬编码 `.quant_shared_data`、`output/r`、`output/data/nav.json` |

测试可在早期使用 `xfail`，随着迁移推进逐步转正。阶段完成后删除临时标记或改为常规回归测试。

## 迁移步骤

| 阶段 | 目标 | 主要改动 | 验收 |
|---|---|---|---|
| 准备与护栏 | 建立计划与临时测试 | 新增本 roadmap；新增 `directory_migration` 测试 | 测试能准确描述目标结构 |
| 路径抽象 | 所有路径通过统一函数获取 | 新增 `project_data_root()`、`reports_root()`、`run_logs_dir()` 等路径函数 | 业务代码不再自行拼根目录 |
| 配置与数据路径 | CSV 与 DB 迁入 `project_data` | 更新 `conf.toml`、DataManager、DataStore、exporter、fetch 脚本 | 新 CSV/DB 写入目标路径 |
| report 产物 | report 输出迁入 `project_data/reports` | 更新 report output paths、JSON writer、frontend builder、entry HTML | `index.html` 与 JSON 写入新路径 |
| 日志链路 | raw log 与 report `logs.json` 分离 | 更新 RunLogHelper、parallel worker log 路径 | raw log 可生成 `logs.json` |
| 缓存与诊断产物 | cache/profile/coverage 归位 | 更新 BuildCache、KlineCache、DataFeed、profile、pytest coverage | 不再写入 `output/.cache`、`output/coverage` |
| contracts 同步 | contract 验证新 report 路径 | 更新 contracts README、validate docstring、pytest fixtures | python-contracts 能验证新路径 |
| 脚本与清理策略 | Makefile 与 shell 脚本适配 | 新增分层 clean 命令，更新提示文案 | 脚本不再打印旧 `output/index.html` |
| 历史数据迁移 | 移动既有 CSV/DB/output 内容 | 迁移文件；更新 `export_metadata.filepath` | 旧 run/report 可继续读取 |
| 回归测试 | 全链路验证 | 跑 lint、type check、pytest、contract、report 构建 | 所有检查通过，无新文件写旧目录 |
| 旧目录清理 | 移除旧目录与兼容逻辑 | 删除 `.quant_shared_data/`、`output/`、fallback 代码、临时 xfail | 仓库根只保留 `project_data/` 作为本地数据根 |

## 统一路径函数草案

建议集中提供以下路径函数：

```text
project_data_root()
market_data_dir()
market_csv_dir()
database_dir()
database_path()
reports_root()
report_assets_dir()
report_nav_path()
report_runs_root()
run_report_dir(run_id)
run_report_data_dir(run_id)
run_logs_dir(run_id)
worker_logs_dir(run_id)
cache_root()
report_build_cache_dir()
kline_json_cache_dir()
datafeed_cache_dir()
profiles_dir()
coverage_dir()
```

迁移原则：

- 业务模块不直接写 `.quant_shared_data`、`output` 或硬编码绝对路径。
- report 域只通过 report 路径函数获取报告产物路径。
- data 域只通过 data/project-data 路径函数获取 CSV、DB、缓存路径。
- 日志路径与 report data 路径分离，`logs.json` 是由 raw log 派生的 report 产物。
- contracts 验证路径跟随 report data 目录，不验证 raw log。

## 阶段明细检查项

### 阶段 0：Roadmap 与临时护栏测试

- [x] 本文档已创建并包含目标目录、迁移边界、日志链路、contracts 约束、阶段 9/10。
- [x] 新增 `directory_migration` 测试标记。
- [x] 新增配置路径解析测试，覆盖 `base_dir`、`export_dir`、`db_path`。
- [x] 新增 report 路径测试，覆盖 `project_data/reports/runs/rN/data/`。
- [x] 新增日志路径测试，覆盖 raw log 与 `logs.json` 分离。
- [x] 新增 contract fixture 路径测试，覆盖 latest run 从 `project_data/reports/runs/rN` 查找。
- [x] 新增旧路径禁用测试，覆盖 `.quant_shared_data`、`output/r`、`output/data/nav.json`。
- [x] 新增 DB 文本字段旧路径扫描测试或脚本，覆盖 `.quant_shared_data`、`output`。
- [x] 新增 report JSON 旧路径扫描测试，重点覆盖 `kline_*.json` 的 `csv_source`。
- [x] 新增前端预加载 key 测试，确认 `window.__DATA__` key 与前端 loader 一致。
- [x] 早期未完成项使用 `xfail`，并注明对应迁移阶段。
- [x] 阶段检查：阶段 0 的 checklist 已逐项确认，临时护栏已转为常规回归测试。

### 阶段 1：统一路径抽象

- [x] 提供 `project_data_root()`。
- [x] 提供 `market_data_dir()`、`market_csv_dir()`。
- [x] 提供 `database_dir()`、`database_path()`。
- [x] 提供 `reports_root()`、`report_assets_dir()`、`report_nav_path()`。
- [x] 提供 `report_runs_root()`、`run_report_dir(run_id)`、`run_report_data_dir(run_id)`。
- [x] 提供 `run_logs_dir(run_id)`、`worker_logs_dir(run_id)`。
- [x] 提供 `cache_root()`、`report_build_cache_dir()`、`kline_json_cache_dir()`、`datafeed_cache_dir()`。
- [x] 提供 `profiles_dir()`、`coverage_dir()`。
- [x] report 域代码不再自行拼 report 根目录。
- [x] data 域代码不再自行拼数据根目录。
- [x] 新增路径函数单元测试。
- [x] 阶段检查：阶段 1 的路径抽象已逐项确认，新增路径均有测试或调用方覆盖。

### 阶段 2：配置与数据路径迁移

- [x] `conf.toml` 的 `base_dir` 改为 `project_data`。
- [x] `conf.toml` 的 `export_dir` 改为 `project_data/market_data/csv`。
- [x] `conf.toml` 的 `db_path` 改为 `project_data/database/quant_shared.db`。
- [x] 检查 `config/conf.local.toml` 是否覆盖 `[data]` 路径；未发现 `[data]` 路径覆盖。
- [x] `ConfigManager` 相对路径解析仍指向仓库根。
- [x] `DataStore` 使用新 DB 路径并能自动创建父目录。
- [x] `DataManager` 默认 CSV 目录不再写死 `.quant_shared_data/csv`。
- [x] `export_csv()` 新导出的 CSV 写入 `project_data/market_data/csv/`。
- [x] `fetch_data.py` 的跳过逻辑使用新 CSV 目录。
- [x] `DataManager.load_kline()` 能通过 `export_metadata` 找到 CSV。
- [x] 对旧 DB metadata 迁移前后的行为有测试或手工验证记录。
- [x] 阶段检查：阶段 2 的配置、CSV、DB 读写路径已逐项确认，未出现旧路径新写入。

### 阶段 3：report 生成物迁移

- [x] `reports_root()` 指向 `project_data/reports/`。
- [x] run 级目录从 `output/rN/` 改为 `project_data/reports/runs/rN/`。
- [x] `nav.json` 写入 `project_data/reports/data/nav.json`。
- [x] `run.json` 写入 `project_data/reports/runs/rN/data/run.json`。
- [x] `summary.json`、`backtests.json`、`equity.json`、`trades.json`、`optuna.json` 写入新 run data 目录。
- [x] `kline_*.json` 写入新 run data 目录。
- [x] 前端 bundle 写入 `project_data/reports/assets/`。
- [x] `write_entry_html()` 输出 `project_data/reports/index.html`。
- [x] `window.__DATA__` 预加载逻辑扫描新 report data 目录。
- [x] `make report` 文案提示新入口路径。
- [x] 阶段检查：阶段 3 的 report 产物路径、前端预加载与离线入口已逐项确认。

### 阶段 4：日志链路迁移

- [x] `run.log` 写入 `project_data/logs/runs/rN/run.log`。
- [x] worker 日志写入 `project_data/logs/runs/rN/workers/worker_*.log`。
- [x] `RunLogHelper.export_json()` 从新 raw log 目录读取主日志。
- [x] `RunLogHelper.export_json()` 从新 workers 目录读取 worker 日志。
- [x] `logs.json` 写入 `project_data/reports/runs/rN/data/logs.json`。
- [x] `write_entry_html()` 能把新 `logs.json` 内联进 `index.html`。
- [x] report 清理命令不默认删除 raw log。
- [x] 日志链路测试覆盖 raw log → `logs.json` → `index.html`。
- [x] 阶段检查：阶段 4 的 raw log、worker log、`logs.json` 与 entry HTML 链路已逐项确认。

### 阶段 5：缓存、profile、coverage 迁移

- [x] `BuildCache` 使用 `project_data/cache/report_build/`。
- [x] `KlineCache` 使用 `project_data/cache/kline_json/`。
- [x] DataFeed 磁盘缓存使用 `project_data/cache/datafeed/`。
- [x] profile 文件写入 `project_data/profiles/`。
- [x] pytest coverage HTML 输出到 `project_data/coverage/`。
- [x] 不再生成 `output/.build_cache/`。
- [x] 不再生成 `output/.kline_cache/`。
- [x] 不再生成 `output/feeds/`。
- [x] 不再生成 `output/coverage/`。
- [x] 不再生成 `output/profiles/`。
- [x] 缓存清理命令只删除可重建缓存，不影响 CSV/DB。
- [x] 阶段检查：阶段 5 的缓存、profile、coverage 路径与清理边界已逐项确认。

### 阶段 6：contracts 同步

- [x] `workspace/packages/contracts/README.md` 路径说明改为 `project_data/reports/...`。
- [x] `validate.py` docstring 示例改为新路径。
- [x] `validate_run_artifacts()` 仍以 run 目录为输入，并验证其 `data/*.json`。
- [x] `python-contracts/tests/conftest.py` 从 `project_data/reports/runs/rN` 查找 latest run。
- [x] `nav_path` fixture 指向 `project_data/reports/data/nav.json`。
- [x] `test_run_artifacts.py` skip 文案更新为新路径。
- [x] contract 测试能验证最新 run 的 7 个 run artifact。
- [x] contract 测试能验证全局 `nav.json`。
- [x] 阶段检查：阶段 6 的 schema、Python contract 包与 contract 测试路径已逐项确认。

### 阶段 7：脚本与清理策略迁移

- [x] `Makefile` 增加或调整分层清理命令。
- [x] `clean-reports` 只清理 `project_data/reports/`。
- [x] `clean-cache` 只清理 `project_data/cache/`。
- [x] `clean-logs` 只清理 `project_data/logs/`，并需要明确命令触发。
- [x] `clean-backtests` 只清 DB 中回测/Optuna 相关表，不清 `export_metadata`。
- [x] `clean-runtime` 清理 reports/cache/profiles/coverage，但不清 market data 与 database。
- [x] `backtest-ma.sh`、`backtest-atr.sh`、`backtest-debug.sh` 文案不再提示 `output/index.html`。
- [x] `fetch_data.sh` 与 `fetch_data.py` 文案指向新 CSV 目录。
- [x] `.gitignore` 增加 `project_data/` 规则。
- [x] 确认 CI 不依赖 `output/coverage`。
- [x] 确认 coverage HTML 新路径不会进入 Git。
- [x] `.gitignore` 中旧目录规则保留到阶段 10 再清理。
- [x] 阶段检查：阶段 7 的 Makefile、脚本提示、清理命令边界已逐项确认。

### 阶段 8：历史数据迁移

- [x] 迁移前备份或确认 `.quant_shared_data/` 与 `output/` 当前状态。
- [x] 迁移脚本支持 dry-run。
- [x] 迁移脚本幂等，可重复执行。
- [x] 复制前不覆盖已有目标，或覆盖前自动备份。
- [x] 复制后校验文件数量和大小。
- [x] 迁移 SQLite 前确认没有进程占用数据库。
- [x] 复制 `.quant_shared_data/csv` 到 `project_data/market_data/csv`。
- [x] 复制 `.quant_shared_data/quant_shared.db` 到 `project_data/database/quant_shared.db`。
- [x] 如存在 `quant_shared.db-wal` 与 `quant_shared.db-shm`，同步处理或先 checkpoint 后再迁移。
- [x] 迁移后执行 SQLite 完整性检查。
- [x] 复制 `output/index.html` 到 `project_data/reports/index.html`。
- [x] 复制 `output/data` 到 `project_data/reports/data`。
- [x] 复制 `output/rN` 到 `project_data/reports/runs/rN`。
- [x] 复制 `output/assets` 到 `project_data/reports/assets`。
- [x] 复制 `output/.kline_cache` 到 `project_data/cache/kline_json`。
- [x] 复制 `output/.build_cache` 到 `project_data/cache/report_build`。
- [x] 复制 `output/feeds` 到 `project_data/cache/datafeed`。
- [x] 复制 `output/coverage` 到 `project_data/coverage`。
- [x] 复制 `output/profiles` 到 `project_data/profiles`。
- [x] 更新 `export_metadata.filepath` 中 `.quant_shared_data/csv` 的旧绝对路径。
- [x] 扫描 DB 中所有包含 `.quant_shared_data` 或 `output` 的文本字段。
- [x] 检查 `backtests.data_src` 是否需要迁移。
- [x] 检查 `backtests.engine_config` 中的 `study_db` 是否需要迁移。
- [x] 检查 Optuna/run/study metadata 中是否保存旧 DB 或旧 output 路径。
- [x] 验证 DB 中 `export_metadata.filepath` 指向的新 CSV 文件都存在。
- [x] 阶段 9 通过前不删除旧目录。
- [x] 阶段检查：阶段 8 的历史文件复制、DB metadata 更新、旧目录保留策略已逐项确认。

### 阶段 9：回归测试

- [x] 执行 `ruff check workspace/ scripts/ main.py`，结果通过。
- [x] 执行 `uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report`，结果通过。
- [x] 执行 `uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short`，结果 `390 passed, 3 deselected`。
- [x] 执行 `make report`，报告生成到 `project_data/reports/index.html`。
- [x] `make debug-single` 本次不执行；lint、mypy、pytest、contracts 与 report 构建已覆盖本次目录迁移链路。
- [x] 验证 CSV 能被 `DataManager.load_kline()` 找到。
- [x] 验证 DB 能正常打开并读取旧 run/backtest。
- [x] 验证 report 写到 `project_data/reports/index.html`。
- [x] 验证 raw log 能生成并拼出 `logs.json`。
- [x] 验证 contract 测试通过。
- [x] 验证没有新文件继续写入 `.quant_shared_data`。
- [x] 验证没有新文件继续写入 `output`。
- [x] 扫描 DB 文本字段，确认没有应迁移但仍残留的旧路径。
- [x] 扫描 report JSON，确认没有应迁移但仍残留的旧路径。
- [x] 验证前端 loader 与 `window.__DATA__` key 一致，页面可正常浏览。
- [x] 执行 SQLite 完整性检查通过。
- [x] 阶段检查：阶段 9 的 lint、类型检查、测试、contract、report 构建与旧路径写入检查已逐项确认。

### 阶段 10：清理无用文件和目录

- [x] 确认阶段 9 全部通过。
- [x] 删除 `.quant_shared_data/`。
- [x] 删除 `output/`。
- [x] 删除迁移期间的 fallback 兼容代码。
- [x] 移除临时 `xfail` 标记。
- [x] 将仍有价值的 `directory_migration` 测试转为常规回归测试。
- [x] 更新旧路径文档描述。
- [x] 清理 `.gitignore` 中 `.quant_shared_data` 与 `output/` 的旧规则。
- [x] 确认仓库根只保留 `project_data/` 作为本地数据根。
- [x] 阶段检查：阶段 10 的旧目录删除、兼容逻辑清理、文档更新与回归测试转正已逐项确认。
- [ ] 完成后将本 roadmap 按归档规范移动到 `workspace/docs/archive/`。本项待提交后补充 Git 参考并归档。

## 风险与回滚

| 风险 | 影响 | 应对 |
|---|---|---|
| DB metadata 仍指向旧 CSV | 回测加载数据失败 | 阶段 8 统一更新 `export_metadata.filepath` |
| raw log 搬走后 report 丢日志 | 前端日志面板为空 | 阶段 4 保证 raw log → `logs.json` 链路测试 |
| contract fixture 仍扫旧目录 | 契约测试误跳过或失败 | 阶段 6 同步更新 fixtures |
| clean 命令误删数据源 | CSV/DB 丢失 | 阶段 7 默认清理不删除 market data 与 database |
| 历史 output 未迁移完整 | 旧报告不可查 | 阶段 8 保留迁移清单并先复制后删除 |

回滚原则：

- 阶段 8 前不删除旧目录，只让新写入走 `project_data/`。
- 阶段 9 通过前不执行阶段 10。
- 历史数据迁移优先复制，确认可读后再删除旧目录。
