# 项目改进计划

> 版本: 0.2.0-dev | 最后更新: 2026-05-26 | 主线: 稳定盈利策略研发

---

## 一、项目现状

### 1.1 核心指标

| 指标 | 当前值 | S1 目标 | S2 目标 |
|------|--------|---------|---------|
| 生产代码 | 5,685 行 (38 个 .py 文件) | — | — |
| 测试代码 | 2,722 行 (7 个 test 文件) | — | — |
| 测试用例 | **297** 个全通过 | 310+ | 330+ |
| 覆盖率 | **61%** | ≥ 65% | ≥ 70% |
| 策略类型 | 1 (双均线 MA) | 1 | 2+ |
| CI | ✅ 通过 | 通过 | 通过 |

> 代码精简 27%（7,819→5,685），测试从 162→297（+83%），覆盖率 51%→61%。

### 1.2 模块架构

```
main.py (19 行转发器) → cli/ (命令行子包)
├── cli/main.py          参数解析 + 命令分发
│   └── commands/        5 个子命令 (export/test/backtest/report/live)
├── strategies/          策略核心 (框架无关)
│   ├── core/            Strategy ABC + Bar/Signal/Fill/Position 类型
│   ├── bridges/         vnpy 桥接 + 天勤桥接
│   └── ma_strategy.py   双均线策略 (82 行, 100% 覆盖)
├── backtest/            回测引擎 (纯执行器)
│   ├── vnpy_backtest_engine.py  批量回测 + Walk-Forward
│   └── walk_forward.py          时间窗口切分
├── optimizer/           参数搜索 (S1·A11 ✅)
│   └── optuna_search.py OptunaOptimizer (统一优化器)
├── data/                数据层
│   ├── store.py         SQLite + peewee ORM
│   ├── models.py        Pydantic + ORM 模型
│   ├── manager.py       DataManager 统一入口
│   └── exporter.py      天勤 → CSV 导出
├── report/              报告 + 可视化
│   ├── reports.py       文字报告
│   ├── charts.py        Plotly 多子图
│   ├── _html.py         HTML 模板
│   └── __init__.py      build_report() 统一入口
├── common/              纯函数工具层 (零 I/O)
│   ├── constants.py     全局常量字典
│   ├── formulas.py      统一量化计算公式库
│   ├── schemas.py       Pandera Schema 定义
│   ├── metrics.py       max_drawdown / sharpe_ratio
│   ├── stats.py         rank_by_key / summary_stats
│   └── formatting.py    百分比/浮点数格式化
└── config/              配置管理
    └── app_config.py    Pydantic 配置模型 + 单例
```

### 1.3 架构决策记录

| 决策 | 说明 |
|------|------|
| **Strategy + Bridge 分离** | 策略核心不依赖任何框架，Bridge 做协议转换 |
| **复用官方回测引擎** | vnpy BacktestingEngine 负责订单撮合/滑点/手续费/逐日盯市 |
| **绩效单一来源** | 盈亏/夏普/回撤统一从 vnpy calculate_statistics 获取 |
| **全局常量字典** | 60+ 业务常量统一在 `common/constants.py` |
| **统一公式库** | 15+ 量化公式统一在 `common/formulas.py` |
| **Pandera Schema** | 4 个 DataFrame Schema 全局统一定义 |
| **Pydantic + peewee ORM** | 单条记录 Pydantic 校验 + 持久层 peewee ORM |
| **common/ 零依赖** | 纯函数、零 I/O、零副作用 |
| **Engine 纯执行** | Engine 只调 vnpy，数据加载走 DataManager |

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
| **S0** 工程基础 | 常量/公式/CLI/Schema/report 统一 | ✅ 完成 |
| **S1** 策略研发工具 | 参数优化 + 可视化完善 | 进行中 |
| **S2** 策略研发 | 多策略迭代至稳定盈利 | 未开始 |
| **S3** 生产加固 | 风控熔断 + 通知 | 未开始 |
| **S4** 基础设施 | Docker + 多数据源 | 未开始 |

### S1: 策略研发工具

