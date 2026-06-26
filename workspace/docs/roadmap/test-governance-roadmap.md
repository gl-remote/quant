# 测试体系治理规划

> 类型：Roadmap / 分阶段实施规划
> 状态：核心治理阶段性完成（阶段 A-C 已完成，阶段 D/E 阶段性完成；阶段 F coverage 基线与 CI 收口待讨论）
> 创建日期：2026-06-26
> 会话交接：本规划来自 2026-06-26 关于 `workspace/tests`、coverage、pre-commit、`scripts/test.sh` 的连续讨论；后续 AI Agent 应先阅读本文的「交接说明」和「隐藏规则」，再执行任何改动。

## 背景

当前测试体系已经具备较好的基础：

- `workspace/tests` 按业务域组织，当前 fast suite 可收集 405/408 个测试，3 个 `slow` / `local_data` 测试默认排除。
- 策略切面测试较细，`strategies/strategy_aspects` 已覆盖大量边界条件，并已补充跨切面风控不变量。
- `.pre-commit-config.yaml` 已按业务域增量触发验证。
- `scripts/test.sh` 是验证内容层的单一入口，pre-commit 只负责触发层。
- 近期测试治理已分阶段提交为：
  - `182fb06 test: add verification stages and shared helpers`
  - `d5f7f9b test: add backtest statistics invariants`
  - `8cae76d test: add datafeed visibility invariants`
  - `fda3349 test: add risk aspect invariants`

已完成的修整包括：

- `pyproject.toml`
  - pytest 默认不再自动跑全仓库 coverage。
  - `pythonpath` 调整为 `workspace`，单文件 pytest 不再依赖额外 `PYTHONPATH`。
  - 新增 `integration`、`local_data` markers。
- `workspace/tests/backtest/test_parallel.py`
  - 并行优化器测试标记为 `integration`。
  - 真实 K 线依赖测试标记为 `local_data`。
  - 抽出 `real_5m_dataset` fixture。
  - `test_empty_search_space` 改为内存 Optuna study，避免触碰本机全局数据库。
- `workspace/tests/strategies/runtime/test_data_feed.py`
  - 删除演示式 `print()` 和 `__main__` 手动运行块。
  - `generate_test_bars()` 改为固定时间基准。
  - 为原本偏演示的测试补关键断言。

验证命令已通过：

```bash
uv run ruff check workspace/tests/strategies/runtime/test_data_feed.py workspace/tests/backtest/test_parallel.py
uv run pytest workspace/tests/strategies/runtime/test_data_feed.py --tb=short -q
uv run pytest workspace/tests/backtest/test_parallel.py -m "not slow and not local_data" --tb=short -q
uv run pytest workspace/tests --collect-only -q
```

## 核心判断

测试治理不要追求一个漂亮的全仓库覆盖率数字，而要建立风险分层：

- 快速单元测试用于日常开发和 pre-commit。
- 集成测试用于跨模块语义验证。
- `slow` / `local_data` 测试用于本机或专门回归，不进入默认门禁。
- coverage 应是专门入口或 CI job，不应回到 pytest 默认 `addopts`，也不应塞进 pre-commit 域 hook。
- `scripts/test.sh` 已拆分为稳定入口与 `scripts/test/` 子脚本；coverage 和分层测试已有专用入口。

## 交接说明

后续 AI Agent 接手时，先执行以下阅读顺序：

```text
.trae/rules/project_rules.md
.pre-commit-config.yaml
scripts/test.sh
workspace/docs/roadmap/test-governance-roadmap.md
pyproject.toml
workspace/tests/conftest.py
workspace/tests/backtest/test_parallel.py
workspace/tests/strategies/runtime/test_data_feed.py
```

接手后的第一步不要直接改代码，先用 git 确认状态：

```bash
git status --short
git log --oneline -5
```

如果工作区已有用户改动，不要覆盖。先阅读改动，再决定是否继续。

本文规划建议分阶段实施。每个阶段应单独提交，避免把机械拆分、coverage 行为改变、测试重构混在同一个提交里。

