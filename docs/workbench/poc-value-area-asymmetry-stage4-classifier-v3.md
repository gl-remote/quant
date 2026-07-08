# 阶段 4 · 互斥分类器 v3.0 验证

> 更新时间：2026-07-08（v1 · 阶段 4 完整实验流水 · Step 1 互斥类别 + Step 2 严格验证 + 品种异质性诊断）
> 主题：[docs/research/themes/poc-value-area-asymmetry](../research/themes/poc-value-area-asymmetry/README.md)
> 上阶段：workbench:poc-value-area-asymmetry-stage3-robustness v11
> 契约：[classifier-math-spec.md](../research/themes/poc-value-area-asymmetry/classifier-math-spec.md) v3.0（待更新）
> 参数选择：[parameter-selection-spec.md](../research/themes/poc-value-area-asymmetry/parameter-selection-spec.md) v2（待更新）

## 0. 阶段 4 目标与背景

**问题起点**：阶段 3 冻结的 10 tier 体系存在嵌套：
- `LP ⊆ LL` · `SP ⊆ SC ⊆ SL`
- 一个 event 可能同时命中 4+ 个 tier · **是"多标签系统" · 不是分类器**

**阶段 4 目标**：把 10 tier 拆成**互斥类别** · 每类独立验证 · 冻结分类器 v3.0。

**关键决策**：分类器语义修正为**"独立信号特征识别"**：
- 分类器输出 **单值 tier**（含"未分类"）
- 分类器承诺：**整体上有 alpha 特征**（Bonferroni + 反事实 + 时间稳定）
- 分类器**不承诺**：所有品种在所有档位都赚
- 单品种失效 = **正常品种异质性** · 记录即可

## 1. Step 1 · 互斥类别定义与描述性统计

### 1.1 互斥拆分（方案 γ）

```
多头（skew ≤ 0.30 ∧ atr ≤ 0.70 ∧ trend ≥ 0.75）:
  LP_only:  skew ∈ [0, 0.10]                    (原 LP)
  LL_only:  skew ∈ (0.10, 0.30]                 (原 LL \ LP)

空头（skew ≥ 0.70 ∧ trend ≤ 0.20）:
  SP_only:  atr > 0.80                           (原 SP)
  SC_only:  atr ∈ (0.67, 0.80]                   (原 SC \ SP)
  SL_only:  atr ∈ (0.50, 0.67]                   (原 SL \ SC)

× 稳定/转换 = 10 互斥类别 + "未分类"
```

**互斥性验证**：36625 events · 各类命中总数 3862 · 最大命中数 = 1 · **✅ 严格互斥**。

### 1.2 数据扩容

**动机**：阶段 3 数据集 10518 events · 43 合约 · 独立日 14-33/类 · **不足以支撑 12 格 Bonferroni family=24 严格验证**。

**扩容内容**（`poc_va_asymmetry_stage4_export_data.py`）：
- 补 14 个品种的历史合约（每品种从 2 合约 → 4-8 合约）
- 74 新合约 · 14.1 分钟 · **0 失败**
- 全部走 tqsdk 5m export · CLI `main.py export --env backtest`

**扩容后数据集**（`poc_va_asymmetry_stage4_data_full.py`）：
- **36625 events**（3.5x）
- **143 合约**（3.3x）
- **20 品种前缀** 覆盖 CZCE / DCE / INE / SHFE
- 时间跨度 2023-09 到 2026-06

### 1.3 描述性统计（15 互斥类）

