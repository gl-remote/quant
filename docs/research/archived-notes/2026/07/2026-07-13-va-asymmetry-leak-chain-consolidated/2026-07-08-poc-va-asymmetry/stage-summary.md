# 阶段 4 · 摘要（poc-value-area-asymmetry）

> archive:2026-07-08-poc-va-asymmetry · stage-summary

## 一句话结论

**分类器 v4.0 冻结 · 6 类合并版 · 9 A + 6 A- · 多空双向覆盖 · 主题主动性研究暂停 · 分类器组件保留供下游策略引用。**

## 数据

- 143 合约 · 36625 events · 20 品种前缀
- 2023-09 → 2026-06
- 每 tier 独立 date-cluster bootstrap 5000 · 反事实 5000

## 方法论闭环

**Step 2 · 描述性扫描**：144 tier × 3 period = 432 组统计 · 99 个 (tier,period) 组合通过 `n≥15 ∧ indep≥5 ∧ mean>0` 门槛

**Step 3 · 严格验证（v9.1 FDR 校正）**：
- 硬门槛：L1（样本量）· L2（CI 排 0）· L3（FDR ≤ 5%）· L4（反事实 p<0.001）
- 观察指标：L5（品种保留）· L6（IR）· L7（时稳 ≤ 0.50）
- 评级：A 级（硬门槛 + L7）· A- 级（硬门槛 · L7 警示）
- 结果：144 tier 版 · 11 A + 9 A- · 79 fail

**Step 3.5 · 合并降级验证**（关键收获）：
- 观察：144 tier 稀疏率 91% · 大量强信号被 CI 撑不开
- 合并：把通过区域合并为 **6 大类** · 保持互斥
- 结果：**通过率 20% → 83%** · Bonferroni family=6 · α=0.008 就能过

## v4.0 白名单（6 类合并版）

**多头 3 类**（trend ≥ 0.75）：

| Tier ID | full | stable | trans | 说明 |
|:---:|:---:|:---:|:---:|:---|
| L_seg3_lowmid_up | A- +30.5 | **A** +31.2 | A- +29.9 | 段2/3 低中ATR · KF-23 甜蜜点 |
| L_seg12_high_up  | A- +45.5 | fail    | **A** +57.7 | 段1/2 高ATR · 恐慌反弹 |
| L_seg2_low_flat  | **A** +18.3 | fail  | A- +37.3 | 段2 低ATR 平稳 · v9 新维度 |

**空头 3 类**（trend ≤ 0.20 除 L_seg2_low_flat 外）：

| Tier ID | full | stable | trans | 说明 |
|:---:|:---:|:---:|:---:|:---|
| **S_seg12_high_dn** | **A** +31.4 | **A** +26.8 | **A** +37.1 | ⭐ 三 period 全 A |
| S_seg34_high_dn | **A** +37.1 | A- +25.3 | A- +50.8 | 崩盘前奏扩展 |
| S_seg2_mid_dn   | **A** +23.2 | fail    | **A** +24.5 | 非高 ATR 唯一空头 |

## KF-25 ~ KF-29（本批次定型）

- **KF-25 · FDR 优于 Bonferroni 用于结构性切片族** · 跨主题方法论
- **KF-26 · 平稳期 alpha 仅存在于转换期**
- **KF-27 · 交叉 trend 全部证伪 · 顺 trend 是硬规则**
- **KF-28 · 转换期是空头最密集区**
- **KF-29 · 合并降级优于精细切分** · 跨主题方法论

（详见 theme:poc-value-area-asymmetry#research-status）

## 与前置批次的关系

- 继承 KF-22（date-cluster bootstrap · per-contract rank）
- 继承阶段 3 KF-Q（空头必须高 ATR）· 现在 144 tier 有完整证据
- 阶段 3 KF-23（分位 × ATR 制度信号地图）· 阶段 4 是其三维深化

## 下游可立主题

1. **poc-va-shaping-composite** — 分类器 + 结构塑形组合策略
2. **poc-va-symbol-refinement** — 按品种类型分组参数（KF-24 遗留）
3. **poc-va-tail-asymmetry** — VA 外 tail 独立信息假设（KF-01 遗留）
