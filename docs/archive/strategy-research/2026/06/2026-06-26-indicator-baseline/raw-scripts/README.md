# raw-scripts：indicator-baseline 阶段研究 runner 归档

> 类型：Archive / 原始研究脚本  
> 状态：已归档  
> 所属阶段：Indicator Baseline ATR / MA 双策略基线阶段  
> 阶段文档：[../ma-positive-expectancy.md](../ma-positive-expectancy.md) · [../strategy-atr-tuning.md](../strategy-atr-tuning.md)

## 1. 目录用途

本目录保存 Indicator Baseline（2026-06-26）阶段临时编写的研究 runner。
这些脚本用于 MA / ATR 经典指标策略的信号密度、释放机制变体和退出原因分析，
不再作为 active `scripts/tools` 工具维护。

## 2. 文件说明

| 文件 | 用途 |
|------|------|
| `atr_signal_density_loop.py` | ATR 策略信号密度研究 loop，覆盖 r13_base / weak_cooldown / fast_release / reverse_release 四组 ATR 释放机制变体，输出交易数、持仓周期和 exit_reason 分布 |

## 3. 重要注意事项

这些脚本只作为历史复现素材，不保证与当前策略代码、CLI / config 完全兼容。
如需 ATR 策略实验，应优先重新设计最小 runner。
