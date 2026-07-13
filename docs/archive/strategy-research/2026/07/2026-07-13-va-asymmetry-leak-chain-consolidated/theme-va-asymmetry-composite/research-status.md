# va-asymmetry-composite · Research Status

> 类型：Research Status
> 状态：**假设证伪待重启（2026-07-13）** · 原研究侧 v1.0 metrics 被证明为未来信息泄漏产物

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-13 | **KF-5 登记**：4 层独立证据链证明 v1.0 归档 metrics 来自未来信息泄漏；因果修复后年化 -38.25% / 夏普 -1.60；主题原策略假设失去独立 alpha 支持；archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak 完成归档 |
| 2026-07-10 | 主题整体重置：v1.0（B0 冻结版）整目录归档至 `../../archive/strategy-research/2026/07/2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-10-va-asymmetry-composite/`；同名新主题重启，修订底层逻辑 + 探索计划；B0 作为 frozen control |
| 2026-07-09 | v1.0 阶段 1 降级 · B0 锁定 · KF-1~4 登记 |

## 当前待办

- [ ] 决策：接受原策略证伪，主题冻结进 `themes-frozen/`；或推进方向 A/B/C（见 archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak#README「剩余方向」）
- [ ] 若继续推进：重建因果版 B0 基线（原 B0 也用了泄漏特征）
- [ ] 若继续推进：更新 experimental-plan.md 加入「事件级精确截断 / intraday 特征替代」两条备选路径

## 关键发现清单

### KF-5 · 原研究侧 metrics 来自未来信息泄漏，主题假设失去独立 alpha 支持
- 类型：策略行为 + 方法论 + 假设证伪
- 状态：已证伪
- 证据：archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak
- 影响：（1）strategy-math-spec 中 daily `_spec` 系列特征的信息边界表述需要显式声明「T-1 日收盘后可得」；（2）experimental-plan.md 中所有相对 B0 的对比基线数字需重建（B0 本身也含泄漏）；（3）方法论遗产：截断法泄漏检测范式（同一份代码 × 两份数据 → 结果不同即铁证）可通用于所有后续主题。
- 日期：2026-07-13