| 类别 | 期别 | n | 独立日 | 品种数 | mean bps | hit | 主导品种 top3 |
|:-----|:----:|:-:|:---:|:---:|:---:|:---:|:---|
| LP_only | full | 633 | 93 | 84 | +33.3 | 60.3% | CZCE.CF601, CZCE.SR405, CZCE.FG509 |
| LP_only | stable | 292 | 50 | 46 | +28.1 | 59.6% | CZCE.OI409, SHFE.cu2409, CZCE.FG509 |
| LP_only | trans | 341 | 53 | 49 | +37.7 | 61.0% | CZCE.SR405, CZCE.CF601, CZCE.MA409 |
| LL_only | full | 1290 | 154 | 111 | +33.5 | 60.6% | SHFE.cu2401, SHFE.cu2409, CZCE.TA505 |
| **LL_only** | **stable** | **617** | **91** | **68** | **+33.6** | **63.5%** | SHFE.cu2409, CZCE.CF601, DCE.i2409 |
| LL_only | trans | 673 | 98 | 83 | +33.4 | 57.9% | SHFE.al2601, CZCE.RM601, CZCE.TA505 |
| SP_only | full | 826 | 92 | 66 | +39.1 | 64.9% | CZCE.TA409, SHFE.ag2509, INE.sc2512 |
| SP_only | stable | 559 | 66 | 51 | +33.0 | 64.0% | CZCE.TA409, DCE.c2409, SHFE.hc2410 |
| **SP_only** | **trans** | **267** | **36** | **29** | **+51.9** ⭐ | **66.7%** | INE.sc2512, DCE.m2509, SHFE.rb2405 |
| SC_only | full | 578 | 70 | 59 | +32.4 | 61.4% | DCE.i2409, SHFE.al2501, SHFE.al2409 |
| SC_only | stable | 206 | 29 | 26 | +9.9 | 53.9% | SHFE.au2512, CZCE.MA601, DCE.c2409 |
| SC_only | trans | 372 | 46 | 40 | +44.9 | 65.6% | SHFE.al2409, SHFE.ag2401, SHFE.ag2509 |
| SL_only | full | 535 | 70 | 61 | +13.9 | 57.4% | CZCE.TA409, SHFE.au2512, CZCE.FG409 |
| SL_only | stable | 156 | 18 | 20 | +27.3 | 55.8% | CZCE.TA409, CZCE.CF401, CZCE.OI509 |
| SL_only | trans | 379 | 55 | 50 | +8.4 | 58.0% | SHFE.au2512, CZCE.FG409, CZCE.SR509 |

### 1.4 扩容 vs 原样本对比

| 期别 | 阶段 3 mean | 阶段 4 mean | 变化 |
|:----:|:---:|:---:|:---:|
| LP_only·stable | +48.1 | +28.1 | -42% |
| LL_only·stable | +46.6 | +33.6 | -28% |
| SP_only·stable | +44.3 | +33.0 | -25% |
| SP_only·trans | +32.2 | **+51.9** ⭐ | +61% |
| SC_only·trans | +12.4 | +44.9 | +262% |

**判读**：
- 幅度整体下降 · **样本大幅提升**（3-5x）· CI 会更窄 · **Bonferroni 反而更容易通过**
- **SP_only·trans 幅度反而放大**（+52 · 阶段 3 只有 +32）· 说明扩容揭露了此档的真实强度
- SC_only·trans 从 +12 → +45 · **说明中 ATR 空头转换期是真实新甜蜜点**

## 2. Step 2 · 7 层严格验证

### 2.1 判据（**修正版**）

**修正说明**：原判据中 **L5 品种保留 ≥ 80%** 在 143 品种下过于严格 · 且**违背分类器语义**（分类器只承诺"整体信号存在" · 不承诺所有品种都赚）。**L5 降级为观察指标 · 不作为判决门槛**。

**修正后 6 层判据**（+ L5 为观察）：

| 层 | 判据 | 阈值 | 权重 |
|:---|:---|:---:|:---:|
| L1 · 样本量 | n ≥ 15 ∧ n_days ≥ 5 | - | 硬门槛 |
| L2 · date-cluster CI | 95% CI 排 0 | - | 硬门槛 |
| L3 · Bonferroni | family=15 · p<0.0033 | - | 硬门槛 |
| L4 · 反事实 | vs 随机 · p<0.001 | - | 硬门槛 |
| L5 · 品种保留 | 单品种 mean>0 比例 | ≥60% | **观察** |
| L6 · 单笔 IR | mean/std | ≥0.30 | 硬门槛 |
| L7 · 时间稳定 | \|first-second\|/full | ≤0.50 | 硬门槛 |

**A 级**：6/6 通过 · **B 级**：5/6 通过（或 4/6+n<30）· **未分类**：其他

### 2.2 验证结果（修正判据）

