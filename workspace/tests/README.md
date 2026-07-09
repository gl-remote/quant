# 测试体系设计与规范

本文记录 `workspace/tests/` 的组织方式、运行入口、覆盖率门禁和新增测试规范。它是测试目录内的就近说明；更完整的治理路线见 `docs/archive/infra/test-governance-roadmap.md`。

## 核心原则

- 测试按业务域组织，测试目录应尽量与源码业务域一一对应。
- `scripts/test.sh` 是验证内容层的单一入口；`.pre-commit-config.yaml` 只负责按改动路径触发对应业务域。
- fast suite 不依赖本机真实数据，不隐式读取 `project_data/`。
- `slow`、`local_data` 测试必须显式标记，并从默认 `unit` 中隔离。
- coverage 按业务域设置阈值，不设置全仓库整体阈值。
- 量化核心逻辑优先测试业务不变量，而不是只测试实现细节。

## 目录结构

测试路径选择规则：

- 改某个业务域源码时，优先在 `workspace/tests/<domain>/` 下补测试。
- 跨域行为测试放在更接近业务语义的域；如果无法归属，优先选择触发行为的一侧，而不是新建杂项目录。
- 公共测试构造放 `helpers/`，不要放进具体业务域测试目录。
- pytest 生命周期、临时环境、全局 reset 放 `conftest.py`，不要放进 helper。

```text
workspace/tests/
  common/          # common 公共函数、指标、schema、符号工具
  config/          # 配置读取、默认值、校验
  data/            # 数据模型、store、一致性校验、数据管理边界
  backtest/        # 回测结果、统计、优化、walk-forward
  strategies/      # 策略、DataFeed、strategy_aspects
  report/          # Python report 格式化与查询输出
  cli/             # CLI 路由和命令分发
  helpers/         # 测试构造 helper，不放 pytest 生命周期逻辑
  conftest.py      # 共享 fixture 和 pytest 生命周期控制
```

特殊目录：

- `workspace/packages/python-contracts/tests/` 是 contracts 包自己的测试目录，不放在 `workspace/tests/contracts/` 下；执行时需要使用独立 cwd，避免 `tests.conftest` 冲突。
- `workspace/report/web/` 是前端测试体系，使用 eslint / tsc / vitest，不复用 Python coverage。

## 测试分层

### unit

默认 fast tests，排除：

```bash
-m "not slow and not local_data"
```

运行：

```bash
bash scripts/test.sh unit <domain>
```

例如：

```bash
bash scripts/test.sh unit strategies
bash scripts/test.sh unit backtest
```

### integration

跨模块语义验证，但不依赖本机真实数据。

```bash
bash scripts/test.sh integration <domain>
```

### slow

耗时明显的测试，必须标记：

```python
@pytest.mark.slow
```

运行：

```bash
bash scripts/test.sh slow <domain>
```

### local_data

依赖本机真实数据或 `project_data/` 状态的测试，必须标记：

```python
@pytest.mark.local_data
```

运行：

```bash
bash scripts/test.sh local-data <domain>
```

`local_data` 不得进入默认 unit、pre-commit 或 fast CI。

标记选择规则：

- 能用内存数据、临时文件或 mock 解决的测试，不要标记 `local_data`。
- 只有确实需要本机行情、SQLite 真实库或 `project_data/` 状态时，才标记 `local_data`。
- 只有耗时本身不可避免时，才标记 `slow`；不要用 `slow` 掩盖测试设计不合理。
- `integration` 可以和普通 fast suite 共存，但如果它同时依赖真实数据，必须额外标记 `local_data`。
- 新增 marker 前先确认 `pyproject.toml` 已注册，避免破坏 `--strict-markers`。

## 统一运行入口

日常按业务域验证：

```bash
bash scripts/test.sh all <domain>
```

`all <domain>` 当前包含：

1. ruff lint
2. ruff format check
3. mypy
4. fast unit tests
5. coverage fail-under

常用命令：

```bash
bash scripts/test.sh all common
bash scripts/test.sh all config
bash scripts/test.sh all data
bash scripts/test.sh all backtest
bash scripts/test.sh all strategies
bash scripts/test.sh all report
bash scripts/test.sh all cli
bash scripts/test.sh all contracts
```

全量验证：

```bash
bash scripts/test.sh
```

收集检查：

```bash
uv run pytest workspace/tests --collect-only -q
```

按改动选择命令：

