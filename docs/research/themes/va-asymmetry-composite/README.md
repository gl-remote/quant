# va-asymmetry-composite · 主题 README

> 类型：Research Theme
> 状态：**重启开发态（2026-07-10）** · 旧 v1.0 已归档
> 上游分类器（v1.0 控制基线）：theme:poc-value-area-asymmetry#classifier-math-spec v4.0
> 塑形参考（v1.0）：theme:structural-shaping-alpha#first-passage-designer-math-spec

## 0. 本次变动（2026-07-10 重启）

本主题于 2026-07-10 整体重置：

- **旧版 v1.0（B0 = S1×W0×VW0 冻结版）已整目录归档**至
  `../../archive/strategy-research/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-10-va-asymmetry-composite/`。
- 重置原因：需修订**底层逻辑**与**探索计划**，幅度超出 v1.0 冻结契约的可调范围。
- 旧版全部信息（KF-1~4 结论、1/N 等权谜题注、§11 审计附录、B0 配置）均保留于归档，**不丢失**。
- 本主题为**同名重启**，不新建相似主题，避免主题 sprawl。

## 1. 控制基线（必须相对其评估）

v1.0 的 B0 = S1×W0×VW0（Sharpe 2.70 · 年化 15.10% · MaxDD −2.40%）作为
**frozen control baseline**。任何新底层逻辑的提案，必须用**同一批事件做配对增量**
（净夏普增量 ≥ 0.2）证明优于 B0，否则不采用。B0 完整定义见归档：
`../../archive/strategy-research/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-10-va-asymmetry-composite/strategy-math-spec.md`。

## 2. 待定义（本次重启的核心工作）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 底层逻辑（信号 / 分类器 / 组合） | 🔴 待定义 | 重启后重写，见 strategy-math-spec.md |
| 探索计划 | 🔴 待定义 | 重写 experiment-plan.md |
| 参数选择 spec | ⚪ 待重建 | 待底层逻辑定型后回填 |

## 3. 文档地图

| 文档 | 说明 |
| --- | --- |
| [strategy-math-spec.md](strategy-math-spec.md) | v0.1 重启立题占位（控制基线引用 + 待定义项） |
| [research-status.md](research-status.md) | 重启态 + 变更记录 |
| [archive-references.md](archive-references.md) | 指向归档 v1.0 的关键结论 |
| （规划中）experiment-plan.md | 探索计划，待定义 |
| （规划中）parameter-selection-spec.md | 参数表，待重建 |