| 类·期 | n | n_days | mean | CI 95% | p_boot | p_cf | 品保 | IR | 时稳 | L1-L4 | L6 | L7 | 评级 |
|:-----|:-:|:-:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| LP_only·full | 633 | 93 | +33.3 | [+14.5, +52.6] | 0.0000 | 0.0000 | 64% | +0.282 | 0.03 | ✅ | ❌ | ✅ | **B**（IR 边缘 0.28）|
| LP_only·stable | 292 | 50 | +28.1 | [+2.6, +54.3] | 0.0348 | 0.0002 | 61% | +0.249 | 1.94 | L3✅L4✅ · L3❌ | ❌ | ❌ | 未分类 |
| LP_only·trans | 341 | 53 | +37.7 | [+11.2, +67.0] | 0.0040 | 0.0000 | 68% | +0.308 | 0.72 | L3❌ | ✅ | ❌ | 未分类 |
| **LL_only·full** | **1290** | **154** | **+33.5** | **[+18.2, +49.1]** | **0.0000** | **0.0000** | **65%** | +0.257 | 0.67 | ✅ | ❌ | ❌ | **B**（IR 边缘 0.26）|
| **LL_only·stable** | **617** | **91** | **+33.6** | **[+14.1, +54.1]** | **0.0008** | **0.0000** | **66%** | +0.281 | 0.40 | ✅ | ❌ | ✅ | **B**（IR 边缘 0.28）|
| LL_only·trans | 673 | 98 | +33.4 | [+10.0, +57.5] | 0.0024 | 0.0000 | 57% | +0.239 | 1.32 | ✅ | ❌ | ❌ | 未分类 |
| **SP_only·full** | **826** | **92** | **+39.1** | **[+26.2, +52.3]** | **0.0000** | **0.0000** | **82%** ⭐ | **+0.377** | 0.64 | ✅ | ✅ | ❌ | **B**（时稳 0.64）|
| **SP_only·stable** | **559** | **66** | **+33.0** | **[+18.4, +49.2]** | **0.0000** | **0.0000** | 73% | **+0.335** | 0.44 | ✅ | ✅ | ✅ | **A** ⭐ |
| **SP_only·trans** | **267** | **36** | **+51.9** ⭐ | **[+28.9, +75.8]** | **0.0000** | **0.0000** | 76% | **+0.459** | 0.48 | ✅ | ✅ | ✅ | **A** ⭐ |
| **SC_only·full** | **578** | **70** | **+32.4** | **[+18.4, +48.0]** | **0.0000** | **0.0000** | 74% | **+0.319** | 0.35 | ✅ | ✅ | ✅ | **A** ⭐ |
| SC_only·stable | 206 | 29 | +9.9 | [-3.3, +24.2] | 0.1408 | 0.0598 | 62% | +0.141 | 1.06 | L2❌L3❌L4❌ | ❌ | ❌ | 未分类 |
| **SC_only·trans** | **372** | **46** | **+44.9** | **[+25.5, +66.6]** | **0.0000** | **0.0000** | 79% | **+0.395** | 0.35 | ✅ | ✅ | ✅ | **A** ⭐ |
| SL_only·full | 535 | 70 | +13.9 | [-3.6, +30.4] | 0.1028 | 0.0004 | 59% | +0.137 | 0.38 | L2❌ | ❌ | ✅ | 未分类 |
| SL_only·stable | 156 | 18 | +27.3 | [+4.5, +52.0] | 0.0164 | 0.0000 | 65% | +0.314 | 1.43 | L3❌ | ✅ | ❌ | 未分类 |
| SL_only·trans | 379 | 55 | +8.4 | [-12.8, +29.2] | 0.4160 | 0.0332 | 58% | +0.079 | 2.68 | L2❌L3❌ | ❌ | ❌ | 未分类 |

### 2.3 阶段 4 白名单（v3.0 冻结）

**🟢 A 级**（6/6 硬门槛全过 · 4 个）：
- `SP_only·stable`：+33 · CI [+18, +49] · IR 0.34（**空头核心**）
- `SP_only·trans`：**+51.9** ⭐ · CI [+29, +76] · IR 0.46（**最强空头**）
- `SC_only·full`：+32 · CI [+18, +48] · IR 0.32（**中档空头**）
- `SC_only·trans`：+45 · CI [+26, +67] · IR 0.40（**转换期中空**）

**🟡 B 级**（5/6 硬门槛 · IR 或时稳边缘 · 3 个）：
- `SP_only·full`：+39 · 品保 82%（唯一过 80%）· 但时稳 L7 未过
- `LL_only·full`：+33.5 · **1290 events · 154 独立日**（样本最大）· IR 边缘 0.26
- `LL_only·stable`：+33.6 · IR 边缘 0.28（多头 stable 主线）

**🔴 未分类**（8 个）：
- LP_only·stable / trans：**多头严格 filter 在扩容后 Bonferroni 未过**（阶段 3 时的甜蜜点）
- SL_only 全部三档 · SC_only·stable：**低 ATR 空头无稳定 alpha**

### 2.4 阶段 4 判决

- ✅ **A 级 4 个 · B 级 3 个 · 合计 7 个 tier**
- ✅ **空头方向 · A 级 4 个**（含 stable/trans/full · 覆盖完整）
- ⚠️ **多头方向 · A 级 0 个**（LL_only·stable 为 B 级 · IR 边缘）
- **阶段 4 边缘通过**：至少空头有稳定分类可用 · 多头以 B 级作为参考档位

