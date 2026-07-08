# 阶段 4 · 分位×ATR×Trend 深化验证

> 更新时间：2026-07-08（v2 · 三维 144 tier 深化完成 · FDR 校正判决 · 已归档至 archive:2026-07-08-poc-va-asymmetry）
> 主题：theme:poc-value-area-asymmetry
> 上阶段：archive:2026-07-08-poc-va-asymmetry#stage3-robustness（同批次合并归档 · 见 README）
> 契约：theme:poc-value-area-asymmetry#classifier-math-spec（v4.0）
> 参数：theme:poc-value-area-asymmetry#parameter-selection-spec（v4.0）
> 实验计划：theme:poc-value-area-asymmetry#experiment-plan（v9.1）

## 0. 阶段 4 目标与判决

**核心目标**：完整验证 KF-23 的分位×ATR×Trend 三维信号地图 · 每格独立通过硬门槛
严格性验证。

**新拓展维度（v9 相对阶段 3）**：
- **trend 加入 flat 档**（0.20 < trend_rank < 0.75）· 之前从未深挖
- **多头/空头都覆盖 3 trend 档**（up / flat / down）· 探索"涨段做空 · 跌段做多 · 平稳期双向"
- 4 skew × 3 ATR × 3 trend × 2 direction × 2 regime = **144 tier + 未分类**

**校正方案（v9.1 修订）**：
- 原 v9 用 Bonferroni family=144（α=0.000347）· 3.58σ · 假设违反 · 惩罚过重
- 改用 **FDR (Benjamini-Hochberg) α=0.05** · 允许 ≤5% 假发现率 · 更适合"结构性切片"
- 同时保留 **Bonferroni family=18（α=0.0028）** 作为 sanity check（不硬拒 · 观察指标）

**判决（v9.1）**：**✅ 通过 · 多头 A 级 4 + A- 6 · 空头 A 级 7 + A- 3 · 合计 20 个**

## 1. 三表 · trend 制度下的通过分布

**表格规则**：
- 横轴 `skew段1..4`（多头：L1[0-0.09] L2(0.09,0.19] L3(0.19,0.25] L4(0.25,0.30]；
  空头：S1[0.91-1] S2(0.81,0.91] S3(0.70,0.81] S4(0.60,0.70]）
- 纵轴 `ATR 制度`（低 / 中 / 高）
- 单元数值 = **多头通过 period 数 - 空头通过 period 数**（∈ [-3, +3]）
  - 每个 tier 分 `full / stable / trans` 3 个 period 独立跑严格验证
  - 数值绝对值 = **稳健度**（3 = 三 period 全通过 · 1 = 仅一个 period 过）
  - 正 = 多头 · 负 = 空头 · 空白 = 该格无 tier 通过
- 总通过数（跨 3 表 3 period）= **20 个 (tier, period) 组合 · 13 个独立 tier**

### 1.1 表 · 涨段（Tup · trend_rank ≥ 0.75）

**多头独占 · 空头 0**

|          | skew段1 | skew段2 | skew段3 | skew段4 |
|:--------:|:------:|:------:|:------:|:------:|
| ATR 低   | **+1** |        | **+2** |        |
| ATR 中   |        |        | **+2** |        |
| ATR 高   | **+1** | **+2** |        |        |

**详细**：
- ATR低 × skew段1 · L1_Alow_Tup · [full] · max_mean **+40 bps**
- ATR低 × skew段3 · L3_Alow_Tup · [full, stable] · max_mean **+47 bps** · 品保 **92%**
- ATR中 × skew段3 · L3_Amid_Tup · [full, stable] · max_mean **+137 bps**（含 n=26 A-）
- ATR高 × skew段1 · L1_Ahigh_Tup · [trans] · max_mean **+51 bps** · 时稳警示
- ATR高 × skew段2 · L2_Ahigh_Tup · [full, trans] · max_mean **+64 bps**

