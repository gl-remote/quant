# 回测系统架构设计

> 版本: 1.0.0 | 更新日期: 2026-05-23

---

## 1. 系统架构总览

```
┌──────────────────────────────────────────────────────────┐
│                       main.py                            │
│             (命令行入口 / 参数解析 / 命令分发)              │
└──────────┬───────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│                VnpyBacktestEngine                         │
│             (流水线编排 / 5 阶段协调)                       │
│                                                          │
│  run_full_pipeline(symbol)                               │
│    ├─ 1. load_csv_data()          ← data_loader.py       │
│    ├─ 2. split_datasets()         ← data_loader.py       │
│    ├─ 3. _run_single_backtest() ×3                       │
│    │     ├─ vnpy BacktestingEngine (优先)                │
│    │     └─ BacktestEngine 降级    (备用)                │
│    ├─ 4. generate_dataset_report() ← report.py           │
│    └─ 5. compare_datasets()       ← comparison.py        │
└──────────────────────────────────────────────────────────┘
           │
           ├─── data_loader.py ───  数据加载 / 划分 / 转换
           ├─── strategies/ ──────  vn.py CTA 策略适配
           ├─── report.py ────────  单数据集报告生成
           ├─── comparison.py ────  三阶段对比分析
           └─── config_manager.py ─  配置读取
```

## 2. 模块职责

### 2.1 `backtest/backtest_engine.py` — 核心引擎

**VnpyBacktestEngine** 是整个系统的核心编排器，负责：

- 解析和持有回测配置
- 调用 `data_loader` 加载和划分数据
- 在三阶段上分别执行回测 (优先 vnpy，自动降级)
- 调用 `report` 模块生成报告
- 调用 `comparison` 模块执行对比分析
- 返回完整的结果字典

**BacktestEngine** (降级方案) 是原始的内置回测引擎，在 vnpy 不可用时自动启用：

- 维护资金曲线和交易历史
- 计算最大回撤、夏普比率等绩效指标
- 生成控制台格式的报告

**TradeRecord / BacktestResult** 是回测过程中使用的数据类。

### 2.2 `backtest/data_loader.py` — 数据层

| 函数 | 职责 |
|------|------|
| `load_csv_data(data_dir, symbol)` | 从 CSV 目录加载品种历史数据 |
| `split_datasets(df, ...)` | 按比例划分训练/验证/测试集 |
| `df_to_vnpy_datalines(df, symbol)` | DataFrame 转 vnpy BarData 列表 |
| `get_dataset_info(df, name)` | 获取数据集统计摘要 |

### 2.3 `backtest/strategies/vnpy_ma_strategy.py` — 策略层

**VnpyMaStrategy** 是 vn.py CTA 策略的适配实现：

- 继承 `vnpy_ctastrategy.CtaTemplate` (vnpy 可用时)
- 实现 `on_init()` / `on_start()` / `on_stop()` / `on_bar()` 标准回调
- 包含双均线金叉/死叉信号逻辑、止损止盈风控
- vnpy 不可用时回退为普通 Python 类，保证兼容性

### 2.4 `backtest/report.py` — 报告层

| 函数 | 职责 |
|------|------|
| `generate_dataset_report(statistics, ...)` | 将回传统计转为结构化报告 JSON |
| `format_console_report(report, name)` | 格式化控制台输出 |
| `_extract_performance_metrics()` | 提取绩效指标 |
| `_extract_risk_metrics()` | 提取风险指标 |

### 2.5 `backtest/comparison.py` — 对比分析层

| 函数 | 职责 |
|------|------|
| `compare_datasets(train, val, test)` | 主入口，返回完整对比分析结果 |
| `_analyze_return_degradation()` | 收益递减分析 |
| `_analyze_risk_increase()` | 风险递增分析 |
| `_analyze_stability()` | 策略稳定性分析 (变异系数) |
| `_assess_overfitting()` | 过拟合综合评分 (0-100) |
| `format_comparison_report()` | 格式化对比报告 |

## 3. 数据流

```
CSV 文件 (.quant_shared_data/csv/*.csv)
  │
  ├── load_csv_data() ──→ pandas DataFrame
  │                         │
  │                         ├── split_datasets() ──→ train_df / val_df / test_df
  │                         │
  │                         └── df_to_vnpy_datalines() ──→ List[BarData]
  │                                                           │
  │                              ┌────────────────────────────┘
  │                              ▼
  │              vnpy BacktestingEngine
  │                ├─ add_strategy(VnpyMaStrategy)
  │                ├─ history_data = {vt_symbol: bars}
  │                ├─ run_backtesting()
  │                ├─ calculate_result() ──→ daily_results
  │                └─ calculate_statistics() ──→ statistics
  │
  ├── statistics ──→ generate_dataset_report() ──→ JSON 文件
  │
  └── train_report + val_report + test_report
        └── compare_datasets() ──→ comparison JSON + 控制台输出
```

## 4. 双引擎降级策略

```
    VnpyBacktestEngine._run_single_backtest()
                    │
                    ▼
          ┌── HAS_VNPY? ──┐
          │ Yes           │ No
          ▼               ▼
  _run_vnpy_backtest()   _run_fallback_backtest()
  (vnpy BacktestingEngine)  (BacktestEngine 内置)
```

当 `vnpy` 和 `vnpy_ctastrategy` 包未安装时，系统自动使用内置的 `BacktestEngine` 执行回测，核心功能保持一致，仅在统计指标精度上略有差异。

## 5. 目录结构

```
backtest/
├── __init__.py                   # 公共导出
├── backtest_engine.py            # 核心引擎 (VnpyBacktestEngine + BacktestEngine)
├── data_loader.py                # 数据加载与划分
├── report.py                     # 报告生成
├── comparison.py                 # 对比分析
└── strategies/
    ├── __init__.py
    └── vnpy_ma_strategy.py       # vn.py CTA 策略适配
```

## 6. 依赖关系

```
comparison.py ────→ numpy
report.py ────────→ numpy, json
backtest_engine.py → data_loader, strategies, report, comparison, numpy
data_loader.py ───→ pandas, (vnpy.trader.object)
vnpy_ma_strategy.py → (vnpy_ctastrategy, vnpy.trader)
```