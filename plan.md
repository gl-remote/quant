# 项目改进计划

> 版本: 0.2.0-dev | 最后更新: 2026-05-25 | 主线: 稳定盈利策略研发

---

## 一、项目现状

### 1.1 基础数据

| 指标 | 数值 |
|------|------|
| 生产代码 | 4,568 行 (36 个 .py 文件) |
| 测试代码 | ~1,600 行 (7 个 test 文件) |
| 测试用例 | **162** 个全通过，0 失败 |
| 覆盖率 | **66%** (1,315 stmts / 445 missed) |
| 策略类型 | 1 (双均线 MA) |
| CI | GitHub Actions (pytest + flake8) |
| Python | 3.10+ |

### 1.2 模块架构

```
main.py (678 行 CLI 入口)
├── strategies/      策略核心 (框架无关)
│   ├── core/        Strategy ABC + Bar/Signal/Fill/Position 类型
│   ├── bridges/     vnpy 桥接 + 天勤桥接 (协议转换层)
│   └── ma_strategy.py  双均线策略实现
├── backtest/        回测引擎
│   ├── vnpy_backtest_engine.py  批量回测 + Walk-Forward (包装官方引擎)
│   ├── tq_backtest_engine.py     天勤 GUI 回测 (单标的图形化)
│   ├── data_loader.py            CSV 加载 / 窗口切分
│   └── types.py                  回测结果类型
├── data/            数据层
│   ├── database.py  SQLite + peewee ORM
│   ├── models.py    完整 TypedDict 体系
│   └── exporter.py  天勤 → Qlib CSV 导出
├── report/          报告层
│   ├── dataset_reporter.py     单数据集 JSON 报告
│   ├── comparison_reporter.py  多品种横向对比 + 排名
│   └── sql_reporter.py         SQLite 只读报告
├── common/          纯函数工具层 (零 I/O)
│   ├── metrics.py   max_drawdown / sharpe_ratio
│   ├── stats.py     rank_by_key / summary_stats
│   └── formatting.py  百分比/浮点数格式化
└── config/          配置管理 (YAML)
```

### 1.3 架构决策记录

| 决策 | 说明 |
|------|------|
| **Strategy + Bridge 分离** | 策略核心不依赖任何框架，Bridge 做协议转换。同一份策略代码驱动 vnpy 回测和天勤实盘 |
| **复用官方回测引擎** | vnpy BacktestingEngine 负责订单撮合/滑点/手续费/逐日盯市，外层仅做数据注入和批量编排 |
| **绩效单一来源** | 盈亏/夏普/回撤统一从 vnpy calculate_statistics 获取，Strategy 不自算 (已移除 Performance 类) |
| **fills 作为交易日志** | Strategy.fills 记录每笔成交的方向/价格/手数/原因，只读不计算 |
| **peewee ORM** | 替代 raw SQL，完整的 type-safe 数据库层 |
| **common/ 零依赖** | 纯函数、零 I/O、零副作用，可被所有模块安全引用 |

### 1.4 近期变更 (2026-05-25, 自上次 plan 更新以来)

| 提交 | 变更 |
|------|------|
| `b271654` | **refactor**: 移除 Strategy.performance，绩效单一来源为 vnpy |
| `eb18b81` | **refactor**: symbols_data 扁平化，删除 backtest.aggregator |
| `882f555` | **refactor**: 重构回测模块，报表逻辑移至 report 包 |
| `3ac1307` | **refactor**: 强制类型化 ORM 架构，消除 Any 残留 |
| `fab775e` | **refactor**: 引入 peewee ORM 替代 raw SQL |
| `ef2e586` | **test**: 新增 tests/test_common.py，覆盖 common/ 全部纯函数 |
| `e60eee8` | **fix**: 重命名 lib/ → common/ |
| `0a880a8` | **refactor**: 提取 common/ 通用纯函数模块 |
| `cdf0982` | **feat**: 回测执行与报告解耦 (DB 持久化 + cmd_report) |

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

> 当前处于 **S0: 工程基础打磨完成**，工具链/测试/CI/架构已就绪，可以进入 S1。

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

## 三、代码审计：缺陷清单

> 审计日期: 2026-05-25 (第三次全量审计) | 基准: 量化交易系统行业惯例 | 覆盖: 36 个 .py 文件全部审阅

### 3.1 Bug — 逻辑错误/数值计算错误

