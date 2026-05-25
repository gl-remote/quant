# 项目改进计划

> 版本: 0.2.0-dev | 最后更新: 2026-05-25 | 主线: 稳定盈利策略研发

---

## 一、项目现状

### 1.1 基础数据

| 指标 | 数值 |
|------|------|
| 生产代码 | 7,819 行 (48 个 .py 文件) |
| 测试代码 | ~2,000 行 (7 个 test 文件) |
| 测试用例 | **162** 个全通过，0 失败 |
| 覆盖率 | **51%** (2,098 stmts / 1,021 missed) |
| 策略类型 | 1 (双均线 MA) |
| CI | GitHub Actions (pytest + flake8) |
| Python | 3.10+ |

> 覆盖率下降因代码量增长 71%（4,568→7,819）但测试未同比扩充。核心策略模块 `ma_strategy.py` 覆盖率 99%。

### 1.2 模块架构（唯一权威源）

> 本节的模块架构图是项目结构的**唯一权威源**。其他文档（AI_BEHAVIOR_RULES.md、.memory_rules.md）不再维护独立的架构副本，引用此处。

```
main.py (19 行转发器) → cli/ (命令行子包)
├── cli/main.py          参数解析 + 命令分发 (149 行)
│   └── commands/        5 个子命令 (export/test/backtest/report/live)
├── strategies/          策略核心 (框架无关)
│   ├── core/            Strategy ABC + Bar/Signal/Fill/Position 类型
│   ├── bridges/         vnpy 桥接 + 天勤桥接 (协议转换层)
│   └── ma_strategy.py  双均线策略 (173 行, 99% 覆盖)
├── backtest/            回测引擎
│   ├── vnpy_backtest_engine.py  批量回测 + Walk-Forward (415 行)
│   ├── tq_backtest_engine.py    天勤 GUI 回测 (单标的图形化)
│   ├── data_loader.py           CSV 加载 / 窗口切分
│   └── types.py                 回测结果类型
├── data/                数据层
│   ├── store.py          SQLite + peewee ORM (405 行)
│   ├── models.py         Pydantic + ORM 模型 (246 行)
│   ├── manager.py        DataManager 统一入口
│   └── exporter.py       天勤 → CSV 导出
├── report/              报告层
│   ├── dataset_reporter.py     单数据集 JSON 报告
│   ├── comparison_reporter.py  多品种横向对比 + 排名
│   └── sql_reporter.py         SQLite 只读报告
├── common/              纯函数工具层 (零 I/O)
│   ├── constants.py     全局常量字典 (166 行, 60+ 常量)
│   ├── formulas.py      统一量化计算公式库 (437 行, 15+ 公式)
│   ├── schemas.py        Pandera Schema 定义 (124 行, 4 Schema)
│   ├── metrics.py        max_drawdown / sharpe_ratio
│   ├── stats.py          rank_by_key / summary_stats
│   └── formatting.py     百分比/浮点数格式化
└── config/              配置管理
    └── config_manager.py YAML 分层合并 + 校验 (220 行)
```

### 1.3 架构决策记录（唯一权威源）

> 本节的 10 项 ADR 是项目架构决策的**唯一权威源**。`.memory_rules.md` 不再维护 ADR 副本。

| 决策 | 说明 |
|------|------|
| **Strategy + Bridge 分离** | 策略核心不依赖任何框架，Bridge 做协议转换。同一份策略代码驱动 vnpy 回测和天勤实盘 |
| **复用官方回测引擎** | vnpy BacktestingEngine 负责订单撮合/滑点/手续费/逐日盯市，外层仅做数据注入和批量编排 |
| **绩效单一来源** | 盈亏/夏普/回撤统一从 vnpy calculate_statistics 获取，Strategy 不自算 (已移除 Performance 类) |
| **fills 作为交易日志** | Strategy.fills 记录每笔成交的方向/价格/手数/原因，只读不计算 |
| **全局常量字典** | 60+ 业务常量统一在 `common/constants.py`，消除全部魔术数字/字符串 |
| **统一公式库** | 15+ 量化公式统一在 `common/formulas.py`，零重复实现、可独立测试 |
| **Pandera Schema** | 4 个 DataFrame Schema 全局统一定义在 `common/schemas.py`，数据加载自动校验 |
| **Pydantic + peewee ORM** | 单条记录 Pydantic 校验 + 持久层 peewee ORM，完整类型安全 |
| **CLI 子包化** | `main.py` 为 19 行转发器，命令实现在 `cli/commands/`，每个命令独立模块 |
| **common/ 零依赖** | 纯函数、零 I/O、零副作用，可被所有模块安全引用 |

