# va-asymmetry-composite · Stage 0 立题复现（Workbench）

> 类型：Workbench / 实验流水
> 状态：**Stage 0 复现通过**（archive 基准精确复现 · Run-2 冻结门控待启动）
> 开发分支：`experiment/va-asymmetry-composite`
> 开分支 hash：`57929794929a53c52d7450a11479240cb8f2f355`（2026-07-09，父分支 `dev/0.5`）
> 目标 dev 分支：`dev/0.5`
> 主题 README：[va-asymmetry-composite](../research/themes/va-asymmetry-composite/README.md)
> 阶段计划：[experiment-plan.md](../research/themes/va-asymmetry-composite/experiment-plan.md)
> 立题起点归档：[2026-07-09-poc-va-shaping](../research/archived-notes/2026-07-09-poc-va-shaping/README.md)

## 1. 阶段 0 目标

精确复现 `archive:2026-07-09-poc-va-shaping` 的基准组合，确认 pipeline 一致：

```text
- 分类器：poc-value-area-asymmetry v4.0（6 类合并版 · 14 条严格性约束）
- 塑形参数：SL=1.0 ATR · TP=1.4 ATR · TH=8h holding
- 成本口径：c_realistic（滑点 0.15 ATR × (0.5+SlippageTier) + 手续费 0.03% 双边）
- 名义暴露：100% 不压缩 · 按期货保证金制度估算
- 复现判据：事件数 / 各 tier 顺序 / Sharpe / MDD / 年化净收益 相对偏差 ≤ 5%
- 基准参考值（archive 报告）：年化净 15.45% · Sharpe 2.23 · MaxDD -7.51 · 胜率 60.3% · 盈亏比 1.41
```

失败即暂停，回修分类器或数据对齐问题；通过后进入阶段 1 Gatekeeper。

## 2. 立题交付清单（已完成 · 2026-07-09）

### 2.1 主题目录标准文档（7 份）

| 文档 | 位置 | 内容摘要 |
| --- | --- | --- |
| README | [va-asymmetry-composite/README.md](../research/themes/va-asymmetry-composite/README.md) | 策略蓝图 / 3 模块 / 5 阶段路线 / 风险缓释 |
| research-status | [research-status.md](../research/themes/va-asymmetry-composite/research-status.md) | 阶段 0 边界 / 分类器合同冻结 / 塑形参数 L2 锁定 / 下一步 |
| strategy-math-spec | [strategy-math-spec.md](../research/themes/va-asymmetry-composite/strategy-math-spec.md) | 6 tier 数学定义 / ATR 归一化 / 塑形参数 / 仓位 sizing / ν_implied 归因 |
| experiment-plan | [experiment-plan.md](../research/themes/va-asymmetry-composite/experiment-plan.md) | 5 阶段门控（复现→筛选→组合→OOS→工程）· 统计判据 |
| parameter-selection-spec | [parameter-selection-spec.md](../research/themes/va-asymmetry-composite/parameter-selection-spec.md) | L0-L4 参数层级 / 回填模板 / 品种类型映射 |
| implementation-notes | [implementation-notes.md](../research/themes/va-asymmetry-composite/implementation-notes.md) | Stages 0-3 向量化模拟 / Stage 4 vnpy 集成 |
| archive-references | [archive-references.md](../research/themes/va-asymmetry-composite/archive-references.md) | archive:2026-07-09-poc-va-shaping（立题起点）· 2026-07-08 / 2026-07-06 |

### 2.2 总入口登记（已完成）

| 文档 | 变更要点 |
| --- | --- |
| [strategy-current.md](../research/strategy-current.md) | 一句话结论 / 当前主题表 / 基础设施（新增 3 个策略代码占位）/ 关键归档表（新增 3 行）/ 11 条前置约束 / 文档地图 / AI 工作规则 |
| [research/README.md](../research/README.md) | 当前主题表（3 活跃 + 2 冻结）/ 主线摘要 / 关键文档（按时间倒序）/ AI 阅读顺序 |

### 2.3 上游主题反向登记（pull 模式 · 已完成）

| 上游主题 | 变更要点 |
| --- | --- |
| [poc-value-area-asymmetry research-status](../research/themes/poc-value-area-asymmetry/research-status.md) | 主动性研究暂停 · 登记下游 va-asymmetry-composite · KF-24 占位替换为真实链接 · 变更记录追加 2026-07-09 · 下一步声明转移到下游 |
| [structural-shaping-alpha research-status](../research/themes/structural-shaping-alpha/research-status.md) | 降级为必要条件 & 工具资产层 · 登记下游引用 · 阶段 2a 拉起声明 · 变更记录 / 下一步追加 · L2 塑形参数冻结 |

## 3. 立题边界（不变量）

```text
1. 分类器 v4.0 合同冻结：6 类合并 tier + 14 条严格性约束 + per-contract rank 单位
   除非发现数据 bug，否则不调 tier 门槛（L1 级参数）
2. 塑形基准参数冻结（B0）：无 TP · 多 SL=1.0 ATR / 8h · 空 SL=2.5 ATR / 10h（L2 级参数）
   阶段 2 起可在 ±30% 范围内扫描，但基准不变
3. 成本模型冻结：contract_specs 真实成本（佣金 + tick 滑点，L2 级）· 不做更宽松的成本假设
4. L_seg2_low_flat 淘汰：该 tier 在 archive 塑形扫描中无稳定收益，组合关不纳入
5. 名义暴露必须压缩：结果需同时报告 100%/200%/400% 三档，禁止用无约束杠杆美化夏普
6. 顺序禁止反转：先 Stage 0 复现，再 Stage 1 候选，再 Stage 2 组合搜索；
   未通过前一关不得进入下一关
```

