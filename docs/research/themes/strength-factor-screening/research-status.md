# strength-factor-screening · 研究现状

> 类型：Research / 主题现状
> 状态：**Wave 1 完成 · 全部 L4 · 转 Wave 2**（2026-07-16）
> 最近更新：2026-07-16

## 1. 一句话结论

```text
Wave 1 四候选（F11 窗口回归 / F5 Hurst / F1 ATR 拐点 / F3 RV 突破）在玉米 1h
上全部归 L4 · 无一通过 Gate 1。

关键洞察：波动率制度类因子（F1/F3）与长程记忆因子（F5）都与未来 |ν|/σ 无预测
关系——它们描述"过去"或"当下的波动率结构"，不描述"未来漂移"。

Wave 2 应转向 event-driven 与横截面共振信号。
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
Wave 2 候选方向（KF-B1..B3 已剔除的方向不再重试）:

优先候选:
- F7 · 横截面共振（同板块 ≥3 品种同向 · 需要板块内多品种数据）
- F9 · 事件触发（宏观数据发布 / 库存报告 / 政策 · 需要 event 时序）

低优先:
- F6 · 结构突破 + 量价背离（POC / VA breakout）· 但需注意 KF-B4 教训
- Wave 3 · 融合层（若 Wave 2 单因子仍 L4）

明确不再走的方向（KF-B1/B2/B3 已封）:
- 窗口回归型识别器
- Hurst 长程记忆型识别器
- ATR / RV 变化率型识别器（可作为 Gate 2 覆盖率保护而非强度权重）
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

## 5. 数据管道说明

Wave 1 使用玉米 3 合约 1h（c2601 / c2603 / c2605 · 共 1252 bar · 评估集 1012-1192 点）·
KF-27 反解结果：$(K_S^\ast, K_T^\ast, \tau^\ast) = (2.5, 10.0, 0.6)$ · $se_{\text{target}} = 0.0489$。

共享工具：workbench:strength-factor-screening/scripts/_driver.py
