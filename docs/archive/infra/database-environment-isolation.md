# 数据库环境隔离设计

> 类型：Design / 已实现设计记录  
> 状态：已实现  
> 完成日期：2026-06-26  
> Git 参考：`待提交 database environment isolation implementation`  
> 范围：第一阶段仅做环境级 SQLite 物理隔离，不做领域拆表；不隔离 report/log/cache 等文件产物

## 背景

当前项目已完成本地文件根目录迁移，所有本地数据、报告、日志、缓存都归入 `project_data/`。但数据库仍是单文件设计：

```text
project_data/database/quant_shared.db
```

该 SQLite 文件同时承载：

- CSV 行情元数据：`export_metadata`
- 回测运行与结果：`runs`、`backtests`、`backtest_daily`、`backtest_trades`、`backtest_params`
- Optuna 内部表：`studies`、`trials`、`trial_*`、`study_*`
- run 与 study 关联：`run_studies`
- 实时 test 运行记录：`test_sessions`、`test_trades`
- live 运行记录：`live_sessions`、`live_trades`，运行 live 后动态创建
- 操作日志：`operation_logs`
- 项目迁移记录：`schema_info`

这意味着 `live`、`test`、`backtest`、`report`、`export` 当前都共享同一个数据库文件。对于量化系统，这属于环境隔离不足：测试和实盘状态可能混入回测/report 数据源，清理命令也可能误伤其它环境。

## 审计结论

### 数据库表职责

当前主库中表可以按职责粗分为：

| 域 | 表 | 说明 |
|---|---|---|
| 行情元数据 | `export_metadata` | CSV 文件位置、时间范围、行数 |
| 回测运行 | `runs`、`run_studies` | run 生命周期与 Optuna study 关联 |
| 回测结果 | `backtests`、`backtest_daily`、`backtest_trades`、`backtest_params` | 回测主表、逐日、逐笔、参数 |
| Optuna | `studies`、`trials`、`trial_*`、`study_*`、`version_info`、`alembic_version` | Optuna SQLite storage 内部表 |
| 实时 test | `test_sessions`、`test_trades` | `main.py test` 信号验证记录 |
| live | `live_sessions`、`live_trades` | `main.py live` 运行时交易记录，按需动态创建 |
| 运维日志 | `operation_logs` | export/backtest/test/live 操作日志 |
| 迁移 | `schema_info` | 项目自有 schema 迁移记录 |

### 当前调用链

```text
CLI command
    ↓
ConfigManager
    ↓
DataManager
    ↓
DataStore
    ↓
peewee global database
    ↓
project_data/database/quant_shared.db
```

主要入口：

| 命令/模块 | 当前行为 |
|---|---|
| `export` | 从 resolved env DB 读取或写入导出相关数据；数据库隔离只约束它使用哪个 env DB，不规定业务环境归属 |
| `backtest` | 写 `runs`、`backtests`、明细表、Optuna 表、`operation_logs` |
| `report` | 从 resolved env DB 读取 run/backtest/Optuna 数据并导出 JSON |
| `test` | 写 `test_sessions`、`test_trades`、`operation_logs` |
| `live` | 写 `live_sessions`、`live_trades`、`operation_logs` |
| Optuna | 通过 data 层当前 peewee database 路径生成 `sqlite:///...` storage URL |

### 结构性风险

当前风险不只是单个路径配置问题，还包括：

- `DataManager` 是单例，首次初始化的配置和 store 可能被后续入口复用。
- `ConfigManager` 当前委托 `ProjectConfig.instance()` 全局单例，若未由 CLI `--env` 明确初始化，裸 `DataManager()` 可能抢先绑定错误环境。
- `workspace/cli/main.py` 在命令解析前为 logging 创建 `ConfigManager()`，该初始化不得绑定或决定数据环境。
- peewee `database` 是全局对象，所有 ORM Model 共享同一个数据库连接。
- `data.models.init_database()` 是 `DataStore` 之外的第二条数据库初始化入口，若不纳入同一 guard，会绕过环境隔离。
- `test` 和 `live` 使用同一套 realtime workflow，仅通过 `mode` 决定表名前缀。
- report builder / writer 中存在裸 `DataManager()` fallback，非 CLI 调用必须复用当前进程已初始化环境，不能自行决定环境。
- `strategies.runtime.data_feed.DataFeed.from_requirements()` 内部存在裸 `DataManager()`，必须服从当前进程环境。
- Optuna storage 跟随当前 peewee database，如果进程环境未明确初始化，study 可能写错环境。
- 并行 Optuna worker 是 spawn 子进程，必须显式继承当前环境的 resolved 数据库路径。
- 测试中如果不 reset `ProjectConfig`、`DataManager` 和 peewee global database binding，环境用例会互相污染。

## 设计目标

第一阶段目标是建立环境级物理隔离：

