# va-asymmetry-composite · Research Status

> 类型：Research Status
> 状态：**阶段 0 · 立题（2026-07-09）** · 尚未启动实验
> 最近更新：2026-07-09
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md) v0.1

## 一句话结论

**主题已立题，尚未启动实验。目标：把 poc-value-area-asymmetry 分类器（方向 alpha）
+ structural-shaping-alpha 工具（塑形/成本/归因）+ archive:2026-07-09-poc-va-shaping
塑形参数，经品种筛选 / 信号强度加权 / 多空权重优化三道组合关，压缩到 100% 名义
暴露约束下，构建夏普 ≥ 2.5、年化净收益 ≥ 18%、可实盘的完整交易策略。**

## 边界（立题时锁定，不变）

1. **分类器契约不变**：严格继承 poc-value-area-asymmetry v4.0 的 6 类互斥定义（L_seg3_lowmid_up / L_seg12_high_up / L_seg2_low_flat / S_seg12_high_dn / S_seg34_high_dn / S_seg2_mid_dn + 未分类），不修改分类器内部逻辑
2. **L_seg2_low_flat 默认淘汰**（archive:2026-07-09-poc-va-shaping 已证塑形后 IR < 0），阶段 1 末尾仅补做「C 类农产品 × L_seg2_low_flat」专项验证决定是否豁免
3. **塑形参数基线不变**（多头 SL 1.0 ATR · 6~10h / 空头 SL 2.0~2.5 ATR · 8~10h / Trailing 不触发），只在阶段 2 末尾做「±30% 平台测试」，不做 grid search
4. **止损 2% + 名义 100% 是硬约束**（非可优化项），风控口径与 archive:2026-07-09-poc-va-shaping §风控 v2 一致
5. **成本口径锁定 realistic-cost**，扁平模式仅用于 debug（命名为 `--flat-cost-debug`）
6. **三大组合方向（C.1/C.2/C.3）是本主题唯一可搜索的自由度**，搜索空间按 README §4 / experiment-plan.md §1 严格限定（防组合爆炸）

## 下一步（启动顺序）

### 立即启动 · 阶段 0 · 立题复现

目标：复现 archive:2026-07-09-poc-va-shaping 的起点口径，确认 baseline。

**Step 0.1 · 数据资产确认**（立题即可做）
- 上游：`project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet`（archive:2026-07-09-poc-va-shaping §上游数据登记）
- 辅助：`workspace/common/contract_specs.py`（realistic-cost 查表）· `workspace/common/symbol_utils.py`
- 市场：`project_data/market_data/csv/*.tqsdk.5m.csv`

**Step 0.2 · Baseline 复现脚本**（docs/workbench/va-asymmetry-composite-stage0-baseline.md）
- 5 档保留（L_seg2_low_flat 剔除）
- 塑形参数：多头 SL 1.0 ATR + 8h · 空头 SL 2.5 ATR + 10h（取 archive 最优区间中点）
- 风控：单笔 SL ≤ 2% 权益 · 总名义 ≤ 100% 权益（先进先出压仓）
- 成本：realistic-cost

**Step 0.3 · Gatekeeper 判据（阶段 0 通过条件）**
- ✅ 年化净收益 ≥ 12%
- ✅ 夏普 ≥ 1.8
- ✅ MaxDD ≤ 10%
- ✅ 与 archive 口径差异 < 15%（允许小偏差，因分类器 v4.0 与 archive 可能有 minor 版本差）

### 阶段 0 通过后 · 阶段 1 · 三大方向 Gatekeeper 扫描

详见 experiment-plan.md §1。每个方向只跑 2~3 候选，独立增量 ≥ 0.2 夏普才保留。

### 阶段 1 通过后 · 阶段 2+

详见 experiment-plan.md §2-4。

## 关键发现清单（KF）

立题阶段暂无 KF。首次 KF 应在阶段 0 完成后登记。

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-09 | 初版立题 · README 三模块蓝图 + 五阶段路径；阶段 0~4 边界锁定；6 类分类器 + 三大组合方向文档化 |

## 立题日期

**2026-07-09**