### 1.4 近期变更 (2026-05-25)

| 提交 | 变更 |
|------|------|
| `164d00d` | **refactor**: 数据模块配置管理：移除硬编码，统一通过 config 读取 |
| `a342811` | **feat**: 全项目代码升级与清理 |
| `6a13da1` | **feat**: 在 common/schemas.py 定义全局统一的 Pandera Schema |
| `11ac75f` | **refactor**: 重构 data 模块，全面使用 Pandera + Pydantic 验证 |
| `56ed973` | **refactor**: CLI 架构重构完成 + 文档同步更新 |
| `f5fac35` | **fix**: vnpy_backtest_engine 全局常量替换 + 数据不足边界修复 |
| `27e14b6` | **docs**: 常量字典+公式库规范写入 AI_BEHAVIOR_RULES + CONTRIBUTING |
| `6041db1` | **refactor**: 全局常量标准化 + 公式库统一替换 |
| `5f561bd` | **feat(common)**: 新增 constants.py 全局常量字典 + formulas.py 统一计算公式库 |
| `43ac62a` | **docs**: .memory_rules.md 新增 Bug 修复记录表 |
| `b271654` | **refactor**: 移除 Strategy.performance，绩效单一来源为 vnpy |
| `a3af52a` | **docs**: 刷新 plan.md 项目状态和缺陷清单 |

---

## 二、0.2 版本路线图

```
主线: 写一个回测能稳定盈利的策略
       │
S1 工具 ───→ S2 研发 ───→ S3 加固 ───→ S4 补全
A11/A12      A14+迭代     A15/A17      A16/A18
```

| 阶段 | 目标 | 状态 |
|------|------|------|
| **S1** 策略研发工具 | 参数优化 + 可视化 | 未开始 |
| **S2** 策略研发 | 多策略迭代至稳定盈利 | 未开始 |
| **S3** 生产加固 | 风控熔断 + 通知 | 未开始 |
| **S4** 基础设施 | Docker + 多数据源 | 未开始 |

> 当前处于 **S0: 工程基础打磨完成**，全局常量/公式库/CLI 重构/Pandera 校验已就绪，代码量 7,819 行，8 Bug 全部修复，可进入 S1。

### S1: 策略研发工具

> 先有工具，再做策略。看不到回测曲线、不会调参就谈不上研发。

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A12 | 回测结果本地可视化 | **高** | `visualizer/` — 资金曲线、信号标注、回撤区间、参数对比图 |
| A11 | 内置参数优化模块（网格搜索） | **高** | `optimizer/` — 参数网格定义、并发评估、最优参数输出 |
| S1-DOC | 策略开发指南 | 中 | `doc/strategy-guide.md` — 如何新增策略、调优流程 |

**S1 验收**: 跑一次完整流程 — 网格搜索均线参数 → 可视化最优 vs 默认对比图

### S2: 策略研发（主线）

> 在 S1 工具支撑下，迭代开发。目标是测试集上稳定盈利。

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A14 | RSI/布林带策略 | **高** | `strategies/rsi_strategy.py` |
| S2-OPT | 均线策略参数精调 | 高 | 利用 S1 优化器找到更优参数 |
| S2-COMP | 策略横向对比 | 中 | 多策略并发回测对比报告 |
| S2-ROBUST | 稳健性验证 | 中 | 跨品种/跨时段一致性测试 |

**S2 主线验收标准**:
- 至少 1 个策略满足：测试集夏普 ≥ 0.5、过拟合评分 < 15、最大回撤 < 20%
- 支持 ≥ 2 种策略类型