- `backtest`、`test`、`live` 使用不同 SQLite 文件。
- 环境由 CLI `--env` 或显式 `--config` 的 resolved config 决定；不通过配置内 profile、环境变量或运行中切换决定。
- `--env` 走标准环境配置链；`--config` 也必须解析出 `data.environment` 与 `data.database_path`。
- 每个环境由基础配置 + 环境覆盖文件解析成一份完整同构配置；显式 `--config` 也必须解析成同构 `ProjectConfig`。
- 单个进程只绑定一个环境 DB，不支持运行中切换环境，不支持同进程同时读取多个环境库。
- 所有数据库读写入口只使用 resolved environment 对应的数据库；不跨环境读取，也不 fallback 到 backtest。
- `report` / `export` 类导出流程只关心读取或写入哪个 resolved env DB；不改变其业务语义或产物结构。
- `test` 的信号验证记录不能进入 backtest/live DB。
- `live` 的运行记录不能进入 backtest/test DB。
- Optuna storage 必须跟随当前环境 DB。
- 现有 `project_data/database/quant_shared.db` 直接迁移为 backtest 历史库，不做旧 `db_path` 兼容。

第一阶段明确不做：

- 不拆分行情元数据、回测结果、Optuna、live 状态到不同领域 DB。
- 不重构所有 ORM 表结构。
- 不引入多数据库 join。
- 不裁剪不同环境的 schema；三套环境可以使用同构表结构。
- 不隔离 report 产物目录、原始 logs、worker logs、cache、profiles、coverage 等非数据库文件产物；它们继续沿用现有 `project_data/` 布局。
- 不新增 `paper` environment，不改变 `test` / `live` 交易语义；本阶段只隔离现有命令环境的数据落库路径。

## 目标目录结构

数据库目录按环境分层：

```text
project_data/
└── database/
    ├── backtest/
    │   └── quant.db
    ├── test/
    │   └── quant.db
    └── live/
        └── quant.db
```

现有主库迁移为：

```text
project_data/database/quant_shared.db
        ↓
project_data/database/backtest/quant.db
```

`test` 和 `live` 环境默认不迁移历史数据，后续运行时自行创建空库。

## Environment 定义

第一阶段的核心原则是：**同一套表结构，不同环境使用不同 SQLite 文件与不同 resolved config**。

| Environment | 用途 | 默认 DB | 主要业务数据 |
|---|---|---|---|
| `backtest` | backtest、Optuna、report；export 如选择 backtest env 也使用该库 | `project_data/database/backtest/quant.db` | `export_metadata`、`runs`、`backtests`、回测明细、Optuna 表、`operation_logs` |
| `test` | `main.py test`、report | `project_data/database/test/quant.db` | `test_sessions`、`test_trades`、`operation_logs`；如该环境存在同构 run/backtest 数据，也在本环境内读取 |
| `live` | `main.py live`、report | `project_data/database/live/quant.db` | `live_sessions`、`live_trades`、`operation_logs`；如该环境存在同构 run/backtest 数据，也在本环境内读取 |
| `unit_test` | pytest 临时库 | 测试临时目录，不落入 `project_data` | 测试构造的数据 |

第一阶段不新增第四类交易环境。当前规划中的 `paper trading` 与 `test` 的语义区分已记录在 `docs/roadmap/plan.md` 的 `DEF-09`；本阶段不处理该语义建模，只为现有命令环境提供数据库隔离。

## CLI --env / --config 与命令约束

CLI 支持两种显式选择方式：

- `--env <env>`：标准入口，按 `conf.toml` + `conf.<env>.toml` + 可选 `conf.<env>.local.toml` 加载。
- `--config <path>`：高级显式入口，指定环境配置覆盖文件；该文件与 `conf.toml` deep merge 后必须解析出 `data.environment` 与 `data.database_path`。

二者关系：

- 命令至少需要能解析出一个 resolved environment。
- 同时传入 `--env` 与 `--config` 时，`--config` 解析出的 `data.environment` 必须等于 `--env`，否则 fail fast。
- 命令允许范围按 resolved environment 校验，而不是按参数来源校验。
- 命令启动时应打印 resolved environment 与 resolved database path，作为操作者自检信息。

示例：

```bash
uv run python main.py export --env backtest --symbol DCE.m2509
uv run python main.py export --config workspace/config/conf.backtest.toml --symbol DCE.m2509
uv run python main.py backtest --env backtest --strategy ma --pattern "DCE\\.m"
uv run python main.py report --env backtest --limit 10
uv run python main.py report --env test --limit 10
uv run python main.py report --env live --limit 10
uv run python main.py test --env test --strategy ma --symbol DCE.m2509
uv run python main.py live --env live --strategy ma --symbol DCE.m2509
uv run python main.py live --config workspace/config/conf.live.toml --strategy ma --symbol DCE.m2509
```

命令允许的 resolved environment：

| 命令 | 允许 resolved env | 说明 |
|---|---|---|
| `export` | `backtest` / `test` / `live` | 数据库隔离只约束其使用 resolved env DB；不在本阶段规定业务环境归属 |
| `backtest` | `backtest` | 写回测结果和 Optuna |
| `report` | `backtest` / `test` / `live` | 数据库 schema 同构；读取当前 env 的数据生成报告，不跨环境读取 |
| `test` | `test` | 记录当前 test 命令运行数据 |
| `live` | `live` | 记录当前 live 命令运行数据 |

必须显式传入 `--env` 或 `--config`，并解析出合法 resolved environment。不匹配时直接报错，例如 `live --env backtest`、`test --env live`，或 `live --config conf.backtest.toml` 都应失败。

## 配置设计

### 配置文件布局

采用基础配置 + 环境覆盖：

