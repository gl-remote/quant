# 系统架构设计

> 版本: 0.2.0-dev | 更新日期: 2026-05-25

---

## 架构总览

系统的核心设计原则是**业务逻辑与执行框架分离**。策略算法不依赖任何外部框架，通过桥接器接入不同的运行环境。

```
                        ┌──────────────────────┐
                        │       main.py        │
                        │   19 行入口转发器      │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │       cli/main.py    │
                        │   参数解析 + 命令分发   │
                        └──────────┬───────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                ▼       ▼       ▼                ▼
┌──────────────────┐  ┌──────────┐ ┌──────────┐  ┌──────────────────┐
│  cmd_export      │  │cmd_backtest│cmd_report│  │  cmd_live        │
│  数据导出         │  │ 统一回测   │ 报告生成  │  │  实盘/模拟交易     │
└────────┬─────────┘  └─────┬─────┘ └────┬─────┘  └────────┬─────────┘
         │                  │            │                 │
         ▼                  ▼            ▼                 ▼
┌──────────────────┐  ┌──────────────────┐         ┌──────────────────┐
│   data/exporter  │  │  VnpyBacktest    │         │  TqsdkStrategy    │
│   天勤→CSV       │  │  Engine          │         │  Bridge 桥接器     │
└────────┬─────────┘  └────────┬─────────┘         └────────┬─────────┘
         │                     │                            │
         │             ┌───────┼───────┐                    │
         │             ▼       ▼       ▼                    │
         │      ┌─────────┐┌─────────┐┌─────────┐          │
         │      │data     ││report   ││comparison│          │
         │      │loader   ││报告生成  ││对比分析   │          │
         │      └─────────┘└─────────┘└─────────┘          │
         │             │                                    │
         ▼             ▼                                    ▼
┌──────────────────────────────────────────────────────────────┐
│                    strategies/                                │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ MaStrategyCore  │◀─│VnpyStrategyBridge│TqsdkStrategyBridge│
│  │   纯业务逻辑     │  │  vn.py 桥接器   │  天勤桥接器       │
│  └─────────────────┘  └──────────────┘  └───────────────┘   │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  common/ (零依赖)                                     │    │
│  │  constants.py + formulas.py + schemas.py              │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## 核心架构模式：核心 + 桥接器

这是系统最重要的设计决策。策略的核心算法（SMA 计算、交叉检测、止盈止损判断）集中在 [MaStrategyCore](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/ma_strategy.py) 中，完全独立于任何交易框架。两个桥接器分别负责将该核心接入 vn.py 回测引擎和天勤实盘环境。

**为什么这样设计**：

1. **策略一致性** — 回测和实盘使用同一份算法代码，消除因实现差异导致的回测偏差
2. **框架可替换** — 更换交易框架只需新增桥接器，核心代码零改动
3. **测试便利** — 核心算法可脱离框架独立测试，无需启动完整回测环境

### 桥接器对比

| 特性 | VnpyStrategyBridge | TqsdkStrategyBridge |
|------|-------------------|---------------------|
| **用途** | vn.py 回测 | 天勤实盘/模拟/回测 |
| **生命周期** | on_init/start/stop/bar | 手动管理 |
| **订单执行** | self.buy/sell (vnpy) | 手动交易记录 |
| **行情格式** | vnpy BarData | tqsdk kline_serial |

## 回测流水线

回测引擎 [VnpyBacktestEngine](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) 执行五阶段标准化流水线：

```
┌──────────┐   ┌──────────┐   ┌────────────────┐   ┌──────────┐   ┌──────────┐
│ 1. 加载  │──▶│ 2. 划分  │──▶│ 3. 三阶段回测  │──▶│ 4. 报告  │──▶│ 5. 对比  │
│ CSV 数据 │   │ 训练/验证 │   │  train/val/test│   │ 生成 JSON│   │ 过拟合评估│
│          │   │  /测试集  │   │  ×3 独立执行   │   │ 交易记录 │   │ 稳定性分析│
└──────────┘   └──────────┘   └────────────────┘   └──────────┘   └──────────┘
```

### 数据集划分策略

系统支持两种数据划分模式：

- **时间顺序划分** (`shuffle: false`) — 前 60% 为训练集，中间 20% 为验证集，后 20% 为测试集。避免未来信息泄露，**推荐用于时间序列金融数据**。
- **随机采样划分** (`shuffle: true`) — 随机打乱后按比例分配。可用于跨品种稳健性验证，但存在前视偏差风险。

默认比例为 60-20-20，遵循机器学习领域经典划分标准。

## 模块职责

### `backtest/` — 回测子系统

| 模块 | 职责 |
|------|------|
| [vnpy_backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/vnpy_backtest_engine.py) | 批量回测 + Walk-Forward 编排器，包装 vnpy 官方引擎 |
| [data_loader.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/data_loader.py) | CSV 加载、数据集划分、vnpy BarData 格式转换 |
| [types.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/types.py) | 回测结果类型定义 |

报告生成已迁移至顶层 `report/` 包，通用工具已提取至 `common/`。

### `strategies/` — 策略子系统

```
strategies/
├── core/
│   ├── base.py           ← Strategy ABC
│   ├── types.py          ← Bar/Signal/Fill/StrategyPosition
│   └── run_config.py     ← RunConfig
├── ma_strategy.py        ← MaStrategyCore (纯算法, 173 行, 99% 覆盖)
└── bridges/
    ├── vnpy_bridge.py    ← VnpyStrategyBridge (vn.py 桥接)
    └── tqsdk_bridge.py   ← TqsdkStrategyBridge (天勤桥接)