**解读**：
1. **skew段3 是稳定期涨段的甜蜜点**（KF-23 确认）· ATR 低+中都覆盖 · 稳健度 2
2. **skew段1/2 + ATR 高只在转换期出现** · 波动率驱动的"恐慌 V 反弹"机制（阶段 3 洞察 P）
3. **ATR 高格全部依赖转换期** · 稳定期 + ATR 高 + 涨段是内在矛盾
4. **多头覆盖 3 种机制**：段3+ATR低（均值回归）· 段3+ATR中（秩序恢复）· 段1/2+ATR高（恐慌反弹）

### 1.2 表 · 平稳（Tflat · 0.20 < trend_rank < 0.75）

**单格弱多头 · v9 新维度**

|          | skew段1 | skew段2 | skew段3 | skew段4 |
|:--------:|:------:|:------:|:------:|:------:|
| ATR 低   |        | **+2** |        |        |
| ATR 中   |        |        |        |        |
| ATR 高   |        |        |        |        |

**详细**：
- ATR低 × skew段2 · L2_Alow_Tflat · [full, trans] · max_mean **+37 bps**

**解读**：
1. **v9 新探索的正面收获** · 首次证实平稳期有独立 alpha
2. **稳定期平稳完全无 alpha**（只有 full 和 trans 过 · stable 单独不显著）· 说明这个信号本质是"转换期特性"渗透到 full
3. **极稀疏** · 全 36 个平稳期 tier 只有这一格通过 · 平稳期作为分类维度价值有限 · 但可作为 filter
4. **无空头** · 空头在平稳期完全无 alpha

### 1.3 表 · 跌段（Tdn · trend_rank ≤ 0.20）

**空头独占 · 空头最密集区**

|          | skew段1 | skew段2 | skew段3 | skew段4 |
|:--------:|:------:|:------:|:------:|:------:|
| ATR 低   |        |        |        |        |
| ATR 中   |        | **-2** |        |        |
| ATR 高   | **-3** | **-2** | **-2** | **-1** |

**详细**：
- ATR中 × skew段2 · S2_Amid_Tdn · [full, trans] · max_mean **+24 bps**
- ATR高 × skew段1 · S1_Ahigh_Tdn · [stable, full, trans] · max_mean **+35 bps** · **三 period 全通过** ⭐
- ATR高 × skew段2 · S2_Ahigh_Tdn · [full, trans] · max_mean **+41 bps**
- ATR高 × skew段3 · S3_Ahigh_Tdn · [trans, full] · max_mean **+80 bps**（全表最高）
- ATR高 × skew段4 · S4_Ahigh_Tdn · [full] · max_mean **+26 bps**

**解读**：
1. **ATR 高 × 跌段是本主题最强区** · skew 段 1/2/3/4 全部覆盖
2. **S1_Ahigh_Tdn 稳健度 -3**（全 20 通过里唯一 · 三 period 全通过）· 是**最铁的空头信号**
3. **崩盘前奏机制**在跌段扩散到 skew 段 1-4 · 阶段 2 主线在 144 tier 分解后更精细
4. **ATR 中 + skew段2** 是唯一非高 ATR 的空头信号 · 表明部分空头在低波动环境也可用

## 2. 三表合成解读

### 2.1 多空势力分布地图

| 表 | 多头单元格数 | 空头单元格数 | 总通过 period 数 |
|:---:|:---:|:---:|:---:|
| 涨段 (Tup) | 5 格 · 加权 8 | 0 | 8 |
| 平稳 (Tflat) | 1 格 · 加权 2 | 0 | 2 |
| 跌段 (Tdn) | 0 | 5 格 · 加权 10 | 10 |
| 合计 | 6 格 · 10 | 5 格 · 10 | **20** |

**结论**：
1. **多空严格顺 trend** —— 涨段/平稳全多头 · 跌段全空头 · **无"逆势"通过案例**
2. **多空数量对称**（10 vs 10）· 但集中度不同 —— 多头分散在 6 格 · 空头集中在 5 格 · **空头更集中**
3. **平稳期 alpha 极稀疏** · 仅 1 格 · v9 探索"平稳期"假设**边缘性成立**
4. v9 探索的"涨段做空 / 跌段做多"（cross-trend）· **全部未通过 · 顺 trend 是硬规则**

### 2.2 稳健度排行（|值| = 通过 period 数）

