# value-area · 已冻结主题家族

> 类型：Frozen Theme Family
> 家族状态：全部冻结（value_area_reacceptance 于 2026-07-03 feature-only 降级 · value_area_rolling_reacceptance 于 2026-07-05 假设完全证伪）
> 冻结完成时间：2026-07-05
> 上游 Roadmap：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)

本家族聚合以 **Volume Profile · Value Area · POC** 为核心概念的策略主题。
两个成员前后置继承、共享核心假设、共用方法论。所有独立可交易假设均已被
证伪；保留的价值主要是方法论、feature 语义与技术设施副本。

## 成员

| 成员 | 冻结日期 | 冻结原因 | 目录 | 归档 |
|------|---------|---------|------|------|
| **value-area-reacceptance** | 2026-07-03 | Stage B v2 双 Q 判据未同时达标：Q_return 通过（C3 @ n=144 ret_mean +1.10）但 Q_generalize 未通过（Group_M 5/8 无 trade）→ **feature-only 降级 + 主策略暂停** | [value-area-reacceptance/](value-area-reacceptance/README.md) | [2026/07/2026-07-03-value-area-reacceptance-stage-b/](../../../archive/strategy-research/2026/07/2026-07-03-value-area-reacceptance-stage-b/README.md) |
| **value-area-rolling-reacceptance** | 2026-07-05 | 前主题的 rolling 版本 pivot。Stage 1 / 1.5 / 4 / 4b 完整链条证伪：POC 特殊性 / rolling 独立价值 / reacceptance 触发器特殊性 / 4+ ATR 距离档 edge 全部被独立证伪 → **主题假设完全崩塌** | [value-area-rolling-reacceptance/](value-area-rolling-reacceptance/README.md) | [2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/](../../../archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md) |

## 关系图

```text
value-area-reacceptance                     # discrete + 定时刷新 POC/VA
  │ 前置主题
  │ 失败根因：
  │   - Stage B v2 事件驱动 AttemptEvent 下双 Q 未达标；
  │   - Group_M 泛化能力不足；
  │   - spec §5.2 X_s 极值化导致 C2 恒不触发；
  │
  ├──> value-area-rolling-reacceptance      # rolling POC/VA (2026-07-03 立题)
       # 假设：换 rolling window 追踪 POC 跳变，可修复前主题失败机制
       # 结果：假设链完全崩塌（2026-07-05 冻结）
       #   - POC 特殊性证伪 → rolling 追踪的对象不特殊
       #   - reacceptance 触发器特殊性证伪 → 触发器不比 no_trigger baseline 好
       #   - 4+ ATR 距离档 baseline ≈ 0 → 距离档不是 edge
```

## 共同教训（方法论层）

以下教训适用于**任何以 Volume Profile / VA / POC 为核心概念的后续主题**：

1. **POC 不是唯一/特殊的均值锚**
   前日 fixed POC 与 rolling POC 均被证伪相对 PrevClose / PriceMedian 无
   独立引力（Stage 1.5-A5 / Stage 4 显著性检验）。后续若还想用 POC，必须
   证明其相对至少两个基线锚（fixed POC + 简单均值锚）的独立价值。

2. **距离档过滤本身不是 edge**
   4+ ATR 距离档在 no_trigger baseline 上期望 ≈ 0（Stage 4b）。距离档只是
   R:R 结构塑形，不提供方向 alpha。

3. **触发器需要 no_trigger baseline 对照**
   Stage 4b 用 6 种触发器 × no_trigger baseline 证明：reacceptance /
   long_body_reject / volume_spike / breakout_reversal 都不显著优于 no_trigger。
   后续任何 mean-reversion 触发器都必须过 no_trigger baseline 关。

4. **未配对差异易产生假象**
   Stage 4 未配对时看到 rolling POC 相对 fixed POC +0.184 → 配对后 -0.137
   反向。凡是多锚点/多触发器对比，必须在**同一批事件**上配对评估。

5. **Cluster bootstrap 揭示事件非独立性**
   同一合约内的 reacceptance 事件高度相关。cluster CI 通常显著宽于 iid CI，
   决定"显著"的门槛应基于 cluster CI 而非 t-test。

6. **距离/大小/时间统一用 ATR 归一化**
   Stage 1.5-A 的 ATR 版本让距离-到达率函数跨板块完全重合；tick 单位版本
   看到的"板块分化"实为波动率异质性伪影。

7. **跨周期验证是稳健性硬门槛**
   Stage 4b 5m/15m 双周期一致证伪主题假设。任何"5m 上显著"的结论都应用
   15m 复现，否则可能是采样时钟带来的偶然性。

## 保留资产（供后续主题引用）

### 7.1 Feature 语义（来自 value-area-reacceptance）

- **C3 特征**：次次尝试且未触碰 POC，n_profile=12h 档在 Group_P 上
  ret_mean +1.10。可作为 feature 交给下游策略。定义与语义见
  [value-area-reacceptance/strategy-math-spec.md](value-area-reacceptance/strategy-math-spec.md)。

**注意**：C3 在 Group_M 上 concentration risk 高（m2501 单样本主导 87%
贡献），若引用需重新验证目标品种。

### 7.2 技术设施（副本在 archive）

以下代码资产已在归档时随主题 archive 保存副本，位置见各主题 archive 目录
的 `raw-scripts/` 或 `raw-strategies/`。**后续主题若复用，应拷贝到新主题的
scripts 目录并适配，不要直接从 archive 引用运行**。

- Volume profile 计算（fixed / rolling window）
- Reacceptance 事件检测
- 6 种触发器检测（reacceptance / no_trigger / long_body_reject / volume_spike / random_time / breakout_reversal）
- 多结构 S1-S6 交易模拟（fixed stop / partial exit / trailing / tiered stop / mid-target / time decay）
- Bootstrap 双检验（iid + cluster-by-contract）

### 7.3 反例经验

- POC 不特殊 / reacceptance 不特殊 / 距离档不是 edge → 提示"以 VA/POC 为
  中心的独立策略"这条路径本身可能是死胡同；后续应转向其他 alpha 来源，
  或把 VA/POC 作为**上下文特征**而非**独立 alpha 源**。

## 后续主题引用规则

- **可以**：引用本家族 README 与主题 README 顶部的冻结摘要作为背景。
- **可以**：拷贝技术设施代码到新主题（archive 副本视为公共基础设施）。
- **可以**：把 value-area-reacceptance 的 C3 作为 feature 集成到新主题。
- **不建议**：在新主题里再验证"POC 特殊性 / rolling POC 独立价值 /
  reacceptance 触发器特殊性 / 4+ ATR mean-reversion edge" —— 这些已在 20 品种
  × 5m+15m 上被证伪，重跑无意义。若要挑战这些结论，需先说明为什么本家族
  证据链不适用（例如换到日线 / 换到 tick 数据 / 换到期权隐波）。

## 冻结日期

**2026-07-05**（家族聚合完成）
