# VA Asymmetry Composite · 工程化修复批次

> 类型：Archive / 策略实验摘要
> 状态：已完成（工程侧可运行 ✅；研究↔工程收益差距 ⚠️ 待解决）
> 开发分支：`fix/va-asymmetry-atr-source`
> 开分支 hash：`33623f2`
> 归档日期：2026-07-13

## 背景

VA Asymmetry Composite 策略此前依赖外部 timeline parquet 做 A 层分类，CLI backtest 不可直接运行。本批次将 A 层分类从外部依赖改为策略内部 on_bar 自算，并修复了 MAD min_periods、pandas 3.0 兼容等问题。

同时，全量研究回测跑出了年化 63.44% / 夏普 3.47，但工程侧 CLI 回测仅 ~4-12%，差距 15×，根因已定位为 ATR 公式/K_S_SL/Cap/止损粒度/bar 来源 5 项差异（详见 workbench 诊断报告）。

## 核心结果

| 指标 | 研究侧全量回测 |
|------|---------------|
| 年化收益 | 63.44% |
| 夏普 | 3.47 |
| MaxDD | -12.30% |
| 胜率 | 62.8% |
| 月度胜率 | 81.2% |
| 交易笔数 | 613 |
| 覆盖合约 | 139/143 |

## 产出物

### 脚本（7 个）

| 脚本 | 用途 |
|------|------|
| `va_mad_fix_full_backtest.py` | 主回测对比：旧版 vs 新版 MAD fix，143 合约全量 |
| `va_trend_offset_deep_diag.py` | trend 偏移根因诊断 |
| `va_trend_offset_fix_compare.py` | trend 偏移修复前后对比 |
| `va-asymmetry-composite-batch-backtest.py` | 多品种批跑 |
| `va-asymmetry-composite-check-window-effect.py` | W 参数敏感性 |
| `va-asymmetry-composite-compare-norm-methods.py` | 归一化方式 A/B 测试 |

### 数据（va_mad_fix_comparison/）

- `events_new.parquet` / `events_old.parquet`：新版/旧版分类事件（36,625 行）
- `trades_new.parquet` / `trades_old.parquet`：新版/旧版逐笔交易记录
- `metrics_new.json` / `metrics_old.json`：回测指标
- `summary.md`：对比总结

## 关键修复

1. MAD min_periods = max(3, window//4)（修复小数据集全部 NaN）
2. pandas 3.0 groupby.apply 丢弃 group key 列的回填
3. 跨周期指标持久化（1d→1m）索引不对齐修复
4. ClassifierConfig 默认窗口 20→10

## 待解决

工程侧 vs 研究侧收益 15× 差距，详见 `docs/workbench/va-asymmetry-composite-engineering-diagnosis.md`。
