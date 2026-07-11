# va-asymmetry-composite · Research Status

> 类型：Research Status
> 状态：**阶段 1 降级 · B0 即最优 · 待工程化（2026-07-09）**
> 最近更新：2026-07-09
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md) v0.1

## 一句话结论

**组合层三大方向（品种筛选/强度加权/多空权重）0/6 通过，B0=S1×W0×VW0 即最优。
B0 年化 15.10%、Sharpe 2.70、MaxDD −2.40%。年化未达 18% 目标但夏普/回撤均超预期。
建议直接工程化（路径 A）或提高名义上限至 120%（路径 B）。**

## 边界（立题时锁定，不变）

1. **分类器契约不变**：严格继承 poc-value-area-asymmetry v4.0 的 6 类互斥定义
2. **L_seg2_low_flat 默认淘汰**（archive:2026-07-09-poc-va-shaping 已证塑形后 IR < 0）
3. **塑形参数基线不变**（多头 SL 1.0 ATR + 8h / 空头 SL 2.5 ATR + 10h）
4. **止损 2% + 名义 100% 是硬约束**
5. **成本口径锁定 realistic-cost**
6. **B0 = S1 × W0 × VW0 已锁定为最优组合方案**

## 下一步

1. **路径 A（推荐）**：直接工程化 B0，跳过阶段 2-3 进入阶段 4 模拟盘
2. **路径 B**：提高名义上限至 120% 观察年化是否逼近 18% 且 MaxDD 可控
3. 两者均需用户拍板

## 关键发现清单（KF）

### KF-1 · 组合层无增量 alpha
- 类型：策略行为
- 状态：已证实
- 证据：archive:2026-07-09-poc-va-shaping#va-asymmetry-composite-stage1-gatekeepers
- 影响：B0=S1×W0×VW0 锁定为最优组合方案，阶段 2-3 跳过
- 日期：2026-07-09

### KF-2 · W1 rank-距离加权无区分度
- 类型：策略行为
- 状态：已证实
- 证据：archive:2026-07-09-poc-va-shaping#va-asymmetry-composite-stage1-gatekeepers
- 影响：strategy-math-spec §5.1 W1 修正后 ΔSh=+0.00，强度信号与收益无关
- 日期：2026-07-09

### KF-3 · math-spec 存在 9 处规格问题
- 类型：方法论
- 状态：已修正
- 证据：strategy-math-spec.md（本轮静态一致性检查）
- 影响：W1 方向性歧义直接导致实现错误；§5.3 仓位公式漏 ATR 转换；ATR 窗口 20d vs 实际 10d
- 日期：2026-07-09

### KF-4 · 品种筛选（S2）反向拖累
- 类型：策略行为
- 状态：已证伪
- 证据：archive:2026-07-09-poc-va-shaping#va-asymmetry-composite-stage1-gatekeepers
- 影响：按品种类型筛选 tier 反而剔除盈利组合（ΔSh −0.27），全品种 5 档更优
- 日期：2026-07-09

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-09 | 阶段 1 降级 · B0 锁定 · KF-1~4 登记 · 下一步选项 A/B |
| 2026-07-09 | 初版立题 · README 三模块蓝图 + 五阶段路径 |

## 立题日期

**2026-07-09**
