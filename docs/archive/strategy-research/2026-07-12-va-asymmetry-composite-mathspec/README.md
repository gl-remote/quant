# va-asymmetry-composite · Math Spec 分支归档

- **类型**：Archive / 策略实验摘要
- **状态**：已完成
- **开发分支**：`experiment/va-asymmetry-composite-mathspec`
- **实现提交**：`cdf4f488`
- **目标 dev**：`dev/0.5`
- **日期**：2026-07-12

## 内容

| 文件 | 说明 |
|------|------|
| `p0-p9-summary.md` | P0~P9 全 Phase 实验结论汇总 |
| `p0-p9-fixed-rerun.md` | 前视修复后 fixed 基线重跑结果 |
| `p2-timing-holding-time.md` | P2 entry_mode 全族证伪 + 持仓时长诊断详报 |

## 关键结论

- B0（Cap=4.0）：夏普 3.73 / OOS 2.51 / 年化 77% / MaxDD −9.15%
- 前视修复（ATR/trend shift(1)）使夏普从 7.36→3.73，信号真实
- 全链路 P0~P9 仅 Cap=4.0 被采纳，其余轴保持 B0
- spec §2.2 止损 ATR 口径对齐代码（日线 SMA）