```text
workspace/config/
├── conf.toml                 # 基础配置：策略、通用参数、默认数据源等
├── conf.backtest.toml        # backtest 环境覆盖
├── conf.test.toml            # test 环境覆盖
├── conf.live.toml            # live 环境覆盖
├── conf.backtest.local.toml  # 可选，本机 backtest 私密覆盖
├── conf.test.local.toml      # 可选，本机 test 私密覆盖
└── conf.live.local.toml      # 可选，本机 live 私密覆盖
```

加载顺序：

```text
conf.toml
  ↓ deep merge
conf.<env>.toml
  ↓ deep merge（如果存在）
conf.<env>.local.toml
  ↓ validate / resolve paths
ProjectConfig
```

规则：

- `--env` 决定 `conf.<env>.toml` 与 `conf.<env>.local.toml`。
- `--config` 作为显式环境配置覆盖文件，与 `conf.toml` deep merge 后解析；最终必须解析出完整同构 `ProjectConfig`。
- 不再读取通用 `conf.local.toml` 作为所有环境共享覆盖，避免本机配置污染环境断言。
- 测试可通过内部 API 提供临时配置或 `unit_test` 环境。
- 环境覆盖文件应保持同构字段，只覆盖差异项。

### DataConfig

`DataConfig` 从旧的单一 `db_path` 改为 environment-aware，但每个 resolved config 只包含当前环境的数据库路径：

```toml
# conf.backtest.toml
[app]
mode = "backtest"

[data]
environment = "backtest"
database_path = "project_data/database/backtest/quant.db"
export_dir = "project_data/market_data/csv"
```

```toml
# conf.test.toml
[app]
mode = "test"

[data]
environment = "test"
database_path = "project_data/database/test/quant.db"
```

```toml
# conf.live.toml
[app]
mode = "live"

[data]
environment = "live"
database_path = "project_data/database/live/quant.db"
```

不再支持旧 `db_path`，也不使用 `db_paths` 字典。旧 `project_data/database/quant_shared.db` 只允许出现在迁移说明或“旧库禁止写入”测试中。

建议模型形态：

```python
DataEnvironment = Literal["backtest", "test", "live", "unit_test"]


class DataConfig(BaseModel):
    provider: str = "tqsdk"
    cache_enabled: bool = False
    environment: DataEnvironment
    base_dir: str = ""
    export_dir: str = ""
    database_path: str
    filename_template: str = "{symbol}.{provider}.{interval}.csv"
```

解析规则：

```text
resolved_database_path = resolve(data.database_path)
```

如果环境配置未提供 `data.database_path`，配置加载应直接报错。测试如需临时库，可通过专用测试 API 注入临时数据库路径；不得 fallback 到旧 `quant_shared.db` 或旧 `db_path`。

### 路径函数

建议扩展 `workspace/data/output_paths.py`：

```text
database_root()
database_environment_dir(env)
database_path(env)
```

语义：

```text
database_root()                         -> project_data/database/
database_environment_dir("backtest")    -> project_data/database/backtest/
database_path("backtest")               -> project_data/database/backtest/quant.db
database_path("test")                   -> project_data/database/test/quant.db
database_path("live")                   -> project_data/database/live/quant.db
```

现有无参数 `database_path()` 不应再返回 `quant_shared.db`。业务代码应通过 resolved `DataConfig.database_path` 获取当前环境 DB；测试可直接调用 `database_path(env)` 断言路径。

## API 约定

### DataEnvironment 类型

建议在 `workspace/config/schemas.py` 或 `workspace/data/output_paths.py` 中定义统一的环境字面量：

```python
DataEnvironment = Literal["backtest", "test", "live", "unit_test"]
```

如果不想引入全局 type alias，也必须提供等价的校验常量：

```python
VALID_DATA_ENVIRONMENTS = {"backtest", "test", "live", "unit_test"}
```

### ConfigManager env API

推荐 API：

```python
cm = ConfigManager(env=args.env)
cm = ConfigManager(config_file=args.config)
```

约定：

- `env` 是标准 CLI 入口参数；`config_file` 是高级显式入口参数。
- `ConfigManager(env=...)` 加载 `conf.toml`、`conf.<env>.toml`、可选 `conf.<env>.local.toml`，并解析为完整 `ProjectConfig`。
- `ConfigManager(config_file=...)` 加载 `conf.toml`，再 deep merge 操作者指定的环境配置覆盖文件，并解析为完整 `ProjectConfig`；合并结果必须包含 `data.environment` 与 `data.database_path`。
- 如果 `env` 不在允许集合内，加载配置阶段直接报错。
- 如果同时指定 `env` 与 `config_file`，解析后的 `get_data_config().environment` 必须等于目标 env。
- `get_data_config().environment` 必须等于 resolved env。
- `get_data_config().database_path` 必须已经解析为 resolved env 的绝对路径。
- `workspace/cli/main.py` 为 logging 创建的配置对象不得决定数据环境；在命令解析前只允许使用不触发数据环境绑定的 logging 基础配置，或延后 setup logging 到 `--env` / `--config` 解析后。
- 常规 CLI 保留 `--config`，但必须按 resolved environment 做命令级校验，不能绕过环境约定。
- 不使用隐式全局变量或环境变量切换 env。

### 进程级环境初始化

本阶段是进程级环境隔离，不支持同一进程访问多个 data environment。

