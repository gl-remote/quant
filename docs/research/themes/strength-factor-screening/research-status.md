# strength-factor-screening · 研究现状

> 类型：Research / 主题现状
> 状态：**Wave 1 + Wave 2 完成 · 6 候选全 L4 · 转 Wave 3（event-driven）或考虑冻结**（2026-07-16）
> 最近更新：2026-07-16

## 1. 一句话结论

```text
Wave 1 (F11/F5/F1/F3) + Wave 2 (F7/F7-alt) 共 6 候选在玉米 1h 上全部归 L4。

统一现象：所有基于过去价量统计的因子（无论单品种时序、板块横截面、方向一致
性、还是横截面平均强度）Gate 3 秩相关 r 都在 [-0.12, 0.06] 之间，平均 -0.05。

关键洞察：过去 20h 数据的任何统计量都与未来 20h |ν|/σ 独立——这与 GBM/Markov
模型的核心假设一致。未来的漂移强度可能无法用过去的价量数据推断。

Wave 3 转向 event-driven 因果外源（政策 / 库存 / OPEC）· 若也失败可能需要冻结主题。
```

## 2. 边界

```text
1. 本主题只研究"强度识别因子"，不研究方向因子；

2. 因子筛选的判据以上游 kf:structural-shaping-alpha#KF-27 给出的
   se ≤ se_target（玉米 1h ≈ 0.05）为核心 KPI，不用传统 IC / IR；

3. 塑形容器 (K_S, K_T, τ) 由上游参数优化器反解，本主题不重新定义塑形规则；

4. 任何识别器候选先过截断法泄漏检验（延续 va-asymmetry 家族教训）。
```

## 3. 下一步

```text
Wave 3 候选方向:

高优先（决定性实验）:
- F9 · 事件触发（政策 / 库存 / OPEC / 宏观数据发布 · 因果外源信号）
  · 若也失败 · 主题基本假设"|ν|/σ 可识别"可能不成立 · 需考虑冻结

低优先（工程成本高）:
- F12 · 实时新闻情感 · 需要外部数据源
- 变体 Wave 2：不同板块（黑色 rb+i · 需补数据）· 不同窗口 W ∈ {10, 40}

明确不再走的方向（KF-B1..B6 已封）:
- 内生价量统计（无论时序还是横截面）
- 窗口回归型识别器
- Hurst 长程记忆型识别器
- ATR / RV 变化率型识别器
- 板块横截面统计（方向一致或平均强度）
```

## 4. 关键发现清单

### KF-B1 · 波动率变化率类因子与未来漂移强度独立

- 类型：方法论
- 状态：已证实
- 证据：workbench:strength-factor-screening/candidate-f1-atr-turning-20-60
  + workbench:strength-factor-screening/candidate-f3-realized-vol-breakout-20-60
- 影响：F1（Gate 3 r=-0.067）与 F3（r=-0.003）两条独立证据链证明 ATR / RV 变化率
  与未来 20h $|\nu|/\sigma$ 无预测关系 · Wave 2+ 融合时不作为强度权重 · 只作覆盖率保护条件
- 日期：2026-07-16

### KF-B2 · 长程记忆（Hurst）与短期漂移强度独立

- 类型：方法论
- 状态：已证实
- 证据：workbench:strength-factor-screening/candidate-f5-hurst-60
- 影响：F5 Gate 3 r=0.061 · Hurst 描述过去时间序列结构 · 与未来漂移强度无直接映射 ·
  下游融合时若含 Hurst 必须搭配其他有预测力的信号
- 日期：2026-07-16

### KF-B3 · 窗口回归 se 上限证伪（实测验证）

- 类型：方法论 + 假设证伪
- 状态：已证实
- 证据：workbench:strength-factor-screening/candidate-f11-window-regression-20h
- 影响：F11 实测 se_hat=0.2394 · 与理论预测 $1/\sqrt{20}$=0.224 相差 6.9%
  · 完全对齐 shaping-theory §2.23.5.5 · 未来禁用直接窗口回归型识别器
- 日期：2026-07-16

### KF-B4 · Gate 1.5 与 Gate 3 正交 · 分布对齐 ≠ 逐点预测

- 类型：方法论
- 状态：已证实
- 证据：workbench:strength-factor-screening/candidate-f11-window-regression-20h
- 影响：F11 Gate 1.5 完美通过（C1-C4 全过）但 Gate 3 r=-0.082
  · 证明 Gate 1.5 与 Gate 3 是正交检验 · 双 gate 都必要
  · 补齐 screening-methodology §四 Step 4.5 的实证支持
- 日期：2026-07-16

### KF-B5 · Wave 1 候选选型集体反例 · 方向调整

- 类型：策略行为 + 方向调整
- 状态：已证实
- 证据：workbench:strength-factor-screening/rejected_factors
- 影响：Wave 1 全部 L4 · 主题方向从"波动率 / 长程记忆"转向"event-driven / 横截面共振"·
  更新 experiment-plan.md 的候选矩阵 Wave 2 优先级
- 日期：2026-07-16

### KF-B6 · 过去价量统计与未来 |ν|/σ 独立（跨 6 因子一致）

- 类型：方法论 + 假设边界
- 状态：已证实
- 证据：workbench:strength-factor-screening/rejected_factors（Wave 1 + Wave 2 六因子汇总表）
- 影响：F11/F5/F1/F3/F7/F7-alt 六个跨类型因子的 Gate 3 秩相关 r ∈ [-0.117, 0.061]，
  平均 -0.05 · 5/6 为负或零 · 且各因子彼此独立（时序 / 长程记忆 / 波动率 / 横截面）·
  统一验证"未来 |ν|/σ 无法从过去价量推断" · 与 GBM/Markov 核心假设一致 ·
  下游 Wave 3 必须转向因果外源（event）· 若 event 也失败可能需要冻结主题
- 日期：2026-07-16

### KF-B7 · 弱均值回归的边际证据（不足以使用）

- 类型：策略行为（观察）
- 状态：边界待定
- 证据：workbench:strength-factor-screening/candidate-f7-cross-sectional（Wave 2 补充观察表）
- 影响：6 候选 r 平均 -0.05 · 方向一致（5/6 为负 或 零）· 提示"过去强漂移 → 未来略弱漂移"·
  但 |r| 太小（远低于 Gate 3 的 0.40）· 不足以逆向使用 · 只作观察登记
- 日期：2026-07-16

## 5. 数据管道说明

Wave 1 使用玉米 3 合约 1h（c2601 / c2603 / c2605 · 共 1252 bar · 评估集 1012-1192 点）·
KF-27 反解结果：$(K_S^\ast, K_T^\ast, \tau^\ast) = (2.5, 10.0, 0.6)$ · $se_{\text{target}} = 0.0489$。

共享工具：workbench:strength-factor-screening/scripts/_driver.py