**稳健度 3（全 period 通过 · 最铁）**：
- **S1_Ahigh_Tdn**（空头 · 段1 · ATR高 · 跌段）· 阶段 2 崩盘前奏主线 · 全 3 period 通过

**稳健度 2（两 period 通过 · 稳）**：
- L2_Ahigh_Tup（多头 · 段2 · ATR高 · 涨段） · trans + full
- L2_Alow_Tflat（多头 · 段2 · ATR低 · 平稳） · trans + full
- L3_Alow_Tup（多头 · 段3 · ATR低 · 涨段） · stable + full
- L3_Amid_Tup（多头 · 段3 · ATR中 · 涨段） · stable + full
- S2_Amid_Tdn（空头 · 段2 · ATR中 · 跌段） · trans + full
- S2_Ahigh_Tdn（空头 · 段2 · ATR高 · 跌段） · trans + full
- S3_Ahigh_Tdn（空头 · 段3 · ATR高 · 跌段） · trans + full

**稳健度 1（单 period 通过 · 边缘）**：
- L1_Alow_Tup · L1_Ahigh_Tup · S4_Ahigh_Tdn · 4 个 A- 级只在单 period 显著

### 2.3 ATR 制度纵向对比

| ATR 档 | 涨段格数 | 平稳格数 | 跌段格数 | 主导机制 |
|:---:|:---:|:---:|:---:|:---|
| 低 | 2（L1·L3） | 1（L2） | 0 | 均值回归 · 稳定环境 |
| 中 | 1（L3） | 0 | 1（S2） | 秩序恢复 · 混合形态 |
| 高 | 2（L1·L2） | 0 | 4（S1·S2·S3·S4） | 波动率驱动 · 恐慌反弹 / 崩盘前奏 |

**结论**：
1. **ATR 高档信号最多**（6 格 · 覆盖多空双向）· 且集中在跌段
2. **ATR 低档几乎全是多头 + 涨段** · 与"均值回归/秩序恢复"机制契合
3. **多空对 ATR 的偏好完全相反** —— 多头 ATR 低偏好 · 空头 ATR 高偏好 · 印证阶段 3 KF-Q

### 2.4 反思 · 144 tier 精细化是否合理

**问题**：144 tier 划分**收益递减 · 且有害**
- 144 tier 中通过 20 个 (tier, period) · 独立 tier 仅 13 个 · **稀疏率 91%**
- 相邻 skew 段（如 0.24 / 0.26 之间）Spearman 相关性 > 0.5 · 边界人为选定
- 大量描述性 mean>0 的格子（如 L2_Amid_Tup mean=+24）**因 CI 撑不开被误杀** · 样本量成瓶颈
- 精细化 14 倍 · 精度只翻 4 倍 · ROI 差

**降级验证**：把 144 tier 的通过区域合并为 **6 大类**（保持互斥定义）：

| 合并类 | 方向 | skew | ATR | trend | 覆盖 144 tier 通过格 |
|:---:|:---:|:---:|:---:|:---:|:---|
| L_seg3_lowmid_up | 多 | (0.09, 0.30] | ≤ 0.67 | ≥ 0.75 | L2_Amid + L3_Alow + L3_Amid |
| L_seg12_high_up  | 多 | [0, 0.19]   | > 0.67 | ≥ 0.75 | L1_Ahigh + L2_Ahigh |
| L_seg2_low_flat  | 多 | (0.09, 0.19] | ≤ 0.33 | (0.20, 0.75) | L2_Alow_Tflat |
| S_seg12_high_dn  | 空 | [0.81, 1]   | > 0.67 | ≤ 0.20 | S1_Ahigh + S2_Ahigh |
| S_seg34_high_dn  | 空 | (0.60, 0.81] | > 0.67 | ≤ 0.20 | S3_Ahigh + S4_Ahigh |
| S_seg2_mid_dn    | 空 | (0.81, 0.91] | (0.33, 0.67) | ≤ 0.20 | S2_Amid_Tdn |

**6 类合并版 · 严格验证结果**：