允许：

- 同一进程内重复创建同环境的 `ConfigManager` / `DataManager` / `DataStore`。
- 裸 `DataManager()` 使用当前进程已经初始化的 env。
- `report` 在任意 env 内读取该 env 的同构数据。

禁止：

- 同一进程从 backtest 切换到 test/live。
- 未初始化 env 时由裸 `DataManager()` 自行决定环境。
- report 跨环境读取或 fallback 到 backtest。
- test/live 读取 backtest 作为 fallback。
- 通过环境变量、旧 `db_path`、旧 `quant_shared.db` 隐式切换环境。

## DataManager 与连接生命周期

### 取消 DataManager 单例

第一阶段建议直接取消 `DataManager` 单例。

当前单例设计会导致：

```text
DataManager(backtest_config)
DataManager(live_config)
```

第二次初始化可能复用第一次的 `_config` 和 `_store`。这会破坏环境隔离。

目标行为：

- 每次 `DataManager(config_manager)` 都是普通对象。
- 每个 `DataManager` 懒加载一个 `DataStore`。
- `DataStore` 绑定构造时确定的 `DataConfig.database_path`。
- 同一进程内只允许一个 active env。
- `DataManager.close()` 关闭 store 后应清空 `_store`，避免复用已关闭连接。
- 裸 `DataManager()` 只允许在进程 env 已初始化后复用该 env；未初始化 env 时直接报错。

### peewee global database 约束

当前 ORM 使用全局 peewee database。第一阶段不改 ORM 模型，只明确约束：

- 一个进程只绑定一个 env DB。
- `DataStore` 初始化时如果全局 database 已连接到不同路径，应 fail fast。
- 测试需要显式 close/reset，避免跨用例污染。

建议实现判断规则：

```text
expected_path = abs(database_path_from_current_env)
current_path = abs(database.database) if database.database else None

if current_path is None:
    database.init(expected_path)
elif current_path == expected_path:
    reuse current database binding
elif database.is_closed():
    database.init(expected_path)
else:
    raise RuntimeError("peewee database already bound to another environment")
```

如果 peewee 不允许重复 `init()`，实现时可先 `database.close()` 或使用项目已有重置 helper，但必须有测试覆盖不同 env 不静默复用连接。

`data.models.init_database(db_path)` 也必须服从同一规则。它不能绕过 `DataStore` 的路径检查直接重绑全局 database。可选实现：

- 提取统一 helper，例如 `bind_database(db_path, *, pragmas=None)`，供 `DataStore` 与 `init_database()` 共用。
- 或将 `init_database()` 限定为测试辅助，并要求调用前显式执行测试 reset helper。

无论采用哪种方式，已连接 DB A 时初始化 DB B 都不能静默成功。错误信息应包含当前路径与目标路径，便于排查串库。

### 测试隔离策略

env-aware fail-fast 会让测试更容易暴露全局状态污染。实现阶段必须同步整理测试 fixture：

- 每个测试用例结束后关闭 peewee database。
- reset `ProjectConfig` / `ConfigManager` 全局单例。
- 取消 `DataManager` 单例后不再需要 reset manager；迁移期间若单例仍存在，测试 fixture 必须清空 `_instance` 和 `_initialized`。
- 提供仅测试使用的 database binding reset helper，允许不同临时 DB 用例之间显式切换。
- `unit_test` env 使用 pytest 临时目录，不写入 `project_data`。
- 测试不读取真实 `conf.<env>.local.toml`，除非用例明确覆盖 local merge 行为。
- 多 env 测试不能依赖表不存在；第一阶段允许统一 schema，只断言命令写入当前 env DB，不跨 env 写入。

## CLI 改造边界

### export

`export` 使用 resolved environment 对应的数据库。

```text
main.py export --env <env>
    ↓
ConfigManager(env=<env>)
    ↓
DataManager(cm)
```

当前实现如果写 `export_metadata` 和 `operation_logs`，只能写入 resolved env DB。本阶段不规定 `export` 的业务环境归属，也不扩展或收缩其业务能力。

### backtest

`backtest` 只允许 resolved environment 为 `backtest`。

```text
main.py backtest --env backtest
    ↓
ConfigManager(env="backtest")
    ↓
DataManager(cm)
```

回测结果、Optuna storage、run/study 关联都写入 backtest DB。

### report

`report` 允许 resolved environment 为 `backtest`、`test`、`live`。

```text
main.py report --env <env>
    ↓
ConfigManager(env=<env>)
    ↓
DataManager(cm)
```

约束：

- report 读取当前 env 的同构数据库。
- report 不跨环境读取，不 fallback 到 backtest。
- report 只负责选择正确的 resolved env DB；本阶段不扩展 report 数据模型，不要求展示 realtime session/trade。
- 如果当前 env 没有对应 run/backtest/Optuna 数据，报告为空或给出明确提示。
- `report --build` 的输出目录本阶段不做 env 隔离，继续沿用现有 report 产物路径；不同环境产物覆盖属于第一阶段可接受风险。

### test

`test` 只允许 resolved environment 为 `test`。

```text
main.py test --env test
    ↓
ConfigManager(env="test")
    ↓
DataManager(cm)
```

`test_sessions` 和 `test_trades` 只能在 test DB 中产生业务数据。