```

### `common/` — 通用工具层 (零 I/O、零依赖)

| 模块 | 职责 |
|------|------|
| [constants.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/constants.py) | 全局常量字典 (60+ 常量：交易方向、信号原因、配置默认值等) |
| [formulas.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/formulas.py) | 统一量化计算公式库 (15+ 公式：SMA/交叉检测/止损止盈/仓位/FIFO PnL 等) |
| [schemas.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/schemas.py) | Pandera Schema 定义 (KlineSchema/DailyReturnSchema) |
| [metrics.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/metrics.py) | 绩效指标 (max_drawdown/sharp_ratio) |
| [stats.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/stats.py) | 统计聚合 (rank_by_key/summary_stats) |
| [formatting.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/common/formatting.py) | 安全格式化 (format_pct/format_float/ensure_float) |

### `data/` — 数据子系统

| 模块 | 职责 |
|------|------|
| [manager.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/manager.py) | DataManager 统一数据访问入口 |
| [models.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/models.py) | Pydantic 模型 (BacktestRecord/TradeRecord) + peewee ORM 模型 |
| [store.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/store.py) | SQLite 持久化层 (405 行) |
| [exporter.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/exporter.py) | 从天勤拉取 K 线，智能合并去重，导出 Qlib 标准 CSV |

### `cli/` — 命令行接口

```
cli/
├── main.py               ← 参数解析 + 命令分发 (149 行)
└── commands/
    ├── export.py         ← 数据导出命令
    ├── test.py           ← 策略测试命令
    ├── backtest.py       ← 统一回测命令 (自动选择 TqSdk/vnpy 引擎)
    ├── report.py         ← 报告生成命令
    └── live.py           ← 实盘交易命令