| 改动场景 | 最小建议验证 |
| --- | --- |
| 改 `workspace/<domain>/` | `bash scripts/test.sh all <domain>` |
| 改 `workspace/tests/<domain>/` | `bash scripts/test.sh all <domain>` |
| 改 `workspace/tests/helpers/` | 运行使用该 helper 的相关域；不确定时运行 `bash scripts/test.sh` |
| 改 `workspace/tests/conftest.py` | `bash scripts/test.sh` 和 collect-only |
| 改 `scripts/test*.sh` 或 `.pre-commit-config.yaml` | shell 语法检查 + 至少两个代表域的 `all <domain>` + collect-only |
| 改 `pyproject.toml` pytest / marker / pythonpath 配置 | `bash scripts/test.sh` 和 collect-only |
| 改 report Python | `bash scripts/test.sh all report`，会同时跑前端验证 |
| 改 report web | `bash scripts/test.sh all report` 或对应前端 stage |
| 改 contracts 包 | `bash scripts/test.sh all contracts` |
| 改根级 `workspace/tests/test_*.py` / `README.md` / `__init__.py` | commit 会触发 `bash scripts/test.sh` |
| 改根级文件或文档 | 根据影响面人工选择；至少保留 `_uncovered` 提示可见 |

## Coverage 门禁

coverage 按业务域设置 `fail-under`，不使用全仓库整体阈值。

当前阈值：

| Domain | fail-under | 说明 |
| --- | ---: | --- |
| `common` | 60 | 公共函数较多，后续可逐步提高 |
| `config` | 90 | 配置域覆盖率较高，保持较高阈值 |
| `data` | 50 | 数据源和外部桥接较多，先宽松 |
| `backtest` | 50 | 回测外部引擎和优化路径较多，先守住基线 |
| `strategies` | 75 | 策略核心域，阈值相对更高 |
| `report` | 25 | Python report 偏低，web 由前端测试兜底 |
| `cli` | 30 | CLI 薄封装较多，先守住基线 |
| `contracts` | 60 | 独立 contracts 包 |

运行某域 coverage：

```bash
bash scripts/test.sh coverage <domain>
```

运行全部业务域 coverage：

```bash
bash scripts/test.sh coverage
```

注意：全量 coverage 是逐个 domain 执行各自阈值，不计算、不阻塞全仓库整体百分比。

coverage 下降时的处理：

- 优先补业务语义测试，不要为了过阈值写 import-only 或无意义 snapshot。
- 如果新增代码属于外部桥接、CLI 薄封装或真实数据路径，先判断是否应排除到专项测试，而不是盲目追高覆盖率。
- 阈值调整必须更新 `scripts/test/domains.sh` 和本文档，并说明原因。
- 不要把 coverage 放回 `pyproject.toml` 的 pytest 全局 `addopts`。
- 不要引入全仓库整体 fail-under；只能按业务域治理。

## Pre-commit 关系

pre-commit 仍按业务域增量触发：

- 改 `workspace/<domain>/` 时，触发 `bash scripts/test.sh all <domain>`。
- 改 `workspace/tests/<domain>/` 时，触发对应业务域门禁。
- 改 `workspace/tests/helpers/`、`workspace/tests/conftest.py`、`workspace/tests/test_*.py`、`workspace/tests/README.md` 或 `workspace/tests/__init__.py` 时，触发 `bash scripts/test.sh` 全量验证。
- coverage 不写入 `pyproject.toml` 的 pytest 全局 `addopts`。
- 根级文件、脚本、非 tests 文档等由 `_uncovered` 提示，不直接阻塞；需要人工判断是否补跑验证。

触发层维护规则：

- 新增或移动测试目录时，要同步检查 `.pre-commit-config.yaml` 的 `files` 正则。
- `pass_filenames` 应保持 `false`，避免改动文件列表污染 `<domain>` 参数。
- `_uncovered` 只提示不阻塞；如果它提示了文件，提交前应在说明中写明已如何验证或为何无需验证。
- 不要让 pre-commit 跑 `slow` / `local_data`。

## Fixture 与 helper 规范

### conftest.py

`conftest.py` 只放：

- 共享 pytest fixture 暴露；
- pytest 生命周期控制；
- 临时文件、临时数据库路径等测试环境 fixture。

不要把复杂业务构造逻辑继续堆进 `conftest.py`。

### helpers/

`helpers/` 存放可复用测试构造：

- `market_data.py`：K 线、收盘价、DataFrame 构造；
- `backtest_records.py`：回测记录、交易记录、daily 记录构造；
- `configs.py`：配置字典构造；
- `risk.py`：策略风控测试状态、ctx、断言 helper。