### live

`live` 只允许 resolved environment 为 `live`。

```text
main.py live --env live
    ↓
ConfigManager(env="live")
    ↓
DataManager(cm)
```

`live_sessions` 和 `live_trades` 只能在 live DB 中产生业务数据。

## 文件级改动清单

### 必改文件

| 文件 | 改动 |
|---|---|
| `workspace/data/output_paths.py` | 增加 `database_root()`、`database_environment_dir(env)`、`database_path(env)`；不再返回 `quant_shared.db`；report/log/cache 等非数据库路径保持现状 |
| `workspace/config/schemas.py` | `DataConfig` 删除 `db_path`，增加 `environment`、`database_path` 字段和 env 校验 |
| `workspace/config/manager.py` | 实现 `ConfigManager(env=...)` 与保留 `ConfigManager(config_file=...)`；按 `conf.toml` + `conf.<env>.toml` + `conf.<env>.local.toml` 加载标准 env；显式 config 按 `conf.toml` + 指定覆盖文件合并后解析，必须解析出 environment/database_path；解析相对路径；禁止旧 `db_path` fallback |
| `workspace/config/conf.toml` | 删除 `db_path`；保留基础通用配置 |
| `workspace/config/conf.backtest.toml` | 新增 backtest 环境覆盖，指向 `project_data/database/backtest/quant.db` |
| `workspace/config/conf.test.toml` | 新增 test 环境覆盖，指向 `project_data/database/test/quant.db` |
| `workspace/config/conf.live.toml` | 新增 live 环境覆盖，指向 `project_data/database/live/quant.db` |
| `workspace/data/manager.py` | 取消单例；按 config 的 resolved `database_path` 初始化 `DataStore`；`close()` 后清空 `_store`；裸 `DataManager()` 未初始化 env 时报错 |
| `workspace/data/store.py` | 增加 peewee database path fail-fast；避免不同 env 静默复用连接 |
| `workspace/data/models.py` | `init_database()` 服从统一 bind guard，不能绕过 path fail-fast |
| `workspace/cli/main.py` | 增加全局或子命令 `--env` / `--config`；解析后再初始化 env 相关配置；命令分发前按 resolved env 做校验 |
| `workspace/cli/commands/export.py` | 使用 resolved env 对应数据库；若读写 DB，只能读写当前 env DB，不在本阶段规定业务环境归属 |
| `workspace/cli/commands/report.py` | 使用 resolved env 对应环境；report 读取当前 env DB；不得 fallback 到 backtest；report 输出路径本阶段保持现状 |
| `workspace/cli/commands/backtest.py` / `workspace/cli/workflows/backtests_run.py` | 要求 resolved env 为 backtest；并行 worker 显式继承 backtest DB 路径 |
| `workspace/cli/commands/test.py` / `workspace/cli/workflows/realtime.py` | 要求 resolved env 为 test；使用 test 环境配置 |
| `workspace/cli/commands/live.py` / `workspace/cli/workflows/realtime.py` | 要求 resolved env 为 live；使用 live 环境配置 |
| `workspace/data/optuna_query.py` | `get_optuna_url()` 跟随当前 env DB；未初始化时抛清晰异常；必要时校验与当前 store 路径一致 |
| `workspace/report/builder/data_exports.py` | 裸 `DataManager()` fallback 只能复用当前进程 env；report 不固定 backtest |
| `workspace/report/writer/json_writer.py` | 裸 `DataManager()` fallback 只能复用当前进程 env；直接 ORM 查询前必须确保当前 env DB 已绑定 |
| `workspace/strategies/runtime/data_feed.py` | 内部裸 `DataManager()` 必须服从当前进程 env；未初始化 env 时不能自行绑定默认库 |
| `workspace/report/output_paths.py` | 本阶段不要求 report 产物路径支持 env 隔离；仅在必要时适配调用方签名，保持现有产物目录语义 |

### 可能需要同步的测试文件

| 文件 | 改动 |
|---|---|
| `workspace/tests/test_project_data_layout.py` | 更新数据库路径断言，覆盖 env DB 路径和旧 `quant_shared.db` 禁止写入 |
| `workspace/tests/config/test_config.py` | 增加 `ConfigManager(env=...)`、`ConfigManager(config_file=...)`、环境覆盖加载顺序、`DataConfig.database_path` 解析和 local merge 测试；断言不支持旧 `db_path` |
| `workspace/tests/data/test_database.py` | 增加 DataManager 非单例、`close()` 清空 store、裸 `DataManager()` 未初始化 env 报错、DataStore fail-fast、env DB 初始化测试 |
| `workspace/tests/data/test_models.py` | 如 init_database 测试依赖旧路径，改成临时 DB 或 env DB；覆盖 `init_database()` 不能绕过 path fail-fast |
| `workspace/tests/conftest.py` | 增加测试隔离 fixture，reset `ProjectConfig`、迁移期 `DataManager` 单例和 peewee database binding，避免 env 测试互相污染 |
| `workspace/tests/cli/` 或新增测试文件 | 覆盖 `--env` / `--config` 显式入口、命令/resolved env 校验、realtime 数据隔离、report 允许多 env |
| `workspace/tests/report/` | 覆盖 report 读取当前 env DB；覆盖 report builder/writer 裸 `DataManager()` 只能复用当前 env；不要求 report 输出路径按 env 隔离 |
| `workspace/tests/backtest/` | 覆盖 Optuna URL 使用 backtest env DB；覆盖并行 worker 使用 backtest DB |