| 编号 | 行动 | 优先级 | 状态 | 交付物 |
|------|------|--------|------|--------|
| A12 | 回测结果本地可视化 | **高** | 🟡 部分完成 | `report/charts.py` — Plotly 多子图 + HTML 模板 |
| A11 | 内置参数优化模块 | **高** | ✅ 已完成 | `optimizer/` — GridOptimizer + OptunaOptimizer |
| S1-DOC | 策略开发指南 | 中 | ⬜ 未开始 | `docs/strategy-guide.md` |

**S1 验收**: 跑一次完整流程 — 网格搜索均线参数 → 可视化最优 vs 默认对比图

### S2: 策略研发（主线）

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

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A15 | 实盘风控熔断 | 中 | `risk/` — 日亏损限额、最大回撤硬止损 |
| A17 | 异常通知机制 | 低 | `notify/` — 微信/邮件通知 |

### S4: 基础设施补全

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A16 | Docker 支持 | 低 | `Dockerfile` + `docker-compose.yml` |
| A18 | 多数据源抽象 | 低 | `data/sources/` — 多数据源接口 |

---

## 三、未解决缺陷清单

> 审计日期: 2026-05-25 | 已修复的 Bug 请查看 [`CHANGELOG.md`](./CHANGELOG.md)

### 3.1 待修复缺陷

| 编号 | 严重度 | 问题 | 文件:行 | 说明 |
|------|--------|------|---------|------|
| DEF-01 | 🟡 高 | `_calc_position_size` 总是最少买 1 手 | `ma_strategy.py:153-156` | 资金不足时仍返回 1，无前置检查 |
| DEF-02 | 🟡 中 | `compute_summary_stats` 对 NaN 无防护 | `common/stats.py:46-57` | `np.mean/median/std` 返回 NaN |
| DEF-03 | 🟡 中 | `calc_sharpe_ratio` 零权益无防护 | `common/metrics.py:48-49` | 除零 → inf/nan |
| DEF-04 | 🟡 中 | `upsert_metadata` 非原子操作有竞态窗口 | `data/store.py` | 并发 exporter 可能产生重复记录 |
| DEF-05 | 🟡 中 | `_InjectedStrategy` 闭包+临时属性时序脆弱 | `vnpy_backtest_engine.py:87-98` | 属性语义是"最后的品种"而非"当前品种" |
| DEF-06 | 🟡 中 | tqsdk 实盘硬编码日线 | `tqsdk_bridge.py:136` | `api.get_kline_serial(symbol, 86400)` |
| DEF-07 | 🟡 中 | max_drawdown 归一化三处重复且不一致 | 多处 | 同样逻辑分散三处，归一化不一致 |
| DEF-08 | 🟡 中 | `get_strategy_config` 合并顺序无文档 | `config_manager.py:80` | 优先级隐式，同 key 生效位置不可预测 |
| DEF-09 | 🟡 中 | test 模式只验证固定两行模拟数据 | `main.py:224-239` | 无数值断言，通过 ≠ 正确 |
| DEF-10 | 🟢 低 | `np.std` 多处未统一 ddof | `vnpy_backtest_engine.py:265`, `common/stats.py:64` | WF 用 ddof=1，stats 用 ddof=0 |
| DEF-11 | 🟢 低 | `DataFrame.iterrows()` 逐行构造 BarData 性能差 | `data_loader.py:174` | 可用列表推导或矢量化 |

### 3.2 存量缺陷