## 隐藏规则

这些规则不是普通需求，而是后续 AI Agent 执行时必须遵守的约束：

- 所有 Python 命令必须以 `uv run` 开头，例如 `uv run pytest ...`、`uv run python -m mypy ...`。
- 不要直接调用裸 `python`、`pytest`、`pip`。
- `ruff` 可直接运行，也可用 `uv run ruff ...`。
- coverage 不得回到 pytest 默认 `addopts`；提交门禁通过 `scripts/test.sh all <domain>` 按业务域执行 `fail-under`。
- 不要把 coverage 直接塞进 `.pre-commit-config.yaml` 的域 hook。
- `.pre-commit-config.yaml` 是触发层，`scripts/test.sh` 是内容层。改验证分工前必须先阅读两个文件顶部说明。
- 保留 `bash scripts/test.sh ...` 作为外部稳定入口，pre-commit 不应因为脚本拆分而修改 entry。
- `scripts/test.sh` 拆分时先做机械拆分，不要同时改行为。
- `slow` 和 `local_data` 不得进入默认 unit 测试口径。
- 真实行情数据、`project_data/market_data/csv`、`project_data/database/quant_shared.db` 等本机数据状态不得成为 fast suite 的隐式依赖。
- 文档标题不要使用手动编号，例如不要写 `## 1. 背景`；使用纯标题层级。
- 不要为了提升 coverage 而写无意义的快照测试或只覆盖 import 的测试。
- 对量化核心逻辑，优先测试业务不变量，而不是只测试实现细节。
- 未经用户明确要求，不要自动 commit；如果用户要求 commit，按仓库 Git 安全协议执行。

## 验证体系目标结构

长期目标是保持一个稳定入口，内部拆分职责：

```text
scripts/
  test.sh
  test/
    env.sh
    domains.sh
    python.sh
    web.sh
    precommit.sh
```

职责边界：

| 文件                          | 职责                                                              |
| --------------------------- | --------------------------------------------------------------- |
| `scripts/test.sh`           | 兼容入口，解析 `stage/domain` 并 dispatch                               |
| `scripts/test/env.sh`       | 根目录、颜色、公共变量、`WEB_DIR`                                           |
| `scripts/test/domains.sh`   | `resolve_src`、`resolve_test`、`MYPY_TARGETS`、`COVERED_PREFIXES`  |
| `scripts/test/python.sh`    | `run_lint`、`run_format`、`run_type`、`run_unit`、`run_coverage`       |
| `scripts/test/web.sh`       | report web 的 eslint、tsc、vitest                                  |
| `scripts/test/precommit.sh` | `_uncovered` 盲区提示逻辑                                             |

外部命令保持不变：

```bash
bash scripts/test.sh
bash scripts/test.sh all strategies
bash scripts/test.sh unit backtest
bash scripts/test.sh lint common
```

## 阶段拆分

### 阶段 A：机械拆分 `scripts/test.sh`

状态：已完成（本会话已机械拆分，外部入口保持兼容）。

目标：只拆文件，不改变行为。

要求：

- 新建 `scripts/test/` 目录。
- 将现有函数按职责移动到子脚本。
- `scripts/test.sh` 保留原入口和原用法。
- `.pre-commit-config.yaml` 不改 entry。
- `_uncovered` 输出保持一致。
- report 域前后端联动逻辑保持一致。
- contracts 域独立 pytest 工作目录逻辑保持一致。

建议验证：

```bash
bash scripts/test.sh lint common
bash scripts/test.sh format strategies
bash scripts/test.sh type backtest
bash scripts/test.sh unit strategies
bash scripts/test.sh all cli
bash scripts/test.sh _uncovered pyproject.toml scripts/test.sh
```

如需全量验证：

```bash
bash scripts/test.sh
```

注意：全量验证可能耗时较长，执行前确认是否必要。

### 阶段 B：增加 coverage 专用入口

状态：已完成（本会话已新增 `coverage` stage，初期只报告、不设 fail-under）。

目标：建立 coverage 能力，但不影响默认测试和 pre-commit。