## 4. 下一步操作清单（复现通过 · 2026-07-09）

- [x] 从 `archive:2026-07-09-poc-va-shaping/raw-scripts/` 提取 Stage 3 基准脚本 → 直接复用 `poc_va_risk_managed_v2.py`（产出参考值的那版）
- [x] 确认分类器 v4.0 合同：tier 判定表 + 14 条严格性约束，与主题 parameter-selection-spec 交叉验 → `A_TIER_RAW`(13) + `TIER_TO_V40`(→6 类) 一致
- [x] 重跑基准组合（相同品种集合 / 时间窗 / per-tier 塑形）→ 直接跑 archive 脚本，未另建主题 pipeline
- [x] 比对关键指标：事件总数 / 年化净收益 / Sharpe / MaxDD / 胜率 / 盈亏比 → **全部精确复现（偏差 ≈0%）**
- [x] 通过：追加复现结果表（见下）→ 下一步写 Stage 1 启动计划
- [ ] **待办**：新主题 pipeline 落地 Run-2（uniform 多8h/空10h + 冻结 B0 门控）并自测

### 4.1 复现结果表（Run-1 · archive 精确复现）

> 执行：`uv run python docs/research/archived-notes/2026-07-09-poc-va-shaping/raw-scripts/poc_va_risk_managed_v2.py`
> 数据跨度：2023-09-26 ~ 2026-05-27（975 日历日，197 日有触发，占 20.2%）

| 指标 | 本次复现 | archive 参考 | 偏差 | 判据(≤5%) |
| --- | --- | --- | --- | --- |
| A 级事件数 | 1545 | — | — | — |
| 年化净收益 | 15.45% | 15.45% | 0.00% | ✅ |
| Sharpe | 2.23 | 2.23 | 0.00% | ✅ |
| MaxDD | −7.51% | −7.51% | 0.00% | ✅ |
| 胜率 | 60.26% | 60.3% | −0.04pp | ✅ |
| 盈亏比（avg W/L） | 1.414 | 1.41 | +0.3% | ✅ |
| Calmar | 2.06 | — | — | — |

**多空分档**（验证不对称性）：
- 空头 Sharpe 1.77（年化 10.77%）> 多头 Sharpe 1.40（年化 4.69%）→ 空头是主 alpha 来源，与主题名一致
- 逐 tier 胜率：L_seg12 62.3% / L_seg3 60.6% / S_seg12 62.0% / S_seg2 52.8% / S_seg34 61.9%

**结论**：核心结论「文档里的基准组合可以盈利」成立，5 项关键指标全部精确复现（偏差 ≤0.05pp / ≤0.3%），通过 Stage 0 复现判据。

### 4.2 复现口径说明（与 §1 立题草案的差异 · 需回修 §1）

本次复现跑的是 archive **实际落地脚本**，其口径与 §1 立题草案字面不一致；正是按"实际脚本"才复现出参考值：

| 维度 | §1 立题草案 | 实际复现口径（archive 脚本） | 处理 |
| --- | --- | --- | --- |
| TP 硬止盈 | TP=1.4 ATR | **无 TP**（SL + 时间退出） | 以实际脚本为准，§1 应删 TP |
| 成本 | 0.15 ATR 滑点 + 0.03% 手续费 | **contract_specs 真实成本**（佣金+滑点 tick，≈4.3 元/手佣金） | 以实际脚本为准，§1 成本口径过高会打爆收益 |
| ATR 窗口 | 未明说 | **daily_atr_10_bps**（10 日） | 以实际脚本为准 |
| 持仓期 | TH=8h（两方向） | per-tier：多 6/10h、空 8/10h（Run-1）；新主题 B0 冻结多8h/空10h（Run-2 待做） | Run-1 用 archive per-tier，Run-2 用冻结 B0 |

> ⚠️ 脚本主标题"保证金≤80%"标签有歧义：日志 `保证金触发: 0 天`，实际约束是 **名义 100% 上限**（margin 上限从未触发）。主块结果等价于敏感性表 `保证金≤50%` 行（15.45%）；敏感性表 `保证金≤80%` 行因名义上限放宽到 200% 而给出 24.37%（非本复现口径）。

## 5. 开发分支信息

```text
分支名：experiment/va-asymmetry-composite
创建日期：2026-07-09
父分支（开分支时）：dev/0.5 @ 57929794929a53c52d7450a11479240cb8f2f355
当前状态：立题文档完成 · Stage 0 复现已通过（直接复用 archive 基准脚本，未新写主题 pipeline 代码）
实现提交 hash：（Run-2 新主题 pipeline 落地后回填）
```

---

## 6. 并行支线（与本主线 experiment-plan 解耦）

| 支线 | 状态 | 独立 workbench |
|------|------|---------------|
| Reaccept 对称子环境探索 | Gatekeeper 统计层 PASS · 机制/落地层 REJECT · 待收窄分组扫描决策 | [va-asymmetry-composite-reaccept-symmetric-regime.md](va-asymmetry-composite-reaccept-symmetric-regime.md) ⭐ |

**边界说明**：该支线不改变主线 [experiment-plan.md](../research/themes/va-asymmetry-composite/experiment-plan.md) 五阶段推进顺序，仅在支线 Step 2 决策后可能追加 rank20 gate 到主线 Stage 1 C.2 候选或 Stage 2 参数平台 L3 可选特征。

---

*本文件是主线实验流水（对齐 experiment-plan 五阶段），支线内容剥离到独立 workbench；阶段稳定后压缩结论写入主题目录，完整实验包归档到 `docs/research/archived-notes/`。*