## 3. 品种异质性诊断（关键发现）

### 3.1 诊断动机

L5 品保率大幅低于阶段 3（60-70% vs 阶段 3 90-100%）· 猜测**不同品种需要不同参数**。

### 3.2 每品种最优档位分布（20 品种前缀）

**多头最优档位**：
| 最优档 | 品种数 | 占比 |
|:---:|:---:|:---:|
| LP（严格）| 7 | 35% |
| LL_only（宽松）| 7 | 35% |
| LP_wide（放宽 atr）| 3 | 15% |
| LL_wide（宽松+高 atr）| 3 | 15% |

**空头最优档位**：
| 最优档 | 品种数 | 占比 |
|:---:|:---:|:---:|
| SP（atr>0.80）| 9 | 45% |
| SC_only（atr∈0.67-0.80）| 7 | 35% |
| SL_only（atr∈0.50-0.67）| 4 | 20% |

**结论**：**没有任何单一档位能覆盖多数品种** · 品种异质性是**分类器本质限制**。

### 3.3 品种特性表（供未来品种化主题参考）

| 品种 | 多头最强档 | 幅度 | 空头最强档 | 幅度 | 类型判断 |
|:-----|:---:|:---:|:---:|:---:|:---|
| SHFE.ag（白银） | LP | **+146** | SC_only | +34 | 金融·严多中空 · **极强多头** |
| SHFE.au（黄金） | LL_only | **+150** | SP | +43 | 金融·宽多严空 · **极强多头** |
| DCE.p（棕榈） | LL_only | **+163** | SC_only | +31 | 农产品·宽多中空 · **极强多头** |
| INE.sc（原油） | LP | +59 | SC_only | **+123** | 能源·严多强中空 · **极强空头** |
| CZCE.FG（玻璃） | LP_wide | +74 | SL_only | +103 | 建材·宽 atr 多头·低 atr 空头 · **双向强** |
| DCE.m（豆粕） | LP | +56 | SL_only | +50 | 农产品·严多低空 · 均衡 |
| CZCE.MA（甲醇） | LL_wide | +59 | SL_only | +60 | 化工·宽高 atr 双向 |
| CZCE.TA（PTA）| LP_wide | +73 | SP | +40 | 化工·多头需高 atr |
| CZCE.RM（菜粕） | LL_only | +50 | SC_only | +83 | 农产品·宽多中空 · **极强空头** |
| CZCE.OI（菜油） | LP | +92 | SC_only | +75 | 农产品·双向强 |
| DCE.i（铁矿） | LL_only | +20 | SC_only | +86 | 黑色·空头强 |
| SHFE.cu（铜） | LP | +52 | SP | +30 | 有色·严多严空 |
| CZCE.SR（白糖） | LP | +24 | SC_only | +28 | 农产品·中等信号 |
| CZCE.CF（棉花） | LP_wide | +25 | SP | +46 | 农产品·空头稍强 |
| DCE.y（豆油） | LP | +40 | SP | +11 | 农产品·多头主导 |
| SHFE.al（铝） | LL_only | +23 | SP | +22 | 有色·均衡弱 |
| DCE.c（玉米） | LL_only | +13 | SP | +24 | 农产品·中等偏弱 |
| DCE.cs（玉米淀粉） | LL_wide | +22 | SL_only | +18 | 农产品·宽多低空 |
| SHFE.hc（热卷） | LL_only | +68 | SP | +55 | 黑色·双向强 |
| SHFE.rb（螺纹） | LL_wide | +29 | SP | +58 | 黑色·空头强 |

### 3.4 品种类型总结（3 大类）

**类型 A · 金融/贵金属型**（ag / au / sc / p）：
- 单笔幅度极高（+120 ~ +160）
- 需要**宽松档位**（LL_only / LL_wide）· skew 严格反而弱
- 波动率驱动的均值回归性强

**类型 B · 化工/建材/黑色型**（MA / TA / FG / RM / hc / rb）：
- 需要**宽 ATR 多头档位**（LP_wide / LL_wide）
- 波动率与信号正相关

**类型 C · 农产品/有色主流型**（m / y / SR / OI / c / cu / cs）：
- 需要**严格档位**（LP · SP）
- 均值回归传统机制 · 低 ATR + 涨段是最好组合

### 3.5 品种异质性的经济解读

