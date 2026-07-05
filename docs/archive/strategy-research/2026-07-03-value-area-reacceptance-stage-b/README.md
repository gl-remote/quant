# 2026-07-03 · value-area-reacceptance Stage B 归档

> 类型：Archive / 策略实验摘要
> 状态：已完成 / 未通过（feature-only 降级）
> 归档时间：2026-07-03
> 主题入口：[../../../research/themes-frozen/value-area/value-area-reacceptance/](../../../research/themes-frozen/value-area/value-area-reacceptance/README.md)
> 后继主题：[../../../research/themes-frozen/value-area/value-area-rolling-reacceptance/](../../../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md)
> 开发分支：`experiment/value-area-multi-attempt-poc-reversion`

## 内容

- [stage-b-sweep-summary.md](stage-b-sweep-summary.md) — Stage B v2 + v3
  完整结果矩阵，双 Q 判据评估，v1 → v2 → v3 语义演进对比
- [raw-workbench/stage_b_sweep.py](raw-workbench/stage_b_sweep.py) — 一次性
  driver 脚本，225 runs (15 symbols × 3 n_profile × 5 pattern set) 的
  in-process sweep 实现

## 阅读顺序

1. 先读 [主题 README §1](../../../research/themes-frozen/value-area/value-area-reacceptance/README.md)
   看整体冻结决策（3 层证据）
2. 再读 [stage-b-sweep-summary.md](stage-b-sweep-summary.md) 看 Stage B
   完整数据表与语义演进
3. 需要复现某次 sweep 时读 `raw-workbench/stage_b_sweep.py`

## 关键结论

- **Q_return（Group_P 均值提升）**：C3 @ n_profile=144 达标（ret_mean +1.10）
- **Q_generalize（Group_M ≥5/8 profitable）**：**不达标**（5/8 无 trade，
  m2501 单样本独占 87% 贡献）
- **C2 语义**：v2（X_s := max）下恒不触发，v3（X_s := 最近一次 breakout）
  修复后 76-98 trades 但整体不改善泛化
- **决策**：feature-only 降级；C3 独立信号可提取；主策略暂停
- **后继**：rolling 版本重构（见后继主题）

## 关联

- [前主题 research-status](../../../research/themes-frozen/value-area/value-area-reacceptance/research-status.md)
- [前主题 strategy-math-spec](../../../research/themes-frozen/value-area/value-area-reacceptance/strategy-math-spec.md)
