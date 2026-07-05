# structural-shaping-alpha · Research Status

> 类型：Research Status
> 状态：**立题（假设生成期）**
> 最近更新：2026-07-06（experiment-plan v2 gatekeeper 精简改造）
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)

## 一句话结论

**主题刚立题，尚无实验结果**。核心问题："结构塑形技巧本身是否具有
独立 alpha？"—— v2 改为行业共识组合 gatekeeper，先回答"有没有"再决定
是否深挖。

## 边界

1. **不使用 value-area 家族已证伪的入场信号**（POC / reacceptance / rolling POC / 距离档过滤）
2. **入场固定为 no_trigger baseline** + DirRandom（纯随机方向），避免变成入场信号研究
3. **阶段 1 测"整机"而非拆零件**：6 种行业共识完整组合（仓位 + 止损 + 止盈 + 时间 + trailing）直接对比
4. **判据必须多层对照**：Combo E 基准对照 + 配对差值检验 + cluster bootstrap

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-05 | 初版立题，v1 单维度扫描实验计划 |
| 2026-07-06 | v2 gatekeeper 精简改造：6 组合 × 120 次回测替代 v1 四子维度 × ~18,000 次 |

## 下一步

**阶段 1 · 行业共识组合 Gatekeeper**：

- 6 种行业共识组合（A 教科书 / B 短线 / C 波段 / D 机构 / E 基准 / F 盈亏保护）
- uniform_20bar 采样 + DirRandom 方向 + 20 合约
- 120 次回测，预估 10-20 分钟
- 任何组合显著优于 E → 进入阶段 2 加严验证
- 全部 ≈ 0 → 主题冻结

判据细节见 [experiment-plan.md](experiment-plan.md)。

## 关键发现清单

主题重要结论的唯一入口。格式与更新规则见
[`quant-research-layout` skill § 关键发现清单](../../../../.trae/skills/quant-research-layout/SKILL.md)。

_立题阶段尚无实验结论，占位。首次实验后按下列格式追加条目：_

```markdown
### KF-1 · <一句话结论>
- 类型：策略行为 / 方法论 / 假设证伪
- 状态：已证实 / 已证伪 / 边界待定
- 证据：[workbench 或 archive 链接]
- 影响：对 strategy-math-spec / experiment-plan / 后续主题的具体影响
- 日期：YYYY-MM-DD
```

## 立题日期

**2026-07-05**
