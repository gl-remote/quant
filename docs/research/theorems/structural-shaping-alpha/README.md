# Theorems · structural-shaping-alpha

> **主题定位**：`structural-shaping-alpha` 主题的**稳定数学结论集**。
> 从主题活跃期 spec 提炼；只承载数学骨架 + 严格证明，不承载实证锚点、参数扫描、KF 演化叙事。
> **主题已于 2026-07-24 冻结归档**：[archive:2026-07-24-structural-shaping-alpha-freeze](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/)（含完整 KF-1..27 演化史、22 个研究脚本、shaping-theory 完整叙事）。本目录内容作为主题稳定内核**长期保留**。

---

## 文档地图

| 文件 | 回答的问题 | 稳定性 |
|------|-----------|--------|
| [when-barrier-shaping-yields-alpha.md](when-barrier-shaping-yields-alpha.md) | 在什么条件下双 barrier 塑形容器 $(K_S, K_T, T)$ 能满足 $\mathbb{E}[E_{\text{net}}] > 0$？ | 入库 2026-07-24 |
| [winrate-payoff-tradeoff-under-frictions.md](winrate-payoff-tradeoff-under-frictions.md) | 给定盈亏比 $R$ 与摩擦成本，胜率的市场刚性边界、实盘生存区间、长期收益与破产风险如何量化？ | 入库 2026-07-24 |

---

## 阅读顺序

两份文档**互补**、可独立阅读：

- **when-barrier-shaping-yields-alpha.md** —— 严格数学契约，回答"塑形何时有 alpha"，14 章 + 3 附录，用 Doob OST 两前提对偶给出充分条件；
- **winrate-payoff-tradeoff-under-frictions.md** —— 论文式框架，回答"胜率-盈亏比权衡与摩擦修正"，8 章 + 参考文献 + 挑战备注，用四层约束（市场 · 资金 · 频率 · 成本）给出实盘参数选择依据。

**共享底层**：两者都以对称随机游走首达定理 $p_0 = 1/(1+R)$ 为基础。when-barrier-shaping 用它做"零漂移 null"，winrate-payoff 用它做"胜率下界"。

---

## 与已归档主题的关系

- 主题 `structural-shaping-alpha` 的活跃期 math-spec 已迁移至本目录（`when-barrier-shaping-yields-alpha.md` + `winrate-payoff-tradeoff-under-frictions.md`）；
- 主题目录本身于 2026-07-24 冻结归档：[archive:2026-07-24-structural-shaping-alpha-freeze](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/)（含 README / research-status / experiment-plan / archive-references / shaping-theory + 22 个研究脚本）；
- 若定理需要迭代（更严格证明、更好记号、新推论），在本目录直接修改；
- 若未来发现新的 alpha 通道或稳定数学结论（P1/P2 之外的第三条 Doob OST 前提失效路径），追加新文件到本目录。

---

## 命名引用

其他文档引用本目录内容时使用命名引用：

```markdown
theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha
```

或定位到具体命题（章节锚点）：

```markdown
theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha#命题9.2
```
