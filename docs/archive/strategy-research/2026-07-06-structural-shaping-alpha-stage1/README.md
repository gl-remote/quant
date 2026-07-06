# 2026-07-06 · structural-shaping-alpha 阶段 1 归档批次

> 类型：Archive Batch
> 家族：structural-shaping-alpha（尚未成家族，暂用主题名 slug）
> 主题：`theme:structural-shaping-alpha`
> 结论标签：❌ 证伪（主假设）· 🧪 方法论（KF-1..9）
> 归档日期：2026-07-06

## 一句话结论

**在 DirRandom no-signal baseline 下，7 个行业共识组合 + 8 个探索性 combo
（A-N）全部未通过独立 alpha 判据**——结构塑形不构成独立 alpha 源。产出
9 条方法论 KF + 一套 First-Passage Designer 数学工具（spec + 代码 + 对照表）。

## 主题状态

**阶段 1 完成 · 主题不冻结**（experiment-plan v2.2 已重构阶段 2 为塑形受益
条件扫描 · 2a 待方向 alpha 主题触发 · 2b/2c 随时可拉起）。主题目录仍在
`theme:structural-shaping-alpha`，不迁入 themes-frozen。

## 批次内容

```
2026-07-06-structural-shaping-alpha-stage1/
├── README.md                            ← 本文件
├── stage-summary.md                     ← 阶段 1 判决 + 9 条 KF 索引
├── stage1-gatekeeper-report.md          ← 原 workbench:structural-shaping-alpha-gatekeeper
├── first-passage-lookup-tables.md       ← 工具对照表（原 workbench）
└── raw-scripts/
    ├── structural_shaping_gatekeeper.py     ← 5m 阶段 1 runner（含 A-N combo）
    ├── structural_shaping_gatekeeper_15m.py ← 15m 跨周期复核 runner
    └── first_passage_designer.py            ← First-Passage Designer v1 实现
```

## 主要方法论遗产（进入 kf:structural-shaping-alpha#KF-1..9）

- **KF-1**：$\nu = 0$ 无漂移 GBM 下 $E[\text{gross}] \equiv 0$，加成本 $E[\text{net}] \equiv -2c$——结构塑形不是独立 alpha 源
- **KF-2**：Trailing 分两类——急性 breakeven 显著负 edge；延迟 chandelier 短期区首次出现正 gross
- **KF-3**：Trailing 组合机械诊断准则（armed / 缓冲 / 是否配止盈三元组）
- **KF-4**："少输"型 paired 显著性 ≠ 独立 alpha（B/K 二维拆分证明）
- **KF-5**：扁平 ATR 成本模型跨品种低估 4.5 倍（已升级至 quant-research-methodology skill §5.1）
- **KF-6**：近距（K<3 ATR）被首达定理支配 · 远距（K>7 ATR）可捕获 tail 但样本极偏
- **KF-7**：5m×SCALE=5 的正 mean 是"重采样伪影"（M/N 15m 复核证伪 · L 保留边界）
- **KF-8**："数学正 edge" ≠ 工业可用 alpha（需过 framework §5 四道账户闸门）
- **KF-9**：归因必须用 $\nu = \mu - \sigma^2/2$，不能用 $\mu$（Itô 凸性修正）

## 工具遗产

**First-Passage Designer**（`theme:structural-shaping-alpha#first-passage-designer-math-spec`）：

- 数学 spec：GBM 首达定理 + 有限时间修正 + 凯利可行区间 + $\mu_{\text{implied}}$ 反算
- 代码 v1：`raw-scripts/first_passage_designer.py`，6 条数学恒等式自检通过
- 对照表：5 张（$\lambda=0$ 恒等式 · μ 敏感性 · $T^*$ 分界 · combo 判决 · $\nu_{\text{implied}}$ 反算）
- 未来所有 combo 参数在实测前可先用工具做数学预筛

## 关联

- 上游 baseline：archive:2026-06-29-structural-alpha-random-baseline（继承 DirRandom 采样定义）
- 反例：archive:2026-07-05-value-area-rolling-reacceptance-freeze（value-area 家族证伪）
- 上游 Roadmap：roadmap:strategy-research-framework §1 · §5

## 立题扫描指引

新主题读本批次的**首要入口**：`stage-summary.md`（一句话结论 + KF 索引）。
仅需数学工具时读 `first-passage-lookup-tables.md` 的**表 1 恒等式校验**。
