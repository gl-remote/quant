# 项目改进计划

> 版本: 0.2.0-dev | 最后更新: 2026-05-27 | 主线: 稳定盈利策略研发

---

## 一、项目现状

### 1.1 核心指标

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 策略类型 | 1 (双均线 MA) | 2+ |
| 数据源 | tqsdk / akshare | — |
| 数据资产 | 9 品种 × 3 周期 (1m/5m/15m) | — |
| CI | ✅ 通过 | 通过 |

### 1.2 模块架构

```
main.py
├── cli/                 命令接口 (export/test/backtest/report/live)
├── strategies/          策略核心 (框架无关)
│   ├── core/            ABC + 类型定义
│   ├── bridges/         vnpy / 天勤 桥接
│   └── ma_strategy.py   双均线策略
├── backtest/            回测引擎 (纯执行器)
├── optimizer/           Optuna 参数搜索 (grid + bayesian)
├── data/                数据层
│   ├── datasource/      多数据源抽象 (BaseDataSource → tqsdk/akshare)
│   ├── store.py         SQLite + peewee
│   ├── manager.py       统一数据访问
│   └── exporter.py      数据导出 + 去重合并
├── common/              纯函数工具层
│   ├── symbol_utils.py  合约代码解析 + 默认日期推算
│   ├── schemas.py       Pandera Schema
│   └── formulas.py      量化计算公式库
├── report/              报告 + Plotly 可视化
├── config/              Pydantic 配置管理
└── tools/               运维脚本
    ├── fetch_data.sh    一键拉数据 (1m/5m/15m)
    ├── test-ma.sh       全链路回测
    └── clean_data.sh    清理回测数据
```

### 1.3 架构决策

| 决策 | 说明 |
|------|------|
| Strategy + Bridge 分离 | 策略核心不依赖任何框架 |
| 复用 vnpy 回测引擎 | 订单撮合/滑点/手续费/逐日盯市 |
| 多数据源抽象 | `BaseDataSource` → 注册表工厂，export 和 backtest 解耦 |
| 合约自动解析 | `symbol_utils.parse_contract` → 交易所/品种/月份/默认日期 |
| 文件名含 provider | `{symbol}.{provider}.{interval}.csv` 不同源不覆盖 |
| common/ 零 I/O | 纯函数，供所有上层模块共用 |

---

## 二、0.2 版本路线图

| 阶段 | 目标 | 状态 |
|------|------|------|
| **S0** 工程基础 | 常量/公式/CLI/Schema/report 统一 | ✅ |
| **S1** 策略研发工具 | 参数优化 + 多数据源 + 可视化 | ✅ |
| **S2** 策略研发 | 多策略迭代至稳定盈利 | ⬜ 未开始 |
| **S3** 生产加固 | 风控熔断 + 通知 | ⬜ 未开始 |
| **S4** 基础设施 | Docker + CI 增强 | ⬜ 未开始 |

### S1 已完成

| 交付 | 说明 |
|------|------|
| A11 参数优化 | `optimizer/` — GridSampler + TPESampler |
| A12 可视化 | `report/` — Plotly 多子图 + HTML 报告 |
| A18 多数据源 | `data/datasource/` — tqsdk / akshare 切换 |

### S2: 策略研发（主线）

| 编号 | 行动 | 说明 |
|------|------|------|
| A14 | RSI/布林带策略 | `strategies/rsi_strategy.py` |
| S2-OPT | 均线参数精调 | 用当前 9 品种数据跑网格搜索 |
| S2-COMP | 策略横向对比 | 多策略并发回测对比 |

**验收标准**: 至少 1 个策略满足：夏普 ≥ 0.5、最大回撤 < 20%

### S3: 生产加固

| 编号 | 行动 |
|------|------|
| A15 | 实盘风控熔断 (日亏损限额/回撤硬止损) |
| A17 | 异常通知 (微信/邮件) |

### S4: 基础设施

| 编号 | 行动 |
|------|------|
| A16 | Docker 支持 |

---

## 三、已知缺陷

| 编号 | 严重度 | 问题 | 位置 |
|------|--------|------|------|
| DEF-01 | 🟡 高 | 资金不足时仍返回最少 1 手 | `ma_strategy.py` |
| DEF-02 | 🟡 中 | `compute_summary_stats` NaN 无防护 | `common/stats.py` |
| DEF-03 | 🟡 中 | `calc_sharpe_ratio` 除零 → inf/nan | `common/metrics.py` |
| DEF-04 | 🟡 中 | `upsert_metadata` 非原子操作 | `data/store.py` |
| DEF-05 | 🟡 中 | `_InjectedStrategy` 闭包时序脆弱 | `vnpy_backtest_engine.py` |
| DEF-08 | 🟡 中 | `get_strategy_config` 合并顺序无文档 | `config_manager.py` |
| DEF-S04 | 🟡 策略 | 止损/止盈使用固定比例而非 ATR | `ma_strategy.py` |
| DEF-S05 | 🟡 策略 | 信号优先级由 if/elif 顺序隐式定义 | `ma_strategy.py` |

---

## 四、风险评估

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 策略无法稳定盈利 | 高 | 高 | 放宽标准至夏普 > 0；多品种/多周期 |
| 参数优化过拟合 | 高 | 高 | Walk-Forward 验证 |
| 数据窗口过短 (~30天 1m) | 中 | 中 | 5m/15m 周期补充；手动扩充日期范围 |
| vn.py API 变更 | 中 | 高 | 锁定版本 |