### 可选新增文件

| 文件 | 用途 |
|---|---|
| `workspace/tests/test_database_environment_isolation.py` | 集中放环境隔离护栏测试 |
| `scripts/tools/migrate-database-environments.py` | 一次性迁移脚本，执行 checkpoint、直接移动旧库、integrity check |

不要为了文档本身强制新增迁移脚本。如果实现时 shell 命令足够清晰，也可以不创建脚本。

## Report、Export 与 Optuna

### Report

`report` 是环境内报告工具。数据库隔离只约束它读取哪个 resolved env DB，不在本阶段扩展 report 数据模型或输出结构。

执行约束：

- `report --env backtest` 读取 backtest DB。
- `report --env test` 读取 test DB。
- `report --env live` 读取 live DB。
- `report` 不跨环境读取，不 fallback 到 backtest。
- `report` 只读取当前 env DB 中已有的同构 run/backtest/Optuna 数据；不要求展示 `test_sessions` / `live_sessions`。
- `run_studies` 与 Optuna 内部表必须在同一个当前 env DB。
- 如果当前 env 中 `study_name` 存在但 Optuna 表缺失，report 应跳过 Optuna 图表或给出明确 warning，不能读取其它 env DB 兜底。
- 报告产物本阶段不按 env 隔离，继续沿用现有 JSON/HTML 输出目录；不同环境 report build 覆盖产物属于可接受风险。

### Export

`export` 使用 resolved env DB。数据库隔离只约束它读写哪个 SQLite 文件，不改变 `export` 的业务语义。

执行约束：

- `export --env backtest` 读写 backtest DB。
- `export --env test` 读写 test DB。
- `export --env live` 读写 live DB。
- 当前实现若写 `export_metadata` 和 `operation_logs`，只能写入当前 resolved env DB。

### Optuna

Optuna storage 当前通过 data 层当前 peewee database 路径生成：

```text
sqlite:///<current-env-db-path>
```

环境隔离后必须保持这个语义：

- `backtest --env backtest` 的 Optuna 写入 `project_data/database/backtest/quant.db`。
- 若未来其它 env 产生 Optuna 数据，也只写当前 env DB。
- report 构建 Optuna 图表时读取当前 env DB。
- `get_optuna_url()` 在 peewee database 未初始化时必须抛出清晰异常，不能生成无效 URL。
- 如果存在 `DataManager` / `DataStore` 上下文，Optuna URL 使用的路径必须与当前 store 的 `database_path` 一致；不一致时 fail fast。
- report 生成图表与 backtest 优化应使用一致的 SQLite storage URL 生成规则，避免一个读 global database、一个读 `dm.store.db_path` 导致 run/study 分离。
- 并行 Optuna worker 必须显式继承当前 env 的 resolved DB 路径，不允许在 worker 内裸 `ConfigManager()` 决定环境。

## 数据迁移策略

### 迁移目标

将现有主库作为 backtest 历史库直接移动：

```text
project_data/database/quant_shared.db
        ↓
project_data/database/backtest/quant.db
```

`test` / `live` 历史数据不迁移，后续由对应环境自行生成。迁移前如需追溯旧 test/live 记录，应依赖外部备份。

### 迁移命令草案

实际执行前先确认没有进程占用数据库，并先做外部备份。

```bash
mkdir -p project_data/database/backtest
sqlite3 project_data/database/quant_shared.db "PRAGMA wal_checkpoint(TRUNCATE);"
mv project_data/database/quant_shared.db project_data/database/backtest/quant.db
sqlite3 project_data/database/backtest/quant.db "PRAGMA integrity_check;"
```

如果存在 WAL/SHM 文件：

```bash
ls project_data/database/quant_shared.db-wal project_data/database/quant_shared.db-shm
```

必须先 checkpoint，再移动主 DB。不要直接只移动 `quant_shared.db-wal` 或 `quant_shared.db-shm` 到新目录。

目标文件已存在时：

- 不直接覆盖。
- 先人工确认目标库是否应保留。
- 如需保留，先把已有目标移到外部备份路径。
- 再执行旧主库移动。
- 移动后跑 integrity check。

旧 `quant_shared.db` 不移动到项目内 legacy 目录作为代码可见 fallback。迁移完成后，新代码不得创建或写入 `project_data/database/quant_shared.db`。

### 迁移安全原则

- 迁移前备份现有 `quant_shared.db`、`-wal`、`-shm`。
- 迁移前确认无进程占用数据库。
- 先 checkpoint，再直接移动主 DB。
- 移动后执行 SQLite integrity check。
- 验证 `backtest --env backtest` / `report --env backtest` 能读取新 DB；`export --env <env>` 只读写对应 env DB。
- 验证 `test --env test` / `live --env live` 新写入不会进入 backtest DB。
- 验证新代码不会重新生成 `project_data/database/quant_shared.db`。

## 护栏测试

建议新增以下测试：

