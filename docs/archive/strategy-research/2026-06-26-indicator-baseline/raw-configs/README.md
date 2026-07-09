# raw-configs：indicator-baseline 阶段研究配置归档

> 类型：Archive / 原始研究配置  
> 状态：已归档  
> 所属阶段：Indicator Baseline MA 信号消融（2026-06-26）  
> 阶段文档：[../ma-positive-expectancy.md](../ma-positive-expectancy.md) §3.2 信号消融与反向退出

## 1. 目录用途

本目录保存 Indicator Baseline（2026-06-26）阶段 MA 策略信号消融（ablation）实验用的参数配置。
对应 ma-positive-expectancy.md §3.2 中：

> 为拆解信号，MA 增加 `signal_profile`：`sma_only` / `sma_macd` / `sma_kdj` / `full`。

## 2. 文件说明

| 文件 | `signal_profile` | 核心参数组 | 备注 |
|------|:---:|:---|:---|
| `ma_ablation_sma_only.toml` | `sma_only` | SMA 3/10 · stop 0.3 · tp 0.5 · ATR 5.0/5.0 · trailing 0.1/0.5 | 仅 SMA 金叉死叉的纯均线 baseline |
| `ma_ablation_sma_kdj.toml` | `sma_kdj` | SMA 3/10 + KDJ 30/70 超买超卖 · 其余与 sma_only 一致 | SMA + KDJ 双重筛选的消融组合 |
| `ma_ablation_sma_macd.toml` | `trend_macd` | SMA 30/90（慢参数）· stop 0.04 · tp 0.10 · ATR 2.5/4.0 · trailing 2.0/0.3 · min/max_hold 240/720 bar | 慢均线 + MACD 趋势版，接近 1~2 天持仓 |
| `ma_ablation_full.toml` | `full` | SMA 3/10 · stop 0.3 · tp 0.5 · ATR 5.0/5.0 · trailing 0.1/0.5 · exit_on_reverse | 完整版：SMA + MACD + KDJ 全部启用 + 反向信号退出 |

## 3. 重要注意事项

这些配置只作为历史实验参数记录，不保证：

- 与当前 MA 策略默认参数一致；
- 与当前 CLI / data_requirements 完全兼容；
- 运行结果可直接覆盖 ma-positive-expectancy.md §3.2 的消融结论。

如需复现，应优先根据 ma-positive-expectancy.md §3.2 的表格核对消融结果，
再用本目录配置做一致性验证。
