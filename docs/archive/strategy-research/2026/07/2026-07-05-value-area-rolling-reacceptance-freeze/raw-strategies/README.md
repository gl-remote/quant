# raw-strategies：value-area 家族原始策略归档

> 类型：Archive / 原始工程策略代码
> 状态：已归档（2026-07-15）
> 所属阶段：value-area-rolling-reacceptance 冻结批次（作为 value-area 家族最终归档节点）
> 家族入口：[themes-frozen/value-area/README.md](../../../../../../research/themes-frozen/value-area/README.md)

## 1. 目录用途

本目录保存 value-area 家族三份工程侧策略代码，在 2026-07-15 从 `workspace/strategies/` 归档到本批次。

它们对应的研究主题已在 2026-07-03 / 2026-07-05 冻结（见家族 README），策略代码此前仍留在
`workspace/strategies/` 供历史复现使用，但一直未升级到活跃策略集，随家族已冻结、
`strategy-current.md` 明确无活跃主题，本次一并归档。

## 2. 文件说明

| 文件 | 对应主题 | 用途 |
|------|--------|------|
| `value_area_reacceptance_baseline_strategy.py` | value_area_reacceptance（冻结） | 旧 R27-R29 baseline 规则实现，用于结构诊断与随机基准对照的历史复现 |
| `value_area_random_baseline_strategy.py` | value_area_reacceptance（冻结） | 长期随机入场基准（复用 baseline 的事件、止损、退出口径），用于结构 vs 随机对照 |
| `value_area_multi_attempt_poc_reversion_strategy.py` | value_area_reacceptance R30 主线（Stage B v3 后证伪） | 严格按 R30 spec §1-§10 实现的四维正交入场 + 三类止盈候选 + 滚动 profile 刷新 |

## 3. 与工程侧代码的关系

已从 `workspace/strategies/` 移除，`workspace/strategies/__init__.py` 未变（这三份策略从未在 `__init__.py` 显式导出，仅通过 `load_strategy` 动态加载）。

相应的测试文件同步归档到 `../raw-tests/`：

- `test_value_area_reacceptance_baseline_strategy.py`
- `test_value_area_random_baseline_strategy.py`
- `test_value_area_multi_attempt_poc_reversion_strategy.py`

## 4. 使用注意

归档后：

- 相对 import 路径不再适配作为 Python 包直接导入；
- `value_area_random_baseline_strategy.py` 依赖同目录 `value_area_reacceptance_baseline_strategy.py` 的私有方法，
  只有两份文件一起复制回 active 目录才能继续工作；
- `value_area_multi_attempt_poc_reversion_strategy.py` 依赖硬编码的 `parse_contract` / `CONTRACT_SPECS`，
  相对路径不变，可直接从归档目录被脚本以 `from strategies.<name> import ...` 方式引用，
  但不建议长期依赖，应重新实现最小策略。

## 5. 相关文档

- [家族 README（value-area 冻结总结）](../../../../../research/themes-frozen/value-area/README.md)
- [value_area_reacceptance 主题目录（冻结）](../../../../../research/themes-frozen/value-area/value-area-reacceptance/)
- [value_area_rolling_reacceptance 主题目录（冻结）](../../../../../research/themes-frozen/value-area/value-area-rolling-reacceptance/)
- [Rolling 冻结摘要](../freeze-summary.md)