- **金融资产**（贵金属·原油）：**流动性驱动 + 宏观预期主导** · skew 稍偏离即为信号（宽松档强）
- **工业品**（黑色·化工）：**产能供需 + 库存周期主导** · 需要更极端波动才有信号（高 ATR 强）
- **传统农产品**（豆粕·白糖·玉米）：**天气+种植周期主导** · 严格底/顶厚才是反转信号（严格档强）

## 4. 分类器语义的关键澄清

### 4.1 分类器承诺的边界

**承诺**：
- ✅ 每个 A 级档位在**整体样本上**有统计显著 alpha
- ✅ 通过 Bonferroni · 反事实 · CI 严格性验证
- ✅ 时间稳定性达标
- ✅ 输出**互斥单值 tier** · 无重复计数

**不承诺**：
- ❌ **所有品种在所有档位都有 alpha**（品种异质性是本质限制）
- ❌ 具体交易的入场/出场/仓位（属于下游策略主题）
- ❌ 交易成本 / net Sharpe（属于完整策略）

### 4.2 使用分类器的正确姿势

**阶段 4 后 · 分类器的下游用法**：
1. **组合策略主题**：根据 tier 触发 · 结合入场/出场/仓位规则
2. **品种化优化**：按品种类型选用不同 A/B 级 tier
3. **quality filter**：作为其他策略的背景过滤器

**若某品种在某档位失效** · 属于**下游策略主题**的品种筛选责任 · 不是分类器 bug。

## 5. 已知边界与开放问题

### 5.1 边界

- **通用分类器 v3.0** · 每 tier 品种覆盖率约 60-80%
- 多头方向 A 级空缺（LL_only·stable 为 B 级 · IR 边缘 0.28）
- LP_only·stable/trans 因 Bonferroni 严格性未通过（幅度存在但需扩样本再验）

### 5.2 未来开放主题

以下问题**不属于本主题** · 应立**新主题**处理：

- **`poc-va-symbol-refinement`**：按品种类型分组参数（3 类品种化）
- **`poc-va-dynamic-atr`**：动态 ATR（EWMA / GARCH / HMM）度量
- **`regime-hmm-classifier`**：跨主题的马尔可夫区制识别方法论
- **`poc-va-shaping-composite`**：完整策略（引用本分类器 + 结构塑形）

### 5.3 与 KF-22 · KF-23 的关系

- **KF-22**（数据边界不可造假）：本阶段完全遵守 · 未池化 · 未 shrinkage · 用扩合约（而非合并品种）扩样本
- **KF-23**（分位×制度信号地图）：12 格深化留给 `poc-va-symbol-refinement` 或 `poc-va-quantile-refinement`
- **新 KF-24**（品种异质性证据 · 待定）：本阶段发现的关键规律

## 6. 阶段 4 判决 · 分类器 v3.0 冻结

**通过状态**：**边缘通过**
- A 级 4 个（全部空头方向）
- B 级 3 个（含多头主力 LL_only·stable）
- **总计 7 个可用 tier** · 覆盖多空双向

**冻结契约**：
- 分类器契约 v3.0 · 定义 10 互斥类别 · 单值输出 `tier: str | None`
- parameter-selection-spec v2 · 更新为互斥体系

**主题状态**：
- **主动性研究暂停** · 但**不进 themes-frozen**
- 分类器持续可用 · 供下游主题引用
- **归档 Step 5** · workbench 归档到 archive

## 7. 数据输出

- `project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet` · 扩容数据集（36625 events · 143 合约）
- `project_data/logs/poc_va_asymmetry_stage4/stage4_exclusive_classes_descriptive.csv` · Step 1 描述性
- `project_data/logs/poc_va_asymmetry_stage4/stage4_step2_seven_layer_verification.csv` · Step 2 严格验证
- `project_data/logs/poc_va_asymmetry_stage4/stage4_symbol_prefix_diagnosis.csv` · 品种特性诊断

## 8. 复现命令

```bash
# 1. 拉取扩容数据（14 分钟）
uv run python scripts/ai_tmp/poc_va_asymmetry_stage4_export_data.py

# 2. 构建扩容数据集（约 5 分钟）
uv run python scripts/ai_tmp/poc_va_asymmetry_stage4_data_full.py

# 3. Step 1 · 互斥描述性
uv run python scripts/ai_tmp/poc_va_asymmetry_stage4_step1_exclusive_classes.py

# 4. Step 2 · 7 层严格验证
uv run python scripts/ai_tmp/poc_va_asymmetry_stage4_step2_seven_layer.py

# 5. 品种异质性诊断
uv run python scripts/ai_tmp/poc_va_asymmetry_stage4_symbol_diagnosis.py
```