建议新增 stage：

```bash
bash scripts/test.sh coverage
bash scripts/test.sh coverage common
bash scripts/test.sh coverage strategies
bash scripts/test.sh coverage backtest
```

coverage 口径建议：

- 默认排除 `slow`、`local_data`。
- 不跑真实数据依赖。
- 不把 coverage 写回 pytest 全局 `addopts`。
- 初期只报告，不设置 fail-under。

建议命令形态：

```bash
uv run python -m pytest <tests> \
  -m "not slow and not local_data" \
  --cov=<src> \
  --cov-report=term-missing:skip-covered \
  -q --tb=short
```

contracts 域要保留独立目录执行方式，避免 `tests.conftest` 冲突。

### 阶段 C：建立分层测试命令

状态：已完成（本会话已新增 `integration`、`slow`、`local-data` stage，并让 `unit` 默认排除 `slow`、`local_data`）。

目标：让测试语义从“unit 一个筐”变成清晰分层。

建议 stage 或选择器：

```bash
bash scripts/test.sh unit strategies
bash scripts/test.sh integration backtest
bash scripts/test.sh local-data backtest
bash scripts/test.sh slow backtest
```

已在 `unit` 内固定排除：

```bash
-m "not slow and not local_data"
```

该行为已经改变当前 `run_unit` 口径：`unit` 代表 fast tests，`slow` / `local_data` 需显式 stage 执行。

建议 markers：

- `unit`：可选，不强制，当前多数测试可默认为 unit。
- `integration`：跨模块但不依赖本机真实数据。
- `slow`：耗时明显的测试。
- `local_data`：依赖 `project_data/market_data/csv`、`project_data/database/quant_shared.db` 或其他本机真实数据状态。

### 阶段 D：抽取测试 helpers

状态：阶段性完成（本会话已完成首轮低风险抽取：`backtest_records.py`、`configs.py`、`market_data.py`、`risk.py`，`conftest.py` 保留 fixture 暴露和 pytest 生命周期控制；固定止盈/止损和 cooldown 风控测试已小步迁移；DataFeed 局部构造 helper 已收敛在测试文件内，后续如继续增长再外提）。

目标：降低测试重复，增强失败信息。

建议新增目录：

```text
workspace/tests/helpers/
  market_data.py
  backtest_records.py
  configs.py
  assertions.py
```

迁移原则：

- 先新增 helper，再逐步迁移重复最多的测试。
- 不要一次性大搬所有测试。
- `conftest.py` 只保留 fixture 暴露和 pytest 生命周期控制。
- helper 不应依赖真实数据、不应隐式读 `project_data` 下的本机数据文件。

优先迁移对象：

- `workspace/tests/conftest.py` 中的 K 线构造、回测记录构造、配置字典。
- `strategy_aspects/risk` 下重复的 `_make_state`、`_MockCtx`、风险断言。
- DataFeed 测试中的 DataFrame 构造函数。

建议添加语义断言 helper：

```python
def assert_single_reason(reasons):
    assert len(reasons) == 1
    return reasons[0]
```

后续可逐步替换 `assert len(...) == 1` 风格。

### 阶段 E：补核心不变量测试

状态：阶段性完成（已补充回测统计不变量；已从 `workspace/tests/strategies/runtime/test_data_feed.py` 补充 DataFeed 时间可见性不变量，覆盖重复查询、查询顺序、lookback 单调性、高周期 forming 不偷看未来、指标确定性和 cache 隔离；已在 `workspace/tests/strategies/strategy_aspects/test_cross_cutting.py` 补充策略风控边界不变量）。

目标：覆盖量化系统最容易产生“看起来能跑但结果错误”的场景。

优先方向：

#### 回测统计不变量

目标文件可从 `workspace/tests/backtest/test_vnpy_backtest_engine.py` 开始。

应覆盖：

- 全亏损序列：收益、终值、盈利天数符号正确。
- 全盈利序列：收益、终值、亏损天数符号正确。
- balance 穿零：Sharpe、return、drawdown 不反号。
- 手续费和滑点增加：净收益不能上升。
- 空交易和空 daily：不崩溃、不产生虚假正收益。
- long / short 对称场景：价格路径反向时 PnL 符号对称。

