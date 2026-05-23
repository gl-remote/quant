# 系统架构设计

> 版本: 1.0.0 | 更新日期: 2026-05-24

---

## 架构总览

系统的核心设计原则是**业务逻辑与执行框架分离**。策略算法不依赖任何外部框架，通过网关适配器接入不同的运行环境。

```
                        ┌──────────────────────┐
                        │       main.py        │
                        │    命令行入口/命令分发   │
                        └──────────┬───────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  cmd_export      │   │  cmd_backtest    │   │  cmd_live        │
│  数据导出         │   │  vn.py 回测      │   │  实盘/模拟交易     │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   data/exporter  │   │  VnpyBacktest    │   │  TqsdkMaStrategy │
│   天勤→CSV       │   │  Engine          │   │  天勤网关适配器    │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         │              ┌───────┼───────┐              │
         │              ▼       ▼       ▼              │
         │      ┌─────────┐┌─────────┐┌─────────┐     │
         │      │data     ││report   ││comparison│     │
         │      │loader   ││报告生成  ││对比分析   │     │
         │      └─────────┘└─────────┘└─────────┘     │
         │              │                              │
         ▼              ▼                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    strategies/                                │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ MaStrategyCore  │◀─│ VnpyMaStrategy│  │TqsdkMaStrategy│   │
│  │   纯业务逻辑     │  │  vn.py 网关    │  │  天勤网关      │   │
│  └─────────────────┘  └──────────────┘  └───────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 核心架构模式：核心 + 网关

这是系统最重要的设计决策。策略的核心算法（SMA 计算、交叉检测、止盈止损判断）集中在 [MaStrategyCore](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/core/ma_strategy.py) 中，完全独立于任何交易框架。两个网关适配器分别负责将该核心接入 vn.py 回测引擎和天勤实盘环境。

**为什么这样设计**：

1. **策略一致性** — 回测和实盘使用同一份算法代码，消除因实现差异导致的回测偏差
2. **框架可替换** — 更换交易框架只需新增网关适配器，核心代码零改动
3. **测试便利** — 核心算法可脱离框架独立测试，无需启动完整回测环境

### 网关适配器对比

| 特性 | VnpyMaStrategy | TqsdkMaStrategy |
|------|---------------|-----------------|
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

### 双引擎降级策略

```
_run_single_backtest()
      │
      ▼
┌─ HAS_VNPY? ─┐
│ YES         │ NO
▼             ▼
vnpy          内置 BacktestEngine
Backtesting    (纯 Python 实现)
Engine         SMA计算 + 资金管理
│              + 绩效统计
▼              ▼
statistics    statistics
```

当 vn.py 未安装时，系统自动切换至内置引擎。内置引擎使用相同的策略核心 `MaStrategyCore`，提供的统计指标与 vnpy 引擎一致（总收益、夏普比率、最大回撤、胜率等），仅在计算精度上略有差异。

## 模块职责

### `backtest/` — 回测子系统

| 模块 | 职责 |
|------|------|
| [backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) | 核心编排器，协调五阶段流水线；内置降级引擎 |
| [data_loader.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/data_loader.py) | CSV 加载、数据集划分、vnpy BarData 格式转换 |
| [report.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/report.py) | 单数据集报告生成，包含绩效、风险、交易统计 |
| [comparison.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/comparison.py) | 三阶段对比分析，过拟合风险评估 |

### `strategies/` — 策略子系统

```
strategies/
├── core/
│   └── ma_strategy.py    ← MaStrategyCore (纯算法)
└── gateways/
    ├── vnpy_gateway.py   ← VnpyMaStrategy (vn.py 适配)
    └── tqsdk_gateway.py  ← TqsdkMaStrategy (天勤适配)
```

### `data/` — 数据子系统

| 模块 | 职责 |
|------|------|
| [exporter.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/exporter.py) | 从天勤拉取 K 线，智能合并去重，导出 Qlib 标准 CSV |
| [database.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/data/database.py) | SQLite 数据库：导出元数据管理、操作日志持久化 |

### `config/` — 配置子系统

[ConfigManager](file:///Users/REDACTED_API_KEY/Documents/src/quant/config/config_manager.py) 实现 YAML 分层配置的深度合并：`conf.yaml`（基础配置，提交版本控制）→ `conf.local.yaml`（本地覆盖，含密钥，不提交）。

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
├── main.py                       # 命令行统一入口
├── conf.yaml                     # 基础配置（版本控制）
├── conf.local.yaml               # 本地密钥覆盖（不提交）
├── conf.example.yaml             # 配置模板
├── requirements.txt              # Python 依赖
├── run.sh                        # 快捷运行脚本
├── activate_env.sh               # 环境激活
│
├── config/                       # 配置管理
│   └── config_manager.py         # YAML 分层合并
│
├── strategies/                   # 策略子系统
│   ├── core/ma_strategy.py       # 纯算法核心
│   └── gateways/                 # 框架适配器
│       ├── vnpy_gateway.py       # vn.py 网关
│       └── tqsdk_gateway.py      # 天勤网关
│
├── backtest/                     # 回测子系统
│   ├── backtest_engine.py        # 核心引擎 + 降级引擎
│   ├── data_loader.py            # 数据加载与划分
│   ├── report.py                 # 报告生成
│   └── comparison.py             # 对比分析
│
├── data/                         # 数据子系统
│   ├── exporter.py               # 天勤→CSV 导出
│   └── database.py               # SQLite 管理
│
├── doc/                          # 文档
│   ├── overview.md               # 项目概览
│   ├── architecture.md           # 架构设计（本文）
│   ├── configuration.md          # 配置说明
│   ├── usage-guide.md            # 使用指南
│   ├── api-reference.md          # API 文档
│   └── faq.md                    # 常见问题
│
└── .quant_shared_data/           # 共享数据目录
    ├── csv/                      # 历史行情 CSV
    ├── reports/                  # 回测报告 JSON
    └── quant_shared.db           # 元数据与日志库
```