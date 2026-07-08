# va-asymmetry-composite · Stage 0 立题复现（Workbench）

> 类型：Workbench / 实验流水
> 状态：**待启动**（立题完成 · 开发分支已开）
> 开发分支：`experiment/va-asymmetry-composite`
> 开分支 hash：`57929794929a53c52d7450a11479240cb8f2f355`（2026-07-09，父分支 `dev/0.5`）
> 目标 dev 分支：`dev/0.5`
> 主题 README：[va-asymmetry-composite](../research/themes/va-asymmetry-composite/README.md)
> 阶段计划：[experiment-plan.md](../research/themes/va-asymmetry-composite/experiment-plan.md)
> 立题起点归档：[2026-07-09-poc-va-shaping](../archive/strategy-research/2026-07-09-poc-va-shaping/README.md)

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
2. 塑形基准参数冻结：SL=1.0 / TP=1.4 / TH=8h（L2 级参数）
   阶段 2 起可在 ±30% 范围内扫描，但基准不变
3. 成本模型冻结：c_realistic 固定滑点 + 手续费口径（L2 级）· 不做更宽松的成本假设
4. L_seg2_low_flat 淘汰：该 tier 在 archive 塑形扫描中无稳定收益，组合关不纳入
5. 名义暴露必须压缩：结果需同时报告 100%/200%/400% 三档，禁止用无约束杠杆美化夏普
6. 顺序禁止反转：先 Stage 0 复现，再 Stage 1 候选，再 Stage 2 组合搜索；
   未通过前一关不得进入下一关
```

## 4. 下一步操作清单（待启动）

- [ ] 从 `archive:2026-07-09-poc-va-shaping/raw-scripts/` 提取 Stage 3 基准脚本
- [ ] 确认分类器 v4.0 合同：tier 判定表 + 14 条严格性约束，与主题 parameter-selection-spec 交叉验
- [ ] 在新主题 pipeline 中重跑：相同品种集合 / 相同交易时间窗 / 相同持仓期
- [ ] 比对关键指标：事件总数 / 各 tier 事件数排序 / 年化净收益（偏差 ≤5%）/ Sharpe（偏差 ≤5%）/ MaxDD（偏差 ≤5%）/ 胜率 / 盈亏比
- [ ] 若通过：在本文件追加复现结果表，然后写入 Stage 1 启动计划
- [ ] 若失败：在 [docs/issues/](../issues/) 登记 bug 号，暂停实验，回修后再跑

## 5. 开发分支信息

```text
分支名：experiment/va-asymmetry-composite
创建日期：2026-07-09
父分支（开分支时）：dev/0.5 @ 57929794929a53c52d7450a11479240cb8f2f355
当前状态：立题文档完成 · Stage 0 复现脚本待写入
实现提交 hash：（实现后回填）
```

---

## 6. 并行支线（与本主线 experiment-plan 解耦）

| 支线 | 状态 | 独立 workbench |
|------|------|---------------|
| Reaccept 对称子环境探索 | Gatekeeper 统计层 PASS · 机制/落地层 REJECT · 待收窄分组扫描决策 | [va-asymmetry-composite-reaccept-symmetric-regime.md](va-asymmetry-composite-reaccept-symmetric-regime.md) ⭐ |

**边界说明**：该支线不改变主线 [experiment-plan.md](../research/themes/va-asymmetry-composite/experiment-plan.md) 五阶段推进顺序，仅在支线 Step 2 决策后可能追加 rank20 gate 到主线 Stage 1 C.2 候选或 Stage 2 参数平台 L3 可选特征。

---

*本文件是主线实验流水（对齐 experiment-plan 五阶段），支线内容剥离到独立 workbench；阶段稳定后压缩结论写入主题目录，完整实验包归档到 `docs/archive/strategy-research/`。*
