# raw-strategies：va-asymmetry-composite 工程侧策略归档

> 类型：Archive / 原始工程策略代码
> 状态：已归档（2026-07-15）
> 所属阶段：va-asymmetry 错误路径链条归并封装 · va-asymmetry-composite 主题
> 阶段入口：[../README.md](../README.md)

## 1. 目录用途

本目录保存 va-asymmetry-composite 主线策略在工程侧 (`workspace/strategies/`) 的完整实现代码。

原本用于回答：

```text
分类器 v4.0 六阵营 tier × spec §2/§3 K_SL / H_vol / RiskPerTrade 组合，
在工程侧 5m bar 全量 145 合约上是否复现研究侧 63.44% 年化 / 3.47 夏普？
```

结论：

```text
2026-07-13 因果修复后 -38.25% 年化 / -1.60 夏普 / 1018 笔，
假设由未来信息泄漏支撑（见 ../2026-07-13-va-asymmetry-future-info-leak/），
无实盘上线价值。主题目录整体归档，工程侧代码从 workspace/strategies 移除。
```

## 2. 文件说明

| 文件 | 用途 |
|------|------|
| `va_asymmetry_composite_strategy.py` | B 层执行核心 · 消费 A 层 tier/direction/daily_atr_bps · 严格实现 spec §2/§3 |

## 3. 与 active 代码的关系

已从 `workspace/strategies/__init__.py` 移除 `VAAsymmetryCompositeStrategy` / `VAAsymmetryCompositeParams` 导出。归档后：

- 相对 import 路径不再适配作为 Python 包直接导入；
- `scripts/tools/backtest-va.sh` 已同步归档到 `../raw-scripts/`；
- 若未来要延续 va-asymmetry 假设，应先重建因果版 daily 特征管道（见封装 README §五），再基于新 pipeline 从零实现最小策略，不复用本目录代码。

## 4. 相关文档

- [封装批次 README（必读）](../../README.md)
- [2026-07-13 未来信息泄漏验证](../../2026-07-13-va-asymmetry-future-info-leak/)
- [va-asymmetry-composite 主题目录](../)
- [../raw-scripts/backtest-va.sh](../raw-scripts/backtest-va.sh)