```

### `config/` — 配置子系统

[ProjectConfig](file:///Users/REDACTED_API_KEY/Documents/src/quant/config/app_config.py) 实现 TOML 分层配置的深度合并：`conf.toml`（基础配置，提交版本控制）→ `conf.local.toml`（本地覆盖，含密钥，不提交）。所有默认值来自 Pydantic 模型的 `Field(default=...)`。

## 数据流

### 回测数据流

```
.quant_shared_data/csv/*.csv
      │ load_csv_data()
      ▼
pandas DataFrame (全部历史数据)
      │ split_datasets()
      ├──▶ train_df ──▶ _run_single_backtest() ──▶ statistics
      ├──▶ val_df   ──▶ _run_single_backtest() ──▶ statistics
      └──▶ test_df  ──▶ _run_single_backtest() ──▶ statistics
                                                         │
                              ┌──────────────────────────┘
                              ▼
                    generate_dataset_report() ×3
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              train_report val_report test_report
                              │
                    compare_datasets()
                              │
                              ▼
              ┌───────────────────────────┐
              │  overfitting_assessment   │
              │  stability_analysis       │
              │  return_degradation       │
              └───────────────────────────┘
```

### 数据导出流

```
天勤服务器 ──tqsdk API──▶ _fetch_from_tqsdk()
                                    │
                                    ▼
                            new_df (新数据)
                                    │
                    ┌── 已有 CSV? ──┤
                    │ YES           │ NO
                    ▼               │
              pd.concat +            │
              drop_duplicates        │
                    │               │
                    └───────┬───────┘
                            ▼
                    .quant_shared_data/csv/
                    {symbol}_qlib.csv
                            │
                            ▼
                    SQLite: export_metadata (upsert)
```

## 过拟合评估体系

系统通过四个维度综合评估策略的过拟合风险：

| 维度 | 检测内容 | 严重阈值 | 高风险信号 |
|------|---------|---------|-----------|
| 收益递减 | 训练→测试 收益率下降幅度 | >50% | 策略过度拟合历史数据 |
| 回撤增加 | 测试集回撤 vs 训练集回撤 | 差异 >10% | 风控在未知数据上失效 |
| 夏普下降 | 风险调整收益的衰退 | >50% | 超额收益不可持续 |
| 胜率下降 | 交易信号质量退化 | >30% | 信号在新数据上失效 |

评分范围 0-100，分数越高表示过拟合风险越大。各风险等级及对应建议参见 [使用指南](usage-guide.md)。

## 目录结构

```
quant/
├── main.py                       # 命令行入口转发器 (19 行)
├── run.sh                        # 快捷运行脚本
├── activate_env.sh               # 环境激活
│
├── cli/                          # CLI 命令子包
│   ├── main.py                   #   参数解析与命令分发
│   └── commands/                 #   子命令实现
│       ├── export.py
│       ├── test.py
│       ├── backtest.py
│       ├── report.py
│       └── live.py
│
├── config/                       # 配置管理
│   ├── app_config.py              #   TOML 加载 + Pydantic 模型
│   ├── conf.toml                   #   基础配置（版本控制）
│   ├── conf.local.toml             #   本地密钥覆盖（不提交）
│
├── strategies/                   # 策略子系统
│   ├── core/                     #   抽象接口
│   │   ├── base.py               #     Strategy ABC
│   │   ├── types.py              #     Bar/Signal/Fill/StrategyPosition
│   │   └── run_config.py         #     RunConfig
│   ├── ma_strategy.py            #   均线策略核心 (173 行)
│   └── bridges/                  #   框架桥接器
│       ├── vnpy_bridge.py        #     vn.py 桥接
│       └── tqsdk_bridge.py       #     天勤桥接
│
├── backtest/                     # 回测子系统
│   ├── vnpy_backtest_engine.py   #   批量回测 + Walk-Forward
│   ├── data_loader.py            #   数据加载与划分
│   └── types.py                  #   回测结果类型
│
├── report/                       # 报告子系统
│   ├── dataset_reporter.py       #   单数据集报告
│   ├── comparison_reporter.py    #   多品种对比分析
│   └── sql_reporter.py           #   SQLite 报告
│
├── data/                         # 数据子系统
│   ├── manager.py                #   DataManager 统一入口
│   ├── models.py                 #   Pydantic + peewee ORM 模型
│   ├── store.py                  #   SQLite 持久化层
│   └── exporter.py               #   天勤→CSV 导出
│
├── common/                       # 通用工具层 (零 I/O)
│   ├── constants.py              #   全局常量字典 (60+)
│   ├── formulas.py               #   量化计算公式库 (15+)
│   ├── schemas.py                #   Pandera Schema 定义 (4 Schema)
│   ├── metrics.py                #   绩效指标
│   ├── stats.py                  #   统计聚合
│   └── formatting.py             #   安全格式化
│
├── docs/                         # 文档
│   ├── overview.md               #   项目概览
│   ├── architecture.md           #   架构设计（本文）
│   ├── configuration.md          #   配置说明
│   ├── usage-guide.md            #   使用指南
│   ├── api-reference.md          #   API 文档
│   └── faq.md                    #   常见问题
│
└── .quant_shared_data/           # 共享数据目录
    ├── csv/                      #   历史行情 CSV
    ├── reports/                  #   回测报告 JSON
    └── quant_shared.db           #   元数据与日志库
```