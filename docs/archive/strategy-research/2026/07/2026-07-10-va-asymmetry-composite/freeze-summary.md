# va-asymmetry-composite · v1.0 Freeze Summary（归档快照）

> 类型：Archive Freeze Summary
> 归档日期：2026-07-10
> 来源：docs/research/themes/va-asymmetry-composite v1.0（B0 冻结版）
> 去向：本目录为旧版整主题归档；同名新主题已重启于 docs/research/themes/va-asymmetry-composite/

## 一句话

va-asymmetry-composite 组合层研究完成：B0 = S1×W0×VW0 即最优
（Sharpe 2.70 · 年化 15.10% · MaxDD −2.40%），组合层 0/6 增量夏普通过 →
「优化权重跑不赢 1/N 等权」谜题复现。年化未达 18% 目标，瓶颈在名义暴露压缩
（日均 653% → 压到 100% 砍掉 85% 交易）。2026-07-10 整体重置为新主题，
修订底层逻辑 + 探索计划。

## 关键结论（供后续引用）

- **B0 配置**：S1 全品种 5 档 + W0 等权 + VW0 等权 + 塑形基线
  （多 SL 1.0 ATR / 8h · 空 SL 2.5 ATR / 10h · 无 TP / 无 TH）
- **KF-1**：组合层（强度 / 多空加权）无增量夏普
- **KF-2**：信号强度（W1）与收益无区分度 ΔSh = +0.00
- **KF-4**：按类型筛选 S2 反向拖累 ΔSh = −0.27
- **名义上限 100% 为瓶颈**：653% → 100% 砍 85% 交易，是年化卡 15% 未达 18% 的高概率根因
- **事件去重 8h**（v4.0 分类器契约不变）
- **方法论遗产**：组合层 exhausted 后真实杠杆在名义上限 + 事件层选择 / 择时，而非组合加权

## 文档清单（本目录）

README · strategy-math-spec(v1.0) · parameter-selection-spec(v0.2) ·
experiment-plan · research-status · implementation-notes · archive-references

> 本归档作为**同名重启主题的 frozen control baseline**：任何新底层逻辑提案
> 必须相对此处 B0 做同一批事件的配对增量（≥0.2 夏普）评估。