#### DataFeed 时间可见性不变量

目标文件可从 `workspace/tests/strategies/runtime/test_data_feed.py` 开始。

核心判断：DataFeed 在完成数据构建后，`build_context` / `get_data` / 高周期聚合视图应尽量表现为“给定输入数据 + 给定 current\_time → 确定输出”的纯函数。也就是说，测试重点不应只证明 DataFeed 能跑通，而应证明同一份构建好的 feed 在任意读取顺序、重复读取、不同窗口组合下都返回一致且不偷看的结果。

优先把 DataFeed 测试拆成两层：

- 构建层：用固定 K 线、固定指标需求、固定事件构造 DataFeed。
- 查询层：围绕纯查询语义做表驱动测试，不依赖真实数据、不访问磁盘、不修改外部状态。

应覆盖：

- `build_context(current_time=T)` 不可见 `T` 之后数据。
- 高周期 future bar 不可提前可见。
- forming bar 只能由已到达 base bars 聚合。
- 同一时间点多次读取结果一致。
- 增量 feed 与一次性 history 在同一时间点语义一致。
- 查询顺序不影响结果：先查 `10:10` 再查 `10:05`，应与直接查 `10:05` 一致。
- 重复查询无副作用：同一 `current_time` 连续调用 `build_context`，bar 数量、OHLC、指标值、事件列表应一致。
- lookback 窗口单调性：同一时间点下，较大 lookback 的尾部应包含较小 lookback 的完整结果。
- 指标计算确定性：同一数据和同一 `IndicatorSpec` 产生相同列名和相同尾部指标值。
- 事件过滤确定性：事件只应按 `current_time` 和窗口可见性出现，不因调用顺序改变。
- 多周期一致性：base 周期推进时，高周期 forming/complete 状态只由已到达 base bars 决定。
- cache 隔离：全局 DataFeed cache 测试必须显式 `clear_cache()`，不能让缓存状态影响纯查询断言。

建议新增测试 helper：

```python
def build_deterministic_feed(requirements: DataRequirements, bars: list[Bar]) -> DataFeed:
    """用固定数据构造 DataFeed，供纯查询语义测试复用。"""
```

测试写法建议采用表驱动，例如同一 feed 上枚举多个 `current_time`、期望可见 bar 数、期望最新 bar 时间、期望 forming/complete 状态。重点验证“语义不变量”，不要只验证实现细节。

#### 策略风控不变量

目标目录：`workspace/tests/strategies/strategy_aspects/`。

应覆盖：

- 无持仓时 exit 风控不触发。
- 有持仓时 entry cooldown 不错误拦截平仓。
- 多个 advisory 写入互不覆盖。
- long / short 止盈止损边界对称。
- ATR 为 `None` 或 `0` 时不触发，且不污染 diagnostics。

### 阶段 F：coverage 基线和阈值

状态：待讨论后实施（coverage stage 已建立，当前仍只报告、不设 fail-under；下一步应先确定 coverage 的使用目的和阈值策略）。

目标：先建立可读报告，再逐步设置阈值。

不建议设置全仓库 `--cov-fail-under=80`；当前策略是只设置业务域阈值。

当前业务域 coverage 基线与提交阻塞阈值：

| Domain       | 当前基线           | fail-under | 说明                                           |
| ------------ | -------------- | ---------- | -------------------------------------------- |
| `common`     | 89 passed，63%  | 60         | 纯函数较多，后续可作为优先提高对象。                       |
| `config`     | 20 passed，92%  | 90         | 配置 schema/manager 覆盖较高，可保持较高阈值。             |
| `data`       | 72 passed，54%  | 50         | 数据域先放宽，避免 datasource / 外部桥接路径今天阻塞。         |
| `backtest`   | 26 passed，53%  | 50         | 已补统计不变量；外部引擎/桥接路径不应硬追高。                 |
| `strategies` | 171 passed，77% | 75         | 已覆盖 DataFeed、strategy_aspects、MA 策略等核心路径。 |
| `report`     | 14 passed，29%  | 25         | Python report 当前偏低，web 由前端工具链兜底。            |
| `cli`        | 7 passed，31%   | 30         | CLI 入口当前覆盖偏低，先以不下降为主。                    |
| `contracts`  | 1 passed，65%   | 60         | 合同包独立 pytest cwd，保持独立 coverage 口径。          |