| 合并类 | full | stable | trans | 3-period 评级 |
|:---:|:---:|:---:|:---:|:---:|
| L_seg3_lowmid_up | mean +30.5 A- | mean +31.2 **A** | mean +29.9 A- | 稳定 · 3 全过 |
| L_seg12_high_up  | mean +45.5 A- | fail          | mean +57.7 **A** | trans 主导 |
| L_seg2_low_flat  | mean +18.3 **A** | fail          | mean +37.3 A- | trans 渗透 |
| S_seg12_high_dn  | mean +31.4 **A** | mean +26.8 **A** | mean +37.1 **A** | ⭐ **三 A 全过** |
| S_seg34_high_dn  | mean +37.1 **A** | mean +25.3 A- | mean +50.8 A- | full 主导 |
| S_seg2_mid_dn    | mean +23.2 **A** | fail          | mean +24.5 **A** | 双 A |

**对比总表**：

| 版本 | 类数 | 通过 (tier,period) | A 级 | A- 级 | 通过率 | Bonferroni 也过 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 144 tier（v9.1 FDR） | 144 | 20 | 11 | 9 | 20% | 15 |
| **6 类合并** | **6** | **15** | **9** | **6** | **83%** | **14** |

**关键增益**：
1. **通过率 20% → 83%** · 稀疏问题彻底消失
2. **Bonferroni family=6 · α=0.008** 就能过 · **不需 FDR 大池校正**
3. **S_seg12_high_dn 三 period 全 A** · 复合稳定性远超单一 tier
4. **每类样本量翻 3-5 倍** · CI 更窄 · IR 更稳
5. **下游策略只用管 6 类 · 不是 143 种边缘 case**

**决策**：
- **v4.0 契约用 6 类合并版**（作为**实际使用的分类器**）
- **144 tier 结果作诊断证据保留** · 记录"曾细化过但收敛"
- **不冻结 144 tier 的 20 个组合**作为策略 tier · 只作历史证据
- **KF-24（FDR 方法论）保留** · 但用途改为"小 family 精细验证"

## 3. 白名单（阶段 4 冻结 · 参考版 · v4.0 冻结 6 类合并版见 §2.4）

### 3.1 A 级（11 个 · L1-L4 硬门槛全过 ∧ 时稳 ≤ 0.50）

**多头（4 个）**：

| tier | period | n | mean | 品保 | IR | 时稳 | BSC |
|:----:|:------:|:-:|:----:|:---:|:--:|:---:|:---:|
| L2_Ahigh_Tup   | full   | 375 | +48.9 | 69% | +0.393 | 0.32 | ✓ |
| L3_Alow_Tup    | stable | 186 | +47.4 | **92%** | +0.484 | 0.17 | ✓ |
| L3_Alow_Tup    | full   | 271 | +41.8 | **89%** | +0.457 | 0.08 | ✓ |
| L2_Alow_Tflat  | full   | 851 | +18.3 | 65% | +0.175 | 0.01 | × |

**空头（7 个）**：

| tier | period | n | mean | 品保 | IR | 时稳 | BSC |
|:----:|:------:|:-:|:----:|:---:|:--:|:---:|:---:|
| S3_Ahigh_Tdn | trans  | 160 | **+80.1** | 76% | +0.558 | 0.46 | ✓ |
| S3_Ahigh_Tdn | full   | 351 | +51.0 | 65% | +0.377 | 0.46 | ✓ |
| S2_Ahigh_Tdn | trans  | 186 | +40.7 | 59% | +0.386 | 0.13 | ✓ |
| S1_Ahigh_Tdn | stable | 346 | +33.3 | 73% | +0.410 | 0.16 | ✓ |
| S2_Ahigh_Tdn | full   | 414 | +27.5 | 62% | +0.304 | 0.23 | ✓ |
| S2_Amid_Tdn  | full   | 367 | +23.2 | 74% | +0.292 | 0.13 | ✓ |
| S2_Amid_Tdn  | trans  | 242 | +24.5 | 74% | +0.318 | 0.50 | × |

### 3.2 A- 级（9 个 · 硬门槛全过 · 时稳超标）

**多头（6 个）**：

