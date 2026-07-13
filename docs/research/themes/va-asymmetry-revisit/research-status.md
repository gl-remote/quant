# va-asymmetry-revisit · Research Status

> 类型：Research Status
> 状态：**立题态（2026-07-13）** · 资产清单已从 leak-chain 路径复盘提炼完成，尚未开始实验

## 一句话结论

va-asymmetry 系列所有性能类数字结论已作废（daily 特征未来信息泄漏），但**部分假设的因果叙事不依赖 daily 泄漏值**，且这条错误路径本身沉淀了一套**决策链条明确的因子研发流程**——本主题的任务是**分离出可复用流程 + 未验证猜想集**两份资产，为后续任何主题服务；不预设 va-asymmetry 假设最终成立。

## 边界

- 本主题**只做资产分离**：把"流程约束"（默认参数/硬约束/方法论）与"待验证猜想"（core alpha 假设）拆开；不承担为原策略翻案。
- **不复用旧数字**：任何形如"Sharpe X / 年化 Y%"的历史数字均不写入本主题；每个猜想若开始验证，都从零重跑因果版基线。
- **不复用被证伪的组合层结构**：原 B0=S1×W0×VW0 视为已证伪，仅在流程节点中作为反例登记。
- **不复用任何 daily 泄漏输入**：所有 daily 派生特征进入实验前必须先过截断法（见 KF-0）。

## 下一步

- [ ] 与用户对齐**首批猜想验证优先级**（默认建议：H-1 A3_skew 独立方向 alpha + H-11 τ_signed timing 特征 + H-3/H-4 多空机制假设；理由与全量清单见 [hypothesis-inventory.md](hypothesis-inventory.md)）
- [ ] 若确认首批优先级，再建 `experiment-plan.md` 承载候选矩阵与验证顺序
- [ ] 挑选新方向验证时，**流程侧默认沿用** [factor-research-workflow.md](factor-research-workflow.md)，不重新扫参已收敛的架构参数

## 文档地图

| 文档 | 承载 |
|---|---|
| [README.md](README.md) | 目录索引 |
| [research-status.md](research-status.md) | 本文件：状态 / 边界 / 下一步 / KF 清单 |
| [factor-research-workflow.md](factor-research-workflow.md) | **可复用因子研发流程**（从 va-asymmetry 路径复盘提炼；11 个关键决策节点，每节点 = 问题 + 历史选择 + 结论 + 复用建议） |
| [hypothesis-inventory.md](hypothesis-inventory.md) | **未验证猜想集**（H-系列，核心 alpha 假设；每条 = 假设 + 出处 + 泄漏关系 + 重测方式） |
| [archive-references.md](archive-references.md) | 与本主题相关的 archive 批次索引与关系 |

## 关键发现清单

### KF-0 · 立题基线：va-asymmetry 家族的分类器输入侧必须先过截断法
- 类型：方法论
- 状态：已证实
- 证据：archive:2026-07-13-va-asymmetry-leak-chain-consolidated#README
- 影响：本主题（及沿用本主题流程的任何后续主题）所有实验的第一步都必须用截断法（`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py`）验证特征输入无泄漏，才能进入后续节点。作为流程**第 0 号硬约束**登记。
- 日期：2026-07-13

（本主题未来若产生新的 KF-N，追加于此。）