| 测试方向 | 验证点 |
|---|---|
| 路径函数 | `database_path("backtest")`、`database_path("test")`、`database_path("live")` 分别指向独立路径；无参数路径不指向 `quant_shared.db` |
| 配置解析 | `ConfigManager(env=...)` 按基础配置 + 环境覆盖 + env local 解析；`data.environment` 与 `data.database_path` 正确；旧 `db_path` 不被接受 |
| CLI env/config | 所有数据库相关命令必须显式传 `--env` 或 `--config` 并解析出 env；backtest/test/live 做 resolved env 限制；report/export 读取或写入当前 env DB；`--env` 与 `--config` 同传时必须一致 |
| DataManager 非单例 | 两个同 env config 创建的 DataManager 不共享 store/config；不同 env 不能在同一进程静默切换 |
| 裸 DataManager | 已初始化 env 后可复用当前 env；未初始化 env 时直接报错 |
| 串库防护 | 已连接 DB 路径与目标 env 不一致时 fail fast；`DataStore` 与 `init_database()` 均不能静默切换 DB |
| realtime 数据隔离 | `test --env test` 或等价 `--config` 只向 test DB 写入 `test_sessions`/`test_trades`；`live --env live` 或等价 `--config` 只向 live DB 写入 `live_sessions`/`live_trades` |
| report 输入 | report 读取当前 env DB，不跨环境、不 fallback；report builder/writer fallback 只能复用当前 env；report 产物路径不作为本阶段隔离验收项 |
| 非数据库产物 | report/log/worker log/cache 等路径保持现状；不作为第一阶段隔离验收项 |
| export DB | `export --env backtest/test/live` 均读写对应 env DB；如写 DB，只写当前 resolved env DB；不测试或规定 export 的业务环境归属 |
| Optuna storage | `get_optuna_url()` 返回当前 env DB 的 SQLite URL；未初始化或与当前 store 不一致时 fail fast；并行 worker 继承当前 env DB |
| 迁移验证 | 迁移后的 backtest DB 能读取旧 run/backtest/export_metadata |
| 旧主库禁止 | 新代码不再写 `project_data/database/quant_shared.db` |

## 实施步骤

| 阶段 | 目标 | 主要改动 | 验收 |
|---|---|---|---|
| 设计与护栏 | 固定目标行为 | 更新本设计文档；新增 xfail 护栏测试 | 测试准确描述 `--env` / `--config` 的数据库隔离语义 |
| 路径函数 | 建立 env-aware DB 路径 | 扩展 `output_paths.py` | 三个 env 路径不同且不指向旧主库 |
| 配置模型 | 配置支持环境覆盖与显式 config | 扩展 `DataConfig`、`ConfigManager(env=...)`、`ConfigManager(config_file=...)`；新增 env 配置文件 | `database_path` 解析为绝对路径；旧 `db_path` 不生效 |
| DataManager 生命周期 | 消除单例串库风险 | 取消 `DataManager` 单例；裸 `DataManager()` 只复用当前 env；增加 `DataStore` / `init_database()` path fail-fast | 不同 env 不静默串库；未初始化 env 报错 |
| CLI env/config | 命令显式选择 env/config | 增加 `--env` / `--config` 显式入口；命令按 resolved env 校验 | 各命令只向对应 env DB 写入业务数据；report 可读任意 env |
| Optuna/report/export | 跟随当前 env DB | Optuna URL、report/export 读取或写入当前 env DB | 不跨 env 读写 DB；不改变 report/export 业务语义或产物结构 |
| 并行 worker | 子进程继承当前 env DB | backtest 并行优化 worker 显式传入当前 resolved DB path | 并行 Optuna 与 run/study 同库 |
| 数据迁移 | 现有主库移入 backtest env | checkpoint、直接移动 DB、integrity check | backtest/report 可读旧数据 |
| 回归验证 | 全链路测试 | lint、mypy、pytest、report build | 无新写入旧主库；各 env 数据隔离 |
| 收尾 | 移除旧库路径 | 删除旧 `db_path`、`quant_shared.db` fallback 和旧测试假设 | 文档与测试一致 |

## 执行任务清单

建议按以下顺序执行，避免一次性大改导致定位困难：

| 顺序 | 任务 | 产出 |
|---|---|---|
| 准备 | 新增或更新护栏测试，先允许 xfail | 测试描述 `--env` / `--config` 数据库隔离目标行为 |
| 路径 | 扩展 env-aware 路径函数 | `database_path(env)` 可用 |
| 配置 | 扩展 DataConfig 和 ConfigManager env/config API | env 配置和显式 config 均解析为绝对 DB 路径；旧 `db_path` 不再支持 |
| 生命周期 | 取消 DataManager 单例，增加 DataStore / `init_database()` fail-fast | 不同 env 不静默串库；测试 reset fixture 可控切换临时 DB |
| CLI | 各命令增加并校验 `--env` / `--config` | 命令写入对应 env DB；report 读取当前 env DB |
| 裸 fallback | 约束 report/data_feed/exporter 的裸 `DataManager()` | 只能复用当前 env；未初始化 env 报错 |
| Optuna/report/export | 跟随当前 env DB，report/export 不改变业务语义 | report 与 Optuna 不读错库；export 不读写错库；report 输出路径保持现状 |
| 并行 | worker 显式继承当前 resolved DB path | 并行优化不写错库 |
| 迁移 | 直接移动现有主库到 backtest DB | 旧数据可读 |
| 验证 | 跑测试与旧路径扫描 | 无旧主库新写入 |
| 收尾 | 转正 xfail、清理旧配置字段 | 文档与测试一致 |