| 编号 | 严重度 | 状态 | 问题 | 文件:行 | 根因与影响 | 修复提交 |
|------|--------|------|------|---------|-----------|---------|
| BUG-01 | 🔴 严重 | ✅ 已修复 | tq-backtest 盈亏计算错误 (笛卡尔积) | `main.py:458-464` | `for sf in sells: for bf in buys: total += (sf.price - bf.price) * sf.volume` 每笔卖出与**所有**买入逐一配对，不是配对撮合。盈亏总额完全失真 | `3ea2d3e` |
| BUG-02 | 🔴 严重 | ✅ 已修复 | TQBacktestEngine 零手续费/滑点 | `tq_backtest_engine.py:43-67` | `add_trade` 中买入扣 `price*quantity`、卖出加回同额，无手续费率/滑点扣减。权益曲线系统性偏高 | `7ce71cb` |
| BUG-03 | 🟡 高 | ✅ 已修复 | `format_pct` 语义启发式不可靠 | `common/formatting.py:27-28` | `abs(v) > 1 → v/100` 在回撤值为 -1.5（比值 -1.5，即 -150%）时被迫归一化为 -0.015（显示 -1.50%），完全错误。整个代码库调用方混用比值和百分比值 | `d1589b9` |
| BUG-04 | 🟡 高 | ✅ 已修复 | `_run_backtest` 零异常处理 | `vnpy_backtest_engine.py:298-372` | Walk-Forward 200 个窗口中任一 `engine.run_backtesting()` 崩溃，整个循环终止，已成功的窗口结果全部作废 | `d1589b9` |
| BUG-05 | 🟡 中 | ✅ 已修复 | 买卖统计方向常值混淆 | `sql_reporter.py:68-73` | vnpy 返回 `direction='long'/'short'`（对应开多/开空），但 `MaStrategy` fill 记录使用 `action='buy'/'sell'`。DB 存储 vnpy 方向值，SQL 报告查询 `direction=='long' and offset=='open'` 依赖 vnpy 内部表示，脆弱 | `f889e16` |
| BUG-06 | 🟡 中 | ✅ 已修复 | Walk-Forward 窗口数公式为近似值 | `data_loader.py:318` | `n/(1+(min_windows-1)*step_ratio)` 在浮点截断 + int 舍入下，实际窗口数可能少于 min_windows，且不警告 | `500312b` |
| BUG-07 | 🟡 中 | ✅ 已修复 | `annual_return_abs` 命名与值不匹配 | `dataset_reporter.py:119-120` | `annual_return_abs` 命名暗示绝对金额，实际存储 `statistics.get('annual_return', 0)` 即 vnpy 返回的**比值**（如 0.15 = 15%）。comparison_reporter 按 `total_return_abs` 取值时类型预期混乱 | `fc4ca15` |
| BUG-08 | 🟢 低 | ✅ 已修复 | `config_manager` 静默修改源配置字典 | `config_manager.py:76-79` | `_load` 返回 `self.config` 引用，`get_strategy_config` 对 `tc` 字典写入默认值 → 污染全局配置。后续获取同一 key 会得到默认值而非原始缺失 | `3d505cf` |

### 3.2 缺陷 — 质量/鲁棒性/工程实践

| 编号 | 严重度 | 问题 | 文件:行 | 说明 |
|------|--------|------|---------|------|
| DEF-01 | 🟡 高 | `_calc_position_size` 总是最少买 1 手 | `ma_strategy.py:153-156` | `max(1, int(vol))` 在资金不足时仍返回 1，下单会超资金限额被 vnpy 拒绝，但无前置检查 |
| DEF-02 | 🟡 中 | `compute_summary_stats` 对 NaN 无防护 | `common/stats.py:46-57` | `np.mean/median/std` 对含 NaN 数组返回 NaN，调用方（comparison_reporter）直接格式化输出 |
| DEF-03 | 🟡 中 | `calc_sharpe_ratio` 零权益无防护 | `common/metrics.py:48-49` | `returns = np.diff(curve) / curve[:-1]` 当 curve 含零时除零 → inf/nan。`std==0` 返回 999 或 0，但 inf mean 未处理 |
| DEF-04 | 🟡 中 | `upsert_metadata` 非原子操作有竞态窗口 | `data/database.py:147-183` | SELECT → 判断存在 → UPDATE/CREATE 分两步，并发 exporter 可能产生重复记录 |
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
| ARC-04 | `main.py` 678 行单一入口 | 低 | CLI 子命令逻辑内联，后续可拆分为 `cli/` 包 |
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
| Bug 数 | **8** (0 → 8) | 0 | 0 | 0 |
| 测试用例数 | 162 ✅ | 165+ | 175+ | 185+ |
| 覆盖率 | 66% | ≥ 70% | ≥ 75% | ≥ 80% |
| 策略类型数 | 1 (MA) | 1 | 2+ | 2+ |
| CI 状态 | ✅ 通过 | 通过 | 通过 | 通过 |
| 库存问题数 | **31** (8 Bug + 23 缺陷/架构) | — | — | — |

---

## 六、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| **0.2.0-dev** | **2026-05-25** | 第三次全量审计：发现 8 项 Bug（含 2 严重）、11 项缺陷；确认保留 12 项存量缺陷；Bug 清零后再考虑进入 S1 |
| 0.2.0-dev | 2026-05-25 | 移除双重绩效系统；symbols_data 扁平化；删除 aggregator；引入 peewee ORM；lib→common；回测与报告解耦 |
| 0.2.0-dev | 2026-05-24 | backtest 两轮审计修复 (15 项 Bug/缺陷)；DB 持久化 + cmd_report；S1-S4 四阶段规划 |
| 0.1.0 | 2026-05-24 | Beta 里程碑：策略/回测/数据/实盘完备 |
