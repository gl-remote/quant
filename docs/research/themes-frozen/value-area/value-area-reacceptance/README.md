# value_area_reacceptance 主题

> 类型：Theme / 目录索引
> 状态：已冻结 / 主策略退役 / 后继主题 = value-area-rolling-reacceptance
> 最近更新：2026-07-03

VA reacceptance 主题的所有历史工件（数学规格、Stage A/B 实验计划、参数
选择、工程实现细节）保留在本目录内，作为后继主题的对照参考。**本主题
不再新增实验、不再修改主 spec**。策略代码 `value_area_multi_attempt_
poc_reversion_strategy.py` 保留可运行，仅作为 baseline / 对照使用。

## 1. 主题为什么冻结（决策依据）

三个层次的理由：

### 1.1 直接证据：Stage B v2 / v3 双 Q 判据未通过

- **Q_return**（Group_P 均值提升）：C3 @ n_profile=144 达标（ret_mean
  +1.10），但 v3（修完 C2 极值化定义）后 Group_P 大部分 cell 变差；
- **Q_generalize**（Group_M ≥ 5/8 profitable）：**全部 v2/v3 版本均
  不达标**——Group_M 上 5/8 合约无 trade，或独占样本贡献（m2501 一根
  独苗），无法泛化；
- 结论：按 experiment-plan §7.1 判据，走 feature-only 降级路径，主策略
  暂停作为独立开仓策略。

详见 [research-status.md](research-status.md) §1、[Stage B 归档](../../../../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/README.md)。

### 1.2 结构证据：C1/C2/C3 语义对，但实现语义错

C1（首次 reacceptance）/ C2（突破衰减）/ C3（未触 POC 的次次尝试）都是
布林带 rolling 突破再接受语义下的经典 pattern，语义本身没有问题。**但
本主题采用的"离散刷新 POC/VA + 跨 bar 累积 attempt state"实现语义**
带来了三大结构问题：

1. **需要 §11.3.5 Replay 反事实计算**，为解释"用新锚在过去 n_step 根
   bar 上假装重新发生 attempt"专门写了一节 spec 例外；
2. **策略核心持有大量跨 bar 状态**（`SideState`、`BreakoutTrack`、
   `T_prev_event`、`va_r30_anchors`），无法把 POC/VA 提炼为 indicator；
3. **C2 语义"最近一次 vs 上一次"与"当前锚 vs 上一次锚"两个坐标系纠缠**，
   spec 需要显式声明反事实计算规则，我们上周花了 3 版才修好 X_s 极值化。

### 1.3 理论证据：discrete 定时刷新不匹配 POC 的 jump-process 本质

POC / VA 是**订单流堆积释放**的产物，微观结构文献（Kyle 1985 / Glosten-
Milgrom 1985 / Hamilton 1989 regime switching）都指向 jump process 或
regime switching。**跳变时刻 τ 与 n_step 采样时钟不对齐**，导致 discrete
periodic refresh 平均有 `n_step/2` 长度的"陈旧锚窗口"——信号在这段时间
是错的。三种方案排名：

| 方案 | 对 jump process 的建模 | 工程成本 | 排名 |
|---|---|---|---|
| A. Discrete + change-point detector（CUSUM/BOCPD）| **理论最贴合** | 高 | 最好 |
| B. Rolling window（隐式追踪）| 隐式检测 | 低 | 次好 |
| **C. Discrete 定时刷新（本主题现状）** | 假设 τ 对齐采样时钟（错） | 中 | **最差** |

因此本主题采纳的建模路径（C）在 jump 假设下**是三个方案里最差的近似**。
完整论证见 [value-area-rolling-reacceptance §7](../value-area-rolling-reacceptance/README.md#7-理论依据为什么-rolling-反而更贴合-poc-是跳变量-的直觉)。

## 2. 冻结但保留代码的原因

尽管主题冻结，策略代码 `value_area_multi_attempt_poc_reversion_strategy`
不删，保留三个用途：

1. **对照 baseline**：后继 rolling 主题验证时可以复用本策略作为"离散
   实现"的横向对照，检验 rolling 是否真的更优；
2. **feature-only 出口**：C3 独立事件（无 POC 触碰的次次尝试）在
   n_profile=144 上有边际信息，可暴露为 feature，交给其他 rolling
   策略消费；
3. **历史可复现**：Stage A/B 归档结果依赖此实现，删除会使归档不可复现。

## 3. 后继主题

**value-area-rolling-reacceptance**：把 POC/VA 做成 rolling indicator，
用布林带语义重写 C1/C2/C3，消除本主题的所有结构性问题。

- 入口：[../value-area-rolling-reacceptance/README.md](../value-area-rolling-reacceptance/README.md)
- 理论论证：同 README §7（jump-process 假设下 rolling 是隐式 change-
  point detection，是理论次优 + 工程最简的帕累托最优点）

## 4. 文档地图

| 目的 | 文档 |
| --- | --- |
| 主题当前研究进度（先看这个） | [research-status.md](research-status.md) |
| 数学规格（策略契约，已冻结） | [strategy-math-spec.md](strategy-math-spec.md) |
| 实验计划（Stage A/B 归档参考） | [experiment-plan.md](experiment-plan.md) |
| 参数选择规格（未启用） | [parameter-selection-spec.md](parameter-selection-spec.md) |
| 工程实现细节 | [implementation-notes.md](implementation-notes.md) |

## 5. 阅读顺序

```text
README.md                     (本文，含冻结决策依据)
    ↓
research-status.md            主题结论 / 边界 / 未决问题 / 后继指向
    ↓
strategy-math-spec.md         已冻结的数学契约（作为对照基线）
    ↓
implementation-notes.md       实现层的工程细节（供 rolling 版本参考）
```

## 6. 与外部文档的关系

- 全局研究入口：[../../../strategy-current.md](../../../strategy-current.md)
- 长期框架：[../../../../roadmap/strategy-research-framework.md](../../../../roadmap/strategy-research-framework.md)
- Stage B v2/v3 归档：[../../../../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/](../../../../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/README.md)
- 后继主题：[../value-area-rolling-reacceptance/README.md](../value-area-rolling-reacceptance/README.md)
- 历史归档：见 [research-status.md §9 关联文档](research-status.md#9-关联文档)

## 7. 工作规则

- **本主题冻结后禁止**：修改 strategy-math-spec.md、新增 experiment-plan
  条目、扩展策略代码；如需修改，走后继主题；
- **允许**：修 typo / 补充历史注解 / 归档链接更新；
- Stage B 结果稳定后可从 `docs/workbench/` 归档到
  `docs/archive/strategy-research/`，同时更新
  [research-status.md](research-status.md) 的关联链接。