## 禁止事项

实现阶段禁止做以下事情：

- 不新增 `paper` environment。
- 不拆分领域 DB。
- 不裁剪不同 environment 的 schema。
- 不引入多数据库 join。
- 不重构 report 数据结构。
- 不改策略逻辑。
- 不改 live/test 的交易语义。
- 不删除现有 backtest 历史数据。
- 不让 `report` 跨环境读取或 fallback 到 backtest。
- 不通过环境变量隐式切换 env。
- 不通过旧 `db_path` 兼容旧路径。
- 不把 `project_data/database/quant_shared.db` 作为 fallback 继续写入。
- 不让 `--config` 绕过 resolved environment 校验；显式 config 必须声明环境和数据库路径，并满足命令允许范围。

## 提交前检查

实现完成后至少执行：

```bash
ruff check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

并额外检查：

```bash
test ! -e project_data/database/quant_shared.db
sqlite3 project_data/database/backtest/quant.db "PRAGMA integrity_check;"
```

还需要人工或测试确认：

- `export --env backtest/test/live` 读写对应 env DB；不规定 export 的业务环境归属。
- `backtest --env backtest` 写入 backtest DB。
- `report --env backtest/test/live --build` 读取对应 env DB；输出目录本阶段保持现状，不做 env 隔离验收。
- `test --env test` 写入 test DB。
- `live --env live` 写入 live DB。
- 裸 `DataManager()` 在 env 未初始化时报错。
- 新代码不再创建 `project_data/database/quant_shared.db`。

## 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| DataManager 单例未清理 | env 切换仍串库 | 取消单例并加测试 |
| CLI 解析前创建 ConfigManager | logging 初始化抢先绑定错误 env | logging 基础配置与数据 env 解耦，或解析 `--env` / `--config` 后再初始化完整配置 |
| 裸 DataManager 抢先初始化 | data_feed/report fallback 绑定错误库 | 未初始化 env 时裸 `DataManager()` 报错；已初始化后只复用当前 env |
| peewee 全局 database 重复初始化 | 同进程连接错库 | 增加 fail-fast 检查，单进程只绑定一个 env |
| Optuna storage 写错 DB | study 与 run 不在同库 | `get_optuna_url()` 跟随当前 env，并测试 |
| 并行 worker 未继承 env | worker 写错库或无法写库 | worker initializer 显式传入 resolved DB path |
| report 读到其它 env DB | 报告数据污染 | report 只读 resolved env 对应 DB，不 fallback |
| report 产物覆盖 | 不同 env 报告 JSON/HTML 互相覆盖 | 第一阶段可接受风险；本阶段只隔离数据库，不隔离 report/log/cache 等产物 |
| 旧 `quant_shared.db` 继续生成 | 迁移不彻底 | 新增旧主库禁止写入测试 |
| test/live 历史数据不迁移 | 旧库中历史 test/live 记录不会进入新 test/live DB | 迁移前外部备份；第一阶段明确不迁移 |
| 旧库 live 数据误迁移 | live 数据被错误并入新 live DB 或 backtest DB | 第一阶段不迁移 test/live 历史数据；如需追溯依赖外部备份 |

## 验收标准

第一阶段完成后必须满足：

- `project_data/database/backtest/quant.db` 是 resolved env `backtest` 的唯一 DB。
- `project_data/database/test/quant.db` 是 resolved env `test` 的唯一 DB。
- `project_data/database/live/quant.db` 是 resolved env `live` 的唯一 DB。
- 三个 env 可以复用同一套 schema；不要求按环境裁剪表。
- 常规 CLI 必须显式传 `--env` 或 `--config`，并解析出合法 resolved environment。
- `export` 允许 resolved env 为 `backtest/test/live`，并且只读写当前 env DB。
- `backtest` 只允许 resolved env 为 `backtest`。
- `test` 只允许 resolved env 为 `test`。
- `live` 只允许 resolved env 为 `live`。
- `report` 允许 resolved env 为 `backtest/test/live`，并且只读取当前 env DB。
- report 构建输出目录本阶段保持现状，不按 env 隔离；不同环境产物覆盖属于第一阶段可接受风险。
- `project_data/database/quant_shared.db` 不再被新代码创建或写入。
- 旧 `db_path` 字段不再被配置模型接受或作为 fallback 使用。
- 裸 `DataManager()` 未初始化 env 时直接报错，已初始化时只复用当前 env。
- `test --env test` 或等价 `--config` 只写 test realtime 数据和数据库日志。
- `live --env live` 或等价 `--config` 只写 live realtime 数据和数据库日志。
- report 构建能读取迁移后的 backtest 历史数据。
- Optuna 图表能从当前 env DB 正常生成；backtest 优化写入 backtest DB。
- pytest 使用临时 DB，不污染 `project_data`。
- lint、mypy、pytest、contract、report build 全部通过。

## 后续方向

环境隔离完成后，再考虑领域拆分：

```text
project_data/database/backtest/
├── market_metadata.db
├── results.db
└── optuna.db

project_data/database/live/
├── state.db
├── trades.db
└── audit.db
```

但这属于第二阶段，只有在环境隔离稳定后再做。