非 Python / 特殊域：

- `report-web`：暂不接入 Python coverage，仍由 eslint / tsc / vitest / build 兜底。
- 全域 `coverage`：依次执行各业务域 coverage 阈值检查，但不计算、不阻塞全仓库整体百分比。

建议先按模块观察：

| 模块                                      | 初期目标           | 说明                |
| --------------------------------------- | -------------- | ----------------- |
| `workspace/common`                      | 70%+           | 纯函数多，应逐步提高到 85%+  |
| `workspace/strategies/strategy_aspects` | 75%+           | 信号和风控语义核心         |
| `workspace/strategies/runtime`          | 60%+           | 状态复杂，优先覆盖关键路径     |
| `workspace/backtest`                    | 55%+           | 先覆盖统计和结果转换，再扩展引擎  |
| `workspace/data`                        | 60%+           | 优先模型、store、一致性校验  |
| `workspace/report`                      | 分 Python 与 web | 前端已有 vitest，应独立统计 |

阈值策略：

- 使用业务域阈值，不设置全仓库整体 coverage 阈值。
- `all <domain>` 代表 lint + format + type + unit + coverage fail-under。
- pre-commit 触发对应业务域的 `all <domain>`，覆盖率不足会阻塞提交。
- 阈值先按当前基线下沿设置，确保既有代码今天不会因为历史覆盖率阻塞；明天起新增改动需要维持或提高对应业务域覆盖率。
- 后续按 domain 逐步提高阈值，不强求所有域相同。

原则：

- 覆盖率用于防止核心域继续下滑，不用于追求全仓库漂亮数字。
- 观察稳定后按 domain 设置低阈值。
- 不同 domain 阈值不同，不强求全仓库一个数字。
- 对 vnpy / tqsdk 外部桥接层不要硬追高 coverage。

## 与 pre-commit 的关系

`.pre-commit-config.yaml` 当前设计正确，不建议推翻。

原则：

- pre-commit 仍按业务域增量触发，只跑被改业务域的 `all <domain>`。
- `all <domain>` 当前代表 lint + format + type + unit + coverage fail-under。
- 不在 pre-commit 中设置全仓库整体 coverage 阈值。
- 不在 pre-commit 中默认跑 `slow` 或 `local_data`。
- `tests/<domain>/` 改动也触发对应业务域 hook，避免只改测试时绕过 coverage 门禁。
- 根级文件仍由 `_uncovered` 提示，不直接阻塞。

如果未来要增强根级文件处理，建议先只增强提示文案，例如当 `pyproject.toml` 或 `scripts/test.sh` 改动时提示运行：

```bash
bash scripts/test.sh
uv run pytest workspace/tests --collect-only -q
```

不要直接让 `_uncovered` 阻塞提交，除非用户明确要求改变 pre-commit 策略。

## 与 CI 的关系

CI 应承担 pre-commit 不做的全量兜底：

- 全量 lint / format / type。
- fast tests：排除 `slow`、`local_data`。
- coverage report。
- 前端 lint / type / vitest / build。
- 可选夜间或手动触发 local data 回归。

建议 CI 不依赖本机 `project_data` 数据目录。真实数据测试应显式标记并在专门环境运行。

## 推荐命令清单

日常快速测试：

```bash
uv run pytest workspace/tests -m "not slow and not local_data" --tb=short
```

策略专项：

```bash
uv run pytest workspace/tests/strategies --tb=short
```

DataFeed 专项：

```bash
uv run pytest workspace/tests/strategies/runtime/test_data_feed.py --tb=short -q
```