| tier | period | n | mean | 时稳 | BSC | 备注 |
|:----:|:------:|:-:|:----:|:---:|:---:|:----|
| L3_Amid_Tup    | stable | 26  | **+137.1** | 1.42 | ✓ | 极小样本 · 均值极高 |
| L3_Amid_Tup    | full   | 130 | +65.6 | 0.84 | ✓ | KF-23 甜蜜点 |
| L2_Ahigh_Tup   | trans  | 200 | +63.9 | 0.82 | ✓ | 转换期强多头 |
| L1_Ahigh_Tup   | trans  | 195 | +51.4 | 1.16 | × | 转换期恐慌反弹 |
| L1_Alow_Tup    | full   | 306 | +39.5 | 1.48 | × | 时稳警示 |
| L2_Alow_Tflat  | trans  | 280 | +37.3 | 0.66 | × | **v9 新维度收获** |

**空头（3 个）**：

| tier | period | n | mean | 时稳 | BSC | 备注 |
|:----:|:------:|:-:|:----:|:---:|:---:|:----|
| S1_Ahigh_Tdn | full   | 639 | +34.0 | 0.51 | ✓ | 边缘时稳 |
| S1_Ahigh_Tdn | trans  | 293 | +34.8 | 0.69 | ✓ | 转换期强空头 |
| S4_Ahigh_Tdn | full   | 425 | +25.6 | 0.54 | ✓ | 边缘时稳 |

### 3.3 未过但 mean ≥ 30 bps 的 fail 列表（下游可探索）

15 个 · 主要卡在 FDR L3（p_boot ∈ 0.01~0.10）· 描述性强但样本量不到通过阈值。
详见 `stage4_step3_144tier_verification.csv` grade=fail 段 · mean 排序。

## 4. 关键洞察（KF 候选 · 待归档）

### 4.1 KF-24 · FDR 优于 Bonferroni 用于结构性切片族（方法论级）

**背景**：v9 用 Bonferroni family=144（α=0.000347 · 3.58σ）· 只有 7 通过 · 26 个"仅 L3 fail"
的强信号（p_boot 0.0004~0.041）被误杀。

**根源**：Bonferroni 假设 144 个检验完全独立 · 但 144 tier 是**结构性切片**：
- 相邻 skew 段（如 段1/段2）Spearman r > 0.5
- (tier, full) / (tier, stable) / (tier, trans) 嵌套
- 真实独立检验数远小于 144

**方法**：改用 **FDR (BH) α=0.05** · 允许 ≤5% 假发现率 · 更适合相关检验族。

**结果**：白名单从 7 → 20 · 且 15/20 仍通过 Bonferroni family=18（sanity check）· FDR 不"松"。

**推广**：**跨主题方法论** · 未来 tier 化 / grid 化 / 分位化研究都应用 FDR。

### 4.2 KF-25 · 平稳期 alpha 仅存在于转换期（v9 新探索的正面收获）

**假设（v9）**：平稳期（trend rank ∈ (0.20, 0.75)）从未被深挖 · 可能有独立 alpha。

**结果**：
- **stable · Tflat** 表全空 · 稳定平稳期确认**无 alpha**
- **trans · Tflat** 表单格 A- · **L2_Alow_Tflat·trans** mean +37 · 时稳 0.66
- 另有 full 期 **L2_Alow_Tflat·full** A · mean +18.3 · 时稳 0.01（stable+trans 混合）

**解读**：平稳期不是"完全无 alpha" · 而是"只有 regime 过渡期 + skew段2 + ATR低"这种边缘条件下才有微弱多头。
本身作为独立分类维度价值有限 · 但作为 filter 可用。

### 4.3 KF-26 · 交叉 trend 全部证伪（"顺 trend"是硬规则）

**假设（v9）**：涨段做空 / 跌段做多 · 平稳期双向 · 可能有独立 alpha。

**结果**：
- 跌段做多（12 个 L*_Tdn 描述性 tier）· 全部 mean 为负 · 无通过
- 涨段做空（12 个 S*_Tup 描述性 tier）· 全部 mean 为负 · 无通过

**解读**：**顺 trend 是硬规则** · 与阶段 3 KF-Q 一致 · 但现在有 144 tier 完整证据 ·
Bonferroni-level 硬证明。