### S3: 生产加固

> 策略能盈利了，加上安全带。

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A15 | 实盘风控熔断 | 中 | `risk/` — 日亏损限额、最大回撤硬止损、连续亏损暂停 |
| A17 | 异常通知机制 | 低 | `notify/` — 微信/邮件通知 |

**S3 验收**: 实盘模式下，触发熔断条件后自动停止交易并通知

### S4: 基础设施补全

> 有余力再做。

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A16 | Docker 支持 | 低 | `Dockerfile` + `docker-compose.yml` |
| A18 | 多数据源抽象 | 低 | `data/sources/` — 除天勤外的数据源接口 |
| S4-DOC | 贡献指南 | 低 | `CONTRIBUTING.md` |

---

## 三、代码审计：缺陷清单（唯一权威源）

> 本节的 Bug/缺陷/架构发现是项目问题追踪的**唯一权威源**。`.memory_rules.md` 不再维护独立缺陷详情，KG 实体通过 Issue ID 关联至此。

> 审计日期: 2026-05-25 (第三次全量审计) | 基准: 量化交易系统行业惯例 | 覆盖: 36 个 .py 文件全部审阅

### 3.1 已修复 Bug

> 不再重复维护已修复 Bug 详情。本版本修复的 8 个逻辑/数值 Bug (BUG-01~08) 已归档至 [`CHANGELOG.md` §[0.2.0-dev] 修复段](./CHANGELOG.md#020-dev---2026-05-25)，含修复提交 hash。

本版本无新增未修复 Bug。

### 3.2 缺陷 — 质量/鲁棒性/工程实践

| 编号 | 严重度 | 问题 | 文件:行 | 说明 |
|------|--------|------|---------|------|
| DEF-01 | 🟡 高 | `_calc_position_size` 总是最少买 1 手 | `ma_strategy.py:153-156` | `max(1, int(vol))` 在资金不足时仍返回 1，下单会超资金限额被 vnpy 拒绝，但无前置检查 |
| DEF-02 | 🟡 中 | `compute_summary_stats` 对 NaN 无防护 | `common/stats.py:46-57` | `np.mean/median/std` 对含 NaN 数组返回 NaN，调用方（comparison_reporter）直接格式化输出 |
| DEF-03 | 🟡 中 | `calc_sharpe_ratio` 零权益无防护 | `common/metrics.py:48-49` | `returns = np.diff(curve) / curve[:-1]` 当 curve 含零时除零 → inf/nan。`std==0` 返回 999 或 0，但 inf mean 未处理 |
| DEF-04 | 🟡 中 | `upsert_metadata` 非原子操作有竞态窗口 | `data/store.py` | SELECT → 判断存在 → UPDATE/CREATE 分两步，并发 exporter 可能产生重复记录 |
| DEF-05 | 🟡 中 | `_InjectedStrategy` 闭包+临时属性时序脆弱 | `vnpy_backtest_engine.py:87-98` | 闭包捕获 `self._backtest_context`，该属性在 batch 模式下每品种覆写。虽然当前单线程安全，但属性语义是"最后的品种"而非"当前品种" |
| DEF-06 | 🟡 中 | tqsdk 实盘硬编码日线 | `tqsdk_bridge.py:136` | `api.get_kline_serial(symbol, 86400)` 硬编码 86400 秒（日线），不通过配置传入 |
| DEF-07 | 🟡 中 | max_drawdown 归一化三处重复且不一致 | `comparison_reporter.py:275`, `sql_reporter.py:386`, `formatting.py:27` | 同样 `abs(dd)>1 → /100` 逻辑分散三处，与 `format_pct` 的归一化逻辑不同，混用时结果不一致 |
| DEF-08 | 🟡 中 | `get_strategy_config` 合并顺序无文档 | `config_manager.py:80` | `{**defaults, **sp, **risk, **tc}` 优先级隐式。tc (trading) 覆盖 risk 覆盖 strategy_params，同 key 从何处生效不可预测 |
| DEF-09 | 🟡 中 | test 模式 — 测试用例只验证固定两行模拟数据 | `main.py:224-239` | 金叉/止损各一行测试，回测结果无任何数值断言；通过 ≠ 正确 |
| DEF-10 | 🟢 低 | `np.std` 多处未统一 ddof | `vnpy_backtest_engine.py:265`, `common/stats.py:64` | WF 用 `ddof=1`(样本)，stats 用 `ddof=0`(总体)，不一致导致 Walk-Forward 对比 report 聚合结果偏差 |
| DEF-11 | 🟢 低 | `DataFrame.iterrows()` 逐行构造 BarData 性能差 | `data_loader.py:174` | 数千行 K 线逐行 `BarData(...)` 创建，可用列表推导或矢量化 |

### 3.3 保留的存量缺陷 (12 项)

以下为前次审计保留且本次重新审查确认仍然存在的缺陷：

| 编号 | 分类 | 问题 | 文件 | 说明 |
|------|------|------|------|------|
| DEF-S01 | 测试 | 覆盖率排除核心文件 | `pyproject.toml` | main.py/bridges/exporter/vnpy_backtest_engine 被排除，66% 非真实值 |
| DEF-S02 | 测试 | Bridge 层零测试覆盖 | `strategies/bridges/` | ~300 行关键桥接代码无测试 |
| DEF-S03 | 测试 | 无集成/端到端测试 | `tests/` | 缺少导出→回测→报告完整流程测试 |
| DEF-S04 | 策略 | 止损/止盈使用固定比例 | `ma_strategy.py` | 不同品种波动率差异大，应用 ATR 动态调整 |
| DEF-S05 | 策略 | 信号优先级隐式 | `ma_strategy.py` | 止损>止盈>死叉由 if/elif 顺序隐式定义 |
| DEF-S06 | 数据 | money 字段为近似值 | `exporter.py` | `close*volume` 不反映期货保证金的实际资金占用 |
| DEF-S07 | 数据 | 缺少数据完整性校验 | `data_loader.py` | 未检查 K 线时间连续性、OHLC 一致性 |
| DEF-S08 | 风控 | 无实盘风控模块 | — | 无日亏损限额/连续亏损暂停/最大回撤硬止损 |
| DEF-S09 | 风控 | 无仓位风险检查 | — | 下单未考虑可用资金/保证金占用/持仓集中度 |
| DEF-S10 | 运维 | 缺少行情数据源健康检查 | `tqsdk_bridge.py` | 实盘运行无断线自动检测与重连 |
| DEF-S11 | 指标 | calc_sharpe_ratio 未扣除无风险利率 | `common/metrics.py` | 假设 rfr=0，对中国期货影响小但应文档化 |
| DEF-S12 | 指标 | 缺少 Sortino/Calmar/基准对比 | — | 缺下行风险指标、年化收益/回撤比 |

### 3.4 架构层面发现 (5 项 — 与上次审计一致，无新增)

| 编号 | 发现 | 严重度 | 说明 |
|------|------|--------|------|
| ARC-01 | `_InjectedStrategy` 闭包注入脆弱 | 中 | 依赖 `self._backtest_context` 临时属性+闭包捕获，并发调用会竞态 |
| ARC-02 | `data_loader.py` 覆盖率仅 37% | 中 | Walk-Forward 切分/CSV 扫描路径几乎无测试 |
| ARC-03 | `vnpy_backtest_engine.py` 覆盖率 11% | 中 | 核心引擎依赖 vnpy 运行时，无法在 CI 环境 mock |
| ARC-04 | ~~`main.py` 678 行单一入口~~ ✅ 已修复 | — | 已重构为 `cli/` 子包，`main.py` 仅 19 行转发 |
| ARC-05 | `sql_reporter.py` 覆盖率 19% | 低 | SQL 报告路径几乎未测试 |

### 3.5 本次审计已确认安全 ✅

| 项 | 结论 |
|----|------|
| peewee ORM 参数化查询 | 无 SQL 注入风险 |
| DatabaseProxy 延迟绑定模式 | 实现正确（`__init__` 内完成绑定） |
| TypedDict 与 ORM 模型字段一致性 | 逐字段核对一致 ✓ |
| 配置中 API 密钥管理 | 环境变量优先 + placeholder 保护 ✓ |
| `parse_percentage` / `ensure_float` | 边界安全，None/str 均有防护 |

### 3.6 已修复项 ✅

| 编号 | 说明 | 日期 |
|------|------|------|
| PERF-01 | Strategy.performance 双重绩效系统 | 2026-05-25 |
| AGG-01 | backtest.aggregator 自定义 rank_by_key | 2026-05-25 |
| BT16~21 | 第二轮审计修复 6 项 | 2026-05-24 |
| BT1~9 | 第一轮审计修复 9 项 Bug | 2026-05-24 |

---

## 四、风险评估

### 4.1 当前已发现风险

| 风险 | 可能性 | 影响 | 关联问题 | 状态 | 缓解措施 |
|------|--------|------|---------|------|---------|
| tq-backtest 盈亏全错 | 每次触发 | 🔴 高 | **BUG-01, BUG-02** | ✅ 已修复 | 已修复：卡尔积→FIFO (`3ea2d3e`)、手续费扣减 (`7ce71cb`) |
| Walk-Forward 崩溃丢弃数据 | 数据异常时 | 🔴 高 | **BUG-04** | ✅ 已修复 | 已修复：`_run_backtest` 加 try/except 逐窗口保护 (`d1589b9`) |
| format_pct 格式化错误 | 中 | 🟡 高 | **BUG-03** | ✅ 已修复 | 已修复：统一 DB 入库语义（全部存比值），消除启发式 (`d1589b9`) |
| 实盘无风控裸奔 | 中 | 🔴 高 | DEF-S08 | S3-A15 风控熔断 |
| 报告数值不可靠 | 高 | 🟡 中 | BUG-05~07, DEF-02, DEF-07 | ✅ 已修复 | BUG-05/06/07 已修复，方向常量+WF验证+命名修正 |
| `_InjectedStrategy` 竞态 | 低 | 🟡 中 | ARC-01 | 当前单线程安全，重构时再处理 |

### 4.2 前瞻风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 策略无法在测试集稳定盈利 | 高 | 高 | 放宽标准至夏普 > 0；多品种分散 |
| 参数优化过拟合 | 高 | 高 | Walk-Forward 验证 + 过拟合评分；限制搜索空间 |
| vn.py API 变更 | 中 | 高 | 锁定版本；CI 依赖一致性检查 |
| 天勤 SDK 升级不兼容 | 中 | 高 | 数据接口抽象层 |

---

## 五、衡量指标

| 指标 | 当前 (2026-05-25) | S1 目标 | S2 目标 | S3 目标 |
|------|-------------------|---------|---------|---------|
| Bug 数 | **0** (8/8 已修复) | 0 | 0 | 0 |
| 测试用例数 | 162 ✅ | 165+ | 175+ | 185+ |
| 覆盖率 | 51% | ≥ 55% | ≥ 65% | ≥ 75% |
| 策略类型数 | 1 (MA) | 1 | 2+ | 2+ |
| CI 状态 | ✅ 通过 | 通过 | 通过 | 通过 |
| 生产代码行 | 7,819 | — | — | — |

---

## 六、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| **0.2.0-dev** | **2026-05-25** | 第四次全量审计：全局常量标准化 + 公式库统一 + Pandera 校验 + CLI 重构完成。代码量 7,819 行，8 Bug 全部修复 |
| 0.2.0-dev | 2026-05-25 | 第三次审计：移除双重绩效系统；symbols_data 扁平化；peewee ORM；lib→common；回测与报告解耦 |
| 0.2.0-dev | 2026-05-24 | backtest 两轮审计修复 (15 项 Bug/缺陷)；DB 持久化 + cmd_report；S1-S4 四阶段规划 |
| 0.1.0 | 2026-05-24 | Beta 里程碑：策略/回测/数据/实盘完备 |
