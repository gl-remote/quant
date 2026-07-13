# va-asymmetry-composite · Archive References

> 本文件登记本主题引用的归档批次。

## archive:2026-07-13-va-asymmetry-future-info-leak（未来信息泄漏铁证）

- 关系类型：假设证伪 + 方法论遗产
- 说明：**决定性归档** —— 用 4 层独立证据链（含截断法因果判据）证明 v1.0 归档 metrics 的 +63.44% 年化来自未来信息泄漏；`A3_skew_spec` / `daily_atr_spec` / `trend_ret_M_spec` / `close_session` 四个 daily 特征在事件触发时使用了当日 event_time 之后的 5m bars。修复后年化 -38.25% / 夏普 -1.60 / 1018 笔。**原策略假设无独立 alpha**。
- 方法论遗产：截断法泄漏检测范式（同一份代码 × 两份数据 → 结果不同即铁证）可通用于所有后续主题。
- 相关文件：archive:2026-07-13-va-asymmetry-future-info-leak#future-info-leak-verification

## archive:2026-07-13-va-asymmetry-engineering-fix（前置批次）

- 关系类型：继承 + 方法论证伪
- 说明：MAD-fix 分类器修复 + 工程侧初步对齐尝试。是发现泄漏之前的最后一次「归因到分类器/输入端」的努力。其结论（工程侧 15× 差距无法通过对齐消除）**被本次归档反证** —— 差距根源不在工程侧对齐，而在研究侧本身泄漏。
- 相关文件：archive:2026-07-13-va-asymmetry-engineering-fix#va_mad_fix_comparison/summary

## archive:2026-07-10-va-asymmetry-composite（本主题 v1.0 冻结版归档）

- 路径：`../../archive/strategy-research/2026/07/2026-07-10-va-asymmetry-composite/`
- 性质：整主题 v1.0 冻结快照，原作为本次重启的 **frozen control baseline**。
- 关键结论：
  - B0 = S1×W0×VW0：Sharpe 2.70 · 年化 15.10% · MaxDD −2.40%
  - 组合层（品种筛选 / 强度加权 / 多空权重）0/6 增量夏普通过 → 1/N 等权谜题复现
  - KF-1~4 登记：组合层无增量、S2 反向拖累 ΔSh −0.27
  - 真实杠杆在名义暴露上限（653% → 100% 砍 85% 交易）与事件去重窗口
- 引用触发：本次重启所有新逻辑相对此归档的 B0 做配对增量评估。
- **⚠️ 边界更新（2026-07-13）**：B0 本身也使用了泄漏版 daily 特征，其 15.10% 年化数字**同样受泄漏污染**。后续任何相对 B0 的配对增量评估都必须先重建因果版 B0 基线。