helper 规则：

- 不读取真实数据文件；
- 不依赖 `project_data/`；
- 不隐式修改全局状态；
- 命名用 `make_*` 表示构造，用 `assert_*` 表示语义断言；
- helper 应保持小而明确，不为一次性场景过度抽象。

改 helper / conftest 时的额外要求：

- 改 `helpers/` 时，要确认哪些业务域引用了该 helper，并运行对应域验证。
- 改 `conftest.py` 时，默认视为影响所有测试，至少运行全量 collect-only。
- 新增 autouse fixture 前必须确认不会污染其他业务域或 contracts 独立测试。
- 全局缓存、单例、临时文件、数据库连接必须在 fixture 中显式 reset / cleanup。

## 新增测试规范

新增或修改测试时，优先考虑：

- 这个测试属于哪个业务域？应放到对应 `workspace/tests/<domain>/` 下。
- 是否依赖真实数据？如果是，必须标记 `local_data`，并提供 fast 替代或 mock。
- 是否耗时明显？如果是，必须标记 `slow`。
- 是否跨模块但不依赖真实数据？可标记 `integration`。
- 是否能表达业务不变量，而不是只验证实现细节？

推荐断言风格：

- 明确断言输出值、边界和副作用；
- 避免只断言“不报错”；
- 避免无意义 snapshot 或 import-only 测试；
- 对量化逻辑优先覆盖符号、方向、时间可见性、收益/风险边界。

场景化新增规则：

- 修 bug 时，先写能失败的回归测试，再修实现；如果无法先写，提交说明中要解释验证方式。
- 新增功能时，同步新增该业务域测试，并确保 coverage 不低于该域阈值。
- 修改 public API、配置 schema、报告 JSON 或 contracts 时，要补兼容性/序列化测试。
- 修改时间、缓存、随机数、全局单例相关逻辑时，要补重复调用和顺序无关测试。
- 修改路径逻辑时，要使用临时目录或 monkeypatch，不要依赖本机绝对路径。
- 修改 CLI 路由时，优先测试参数分发和 workflow 调用，不要在 CLI 单测里跑真实长流程。

## 量化核心不变量

重点守护以下类别：

### 回测统计

- 全盈利 / 全亏损序列统计符号正确；
- 空交易、空 daily 不产生虚假收益；
- 手续费或滑点增加时净收益不能上升；
- drawdown、return、Sharpe 不应反号。

### DataFeed 时间可见性

- `current_time=T` 时不可见 `T` 之后的数据；
- 高周期 forming bar 只能由已到达 base bars 聚合；
- 同一时间点重复查询结果一致；
- 查询顺序不影响过去视图；
- lookback 大窗口尾部包含小窗口完整结果；
- 全局 cache 测试必须显式隔离。

### 策略风控

- 无持仓时 exit 风控不触发；
- 有持仓时 entry cooldown 不拦截平仓；
- 多个 advisory 写入互不覆盖；
- long / short 止盈止损边界对称；
- ATR 为 `None` 或 `0` 时不触发，且不污染 diagnostics。

## 添加新业务域测试

如果新增业务域，需要同步维护：

1. `workspace/tests/<domain>/`；
2. `scripts/test/domains.sh` 中的 `resolve_src`、`resolve_test`、`resolve_coverage_min`；
3. `.pre-commit-config.yaml` 中对应业务域 hook；
4. 本 README 的目录和 coverage 阈值表；
5. 必要时更新 `docs/archive/infra/test-governance-roadmap.md`。

## 提交前建议

小改动按域验证：

```bash
bash scripts/test.sh all <domain>
```

涉及测试体系、脚本、pre-commit 或全局配置时，至少运行：

```bash
bash -n scripts/test.sh scripts/test/env.sh scripts/test/domains.sh scripts/test/python.sh scripts/test/web.sh scripts/test/precommit.sh
bash scripts/test.sh
uv run pytest workspace/tests --collect-only -q
```

涉及真实数据路径时，不要让 fast suite 依赖本机状态；真实数据回归应使用：

```bash
bash scripts/test.sh local-data <domain>
```

提交前如果出现以下情况，必须在提交说明或交付说明中交代验证策略：

- `_uncovered` 提示了改动文件；
- 有测试被标记为 `slow` 或 `local_data` 但没有实际运行；
- coverage 阈值被调整；
- 只运行了局部测试而没有运行对应业务域 `all <domain>`；
- 改动跨多个业务域，但只验证了其中一部分。