并行测试 fast 子集：

```bash
uv run pytest workspace/tests/backtest/test_parallel.py -m "not slow and not local_data" --tb=short -q
```

收集检查：

```bash
uv run pytest workspace/tests --collect-only -q
```

coverage：

```bash
bash scripts/test.sh coverage strategies
bash scripts/test.sh coverage backtest
bash scripts/test.sh coverage
```

## 风险和注意事项

### shell 拆分风险

`scripts/test.sh` 运行在 pre-commit 中。拆分后路径解析必须稳定，不能依赖当前 shell 的工作目录。

建议所有子脚本通过入口脚本 source，并统一使用 `ROOT_DIR`。

### contracts 域风险

`workspace/packages/python-contracts/tests/` 有独立 `conftest.py`，当前脚本通过进入包目录运行 pytest 来避免 `tests.conftest` 冲突。拆分时必须保留这个特殊处理。

### report 域风险

`report` 域包含 Python 和前端。当前流程决策是改 `workspace/report/` 任意文件都跑 Python 与前端验证。拆分时必须保留。

### coverage 噪音风险

当前不应恢复全仓库默认 coverage。全仓库 coverage 数字容易被外部桥接、未测脚本、前端无关路径稀释，导致指标不可解释。

### 测试重构风险

抽 helpers 时不要大规模重排测试目录。先抽复用代码，再逐步替换调用。每次迁移后跑对应 domain 测试。

## 建议提交顺序

每个阶段单独提交：

```text
refactor(test): split verification script helpers
feat(test): add coverage stage to verification script
test: add core backtest invariants
test: extract shared test helpers
test: expand datafeed visibility invariants
ci: add fast coverage reporting
```

实际 commit message 应根据具体改动调整。

## 当前状态快照

截至本次文档同步时：

- 最新相关提交：`fda3349 test: add risk aspect invariants`
- 全测试收集：405/408 tests collected，3 个 `slow` / `local_data` 测试默认排除
- 默认 pytest 已不含 coverage
- 已注册 markers：`slow`、`integration`、`local_data` 等
- `scripts/test.sh` 已保留兼容入口，内部拆分为 `scripts/test/` 子脚本。
- coverage stage 已建立，并按业务域设置 fail-under；全域 coverage 只串行业务域阈值，不设置全仓库整体阈值。
- `unit` 已固定为 fast tests，默认排除 `slow`、`local_data`。
- 已新增 `integration`、`slow`、`local-data` stage。
- `workspace/tests/helpers/` 已建立，并已首轮抽取回测记录、配置字典、行情数据和风控测试构造 helpers。
- 回测统计不变量已补充全盈利、全亏损、成本增加、空 daily、缺列 daily 等场景。
- DataFeed 时间可见性不变量已补充重复查询、查询顺序、lookback 单调性、高周期 forming 不偷看未来、指标确定性和 cache 隔离。
- 策略风控核心不变量已补充无持仓 exit、持仓 cooldown、风险 diagnostics、long/short 对称、ATR None/0 等边界。
- 当前业务域 fail-under：common 60、config 90、data 50、backtest 50、strategies 75、report 25、cli 30、contracts 60。
- pre-commit 的业务域 hook 已包含对应 `tests/<domain>/` 路径，测试改动也会触发该域门禁。

## 完成定义

本规划完成时应满足：

- `scripts/test.sh` 已保留兼容入口，内部拆分为 `env.sh`、`domains.sh`、`python.sh`、`web.sh`、`precommit.sh`。
- pre-commit 仍按业务域增量触发，并通过 `all <domain>` 执行该域 coverage fail-under。
- coverage 有专用入口，不污染默认 pytest。
- `slow` / `local_data` 与 fast suite 已通过 `unit`、`slow`、`local-data` stage 隔离。
- 核心量化不变量测试已阶段性覆盖回测统计、DataFeed 时间可见性、策略风控边界。
- `conftest.py` 不再继续膨胀，常用测试构造迁移到 helpers。
- CI 与本地命令口径一致，coverage 报告可解释。