| 编号 | 分类 | 问题 | 文件 | 说明 |
|------|------|------|------|------|
| DEF-S01 | 测试 | 覆盖率排除核心文件 | `pyproject.toml` | main.py/bridges/exporter 被排除 |
| DEF-S02 | 测试 | Bridge 层零测试覆盖 | `strategies/bridges/` | ~300 行关键代码无测试 |
| DEF-S03 | 测试 | 无集成/端到端测试 | `tests/` | 缺少导出→回测→报告完整流程测试 |
| DEF-S04 | 策略 | 止损/止盈使用固定比例 | `ma_strategy.py` | 应使用 ATR 动态调整 |
| DEF-S05 | 策略 | 信号优先级隐式 | `ma_strategy.py` | 止损>止盈>死叉由 if/elif 顺序隐式定义 |
| DEF-S06 | 数据 | money 字段为近似值 | `exporter.py` | `close*volume` 不反映实际资金占用 |
| DEF-S07 | 数据 | 缺少数据完整性校验 | `data_loader.py` | 未检查 K 线时间连续性、OHLC 一致性 |
| DEF-S08 | 风控 | 无实盘风控模块 | — | 无日亏损限额/连续亏损暂停/最大回撤硬止损 |
| DEF-S09 | 风控 | 无仓位风险检查 | — | 下单未考虑可用资金/保证金占用/持仓集中度 |
| DEF-S10 | 运维 | 缺少行情数据源健康检查 | `tqsdk_bridge.py` | 实盘运行无断线自动检测与重连 |
| DEF-S11 | 指标 | calc_sharpe_ratio 未扣除无风险利率 | `common/metrics.py` | 假设 rfr=0，应文档化 |
| DEF-S12 | 指标 | 缺少 Sortino/Calmar/基准对比 | — | 缺下行风险指标、年化收益/回撤比 |

### 3.3 架构层面发现

| 编号 | 发现 | 严重度 | 说明 |
|------|------|--------|------|
| ARC-02 | `data_loader.py` 覆盖率仅 37% | 中 | Walk-Forward 切分/CSV 扫描路径几乎无测试 |
| ARC-03 | `vnpy_backtest_engine.py` 覆盖率 11% | 中 | 核心引擎依赖 vnpy 运行时，无法在 CI mock |
| ARC-05 | `sql_reporter.py` 覆盖率 19% | 低 | SQL 报告路径几乎未测试 |

---

## 四、风险评估

### 4.1 当前已发现风险

| 风险 | 可能性 | 影响 | 关联问题 | 状态 | 缓解措施 |
|------|--------|------|---------|------|---------|
| 实盘无风控裸奔 | 中 | 🔴 高 | DEF-S08 | S3-A15 风控熔断 |
| 报告数值不可靠 | 高 | 🟡 中 | DEF-02, DEF-07 | 已有修复计划 |

### 4.2 前瞻风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 策略无法在测试集稳定盈利 | 高 | 高 | 放宽标准至夏普 > 0；多品种分散 |
| 参数优化过拟合 | 高 | 高 | Walk-Forward 验证 + 过拟合评分；限制搜索空间 |
| vn.py API 变更 | 中 | 高 | 锁定版本；CI 依赖一致性检查 |
| 天勤 SDK 升级不兼容 | 中 | 高 | 数据接口抽象层 |

---

## 五、Engine 重构设计

> 将当前 CLI/Engine 职责重叠（数据加载 + 策略创建）彻底分离，为 S1 参数搜索铺平道路。

### 5.1 目标架构

```
data/              加载 K 线 + 元数据查询 + 持久化 (不变)
optimizer/         参数搜索，产出 N 个 Strategy 变体 (新建)
backtest/          纯执行器：调 vnpy，不管数据来源和策略创建
CLI/               编排 data + optimizer + backtest，结果持久化
```

### 5.2 Engine 接口

```python
class BacktestEngine:
    def __init__(self, backtest_config: BacktestConfig, dm: DataManager)

    def run(self, pairs: list[tuple[DataFrame, Strategy]]) -> list[dict]

    def run_walk_forward(
        self, data: DataFrame, strategy: Strategy,
        train_size=None, val_size=None, test_size=None, step=None,
    ) -> dict
```

**关键约束**:
- Engine 不再 import 任何具体策略类
- Engine 不再扫描 CSV 文件系统
- 多策略共用一个 vnpy engine，一次回放拿到所有策略结果

### 5.3 调用流程

```
backtest --mode search:
  CLI: dm.load_kline_safe(symbol) → list[(symbol, DataFrame)]
  CLI: optimizer.optimize(strategy_cls, search_space) → OptunaResult
  CLI: results = extract_results(result.trial_data)
  CLI: _persist_results(dm, results)

backtest --mode walk-forward:
  CLI: dm.load_kline_safe(symbol) → DataFrame
  CLI: strategy = load_strategy(...) → Strategy × 1
  CLI: result = engine.run_walk_forward(data, strategy)
  CLI: _persist_results(dm, [result])
```