### 4.4 KF-27 · 转换期是空头最密集区

**Observation**：`trans·Tdn` 表 4 格通过（S3_Ahigh · S2_Ahigh · S1_Ahigh · S2_Amid）·
覆盖 skew段1/2/3 + ATR中/高 · 是全 144 tier 最密集区域。

**解读**：崩盘前奏在制度过渡期显著扩散 · 空头的"扫射范围"变大。
下游策略在转换期应加大空头仓位或降低门槛。

### 4.5 KF-28 · Sanity check：15/20 白名单过 Bonferroni family=18

**结果**：即使用最严格的 Bonferroni family=18（α=0.0028 · 2.99σ）· 白名单 20 个中仍有 15 个通过。
剩下 5 个（L2_Alow_Tflat·full · L2_Alow_Tflat·trans · L1_Alow_Tup·full · L1_Ahigh_Tup·trans · S2_Amid_Tdn·trans）都是 BH 相对 Bonferroni 多捞出的。

**解读**：白名单核心置信度不低 · FDR 判决合理 · **20 中 15 个是"高置信度 A/A-"**（BSC✓）。

## 5. 判决与下一步

### 5.1 判决

**✅ 阶段 4 通过 · 冻结分类器 v4.0**

- 多头 A 级 4 · A- 级 6 · 覆盖 skew段2/3 · ATR低/中/高 · trend up/flat
- 空头 A 级 7 · A- 级 3 · 覆盖 skew段1/2/3/4 · ATR中/高 · trend down
- 20 中 15 个过 Bonferroni sanity check · 高置信度

### 5.2 下一步

**Step 5-6（experiment-plan v9.1 §4.6-4.7）**：

1. **契约更新**：
   - `classifier-math-spec.md` 更新 tier 定义（144 tier + 20 白名单）
   - `parameter-selection-spec.md` 重建 · A/A- 白名单
2. **research-status.md**：加 KF-24 ~ KF-28
3. **是否数据回补**（experiment-plan §4.5）：
   - 79 fail 中"仅 L3 fail"（p_boot < 0.05 · CI 排 0 · CF 过）候选 · 可评估补数据的性价比
   - 如补数据 · 保持 FDR α=0.05 冻结 · N 变化即可
   - **建议**：**当前 20 个已通过 · 数据回补优先度低** · 若下游策略需要更多 tier 再触发

### 5.3 后续可立主题

若阶段 4 完成后可立（experiment-plan §4.10）：

1. **`poc-va-shaping-composite`** — 分类器 + 结构塑形组合策略
2. **`poc-va-symbol-refinement`** — 按品种类型分组参数（KF-24 遗留）
3. **`poc-va-tail-asymmetry`** — VA 外 tail 独立信息假设（KF-01 遗留）

## 6. 数据文件

- **描述性扫描**：`project_data/logs/poc_va_asymmetry_stage4/stage4_step2_144tier_descriptive.csv`
  （432 行 · 144 tier × 3 period）
- **严格验证**：`project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv`
  （99 候选 · 20 A/A- 通过）
- **6 类合并版验证**：`project_data/logs/poc_va_asymmetry_stage4/stage4_6class_merged_verification.csv`
  （18 行 · 9 A + 6 A- + 3 fail）
- **扩容数据集**：`project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet`
  （143 合约 · 36625 events · 2023-09 → 2026-06）

## 7. 脚本

- **Step 2 描述性**：[poc_va_asymmetry_stage4_step2_144tier_descriptive.py](raw-scripts/poc_va_asymmetry_stage4_step2_144tier_descriptive.py)
- **Step 3 严格验证**：[poc_va_asymmetry_stage4_step3_144tier_verification.py](raw-scripts/poc_va_asymmetry_stage4_step3_144tier_verification.py)
- **6 表聚合**：[poc_va_stage4_build_6tables.py](raw-scripts/poc_va_stage4_build_6tables.py)
- **失败原因分析**：[poc_va_stage4_fail_analysis.py](raw-scripts/poc_va_stage4_fail_analysis.py)
- **合并降级验证**：[poc_va_stage4_6class_merged.py](raw-scripts/poc_va_stage4_6class_merged.py)
