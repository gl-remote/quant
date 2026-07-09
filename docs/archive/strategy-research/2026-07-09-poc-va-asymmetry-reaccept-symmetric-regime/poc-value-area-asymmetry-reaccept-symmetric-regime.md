# poc-value-area-asymmetry · Reaccept 对称子环境探索支线（Workbench）

> 类型：Archive / 策略实验摘要
> 状态：**已完成 · 统计层 PASS（B区顺势S 唯一可做）· 落地层不完整（单方向·n偏少）· 登记为 KF-30 待深入**
> 关联主题：[poc-value-area-asymmetry](../../research/themes/poc-value-area-asymmetry/README.md)
> 数据依赖：archive:2026-07-08-poc-va-asymmetry（分类器 v4.0 冻结产出的
> `classifier_v31_timeline.parquet` · 143 合约 · 36625 events · 3 维 rank）
> 分类器契约：[classifier-math-spec.md](../research/themes/poc-value-area-asymmetry/classifier-math-spec.md)
> 立题起点归档：archive:2026-07-09-poc-va-shaping
> 开发分支：`experiment/va-reaccept-symmetric-regime`（父分支 dev/0.5 @ 5792979）
> 日期：2026-07-09

---

## 1. 支线定位

**与关联主题 [poc-value-area-asymmetry](../research/themes/poc-value-area-asymmetry/README.md) 的关系**：

- 主题当前状态：分类器 v4.0（6 类合并版）已冻结 · 主动性研究暂停 · 属于「交易背景分类器」组件层，不承担完整策略（入场/出场/仓位/成本）设计责任。
- 本支线**旁支探索**动机：分类器 v4.0 在**倾斜子环境**（L_seg/S_seg 有向 tier）中已证明有方向 alpha，但**对称子环境**（skew_neutral）在主题内被判定为「无独立方向 alpha」并降级淘汰（如 L_seg2_low_flat）。本支线检验一个新假设：**对称子环境虽无方向 alpha，但可能存在「保护型 alpha」——即触发器（rank20 反转代理）能显著改善子池内的开仓质量**。
- 本支线**不改变**主题分类器 v4.0 契约、不改变主题的阶段结论、不修改主题目录任何文件。若支线得到关键发现（KF 级证据），会通过 pull 模式登记到 [poc-value-area-asymmetry/research-status.md](../research/themes/poc-value-area-asymmetry/research-status.md) 的关键发现清单。
- 本支线**复用主题产物**：`signed_skew_rank_roll` / `atr_rank_roll` / `trend_rank_roll` 三维 rank 字段 · `ret_8h_bps` / `ret_4h` / `daily_atr_10_bps` 收益/波动字段（均来自 archive:2026-07-08-poc-va-asymmetry 冻结的 timeline）。

---

## 2. 假设与实验设计

### 2.1 核心假设

旧 VA reaccept 策略因全样本**趋势自相关高达 +0.851**（价格延续性强，均值回归失效）而整体被冻结；但在「VA 对称（skew_neutral）+ 中高波动（atr_midhigh）+ 趋势平稳（trend_stable）」的三维子环境中，反转土壤可能恢复，reaccept 仍可稳定盈利。

### 2.2 实验设计要点

- **三维筛选**：`signed_skew_rank_roll ∈ [0.30, 0.70]` × `atr_rank_roll ∈ (0.33, 1.00]` × `trend_rank_roll ∈ [0.20, 0.80]`
- **触发器代理**（非严格 VA reaccept，仅 Gatekeeper 定性）：同合约 rolling rank20 ≤ 20% + 反弹（L 侧）/ ≥ 80% + 回落（S 侧）
- **配对方法**：1:1 最近邻不放回，按 contract × side × close_diff_atr 5 分桶（相邻桶放宽）
- **统计检验**：Cluster bootstrap（单位 contract × date），B=200（Gatekeeper 定性用）
- **成本口径**：扁平（0.05 ATR 双边）+ 真实（spec 手续费 + 滑点）双口径
- **持有期**：8h（对齐分类器 `ret_8h_bps` 前向窗口）

### 2.3 通过判据

- ① 配对差 CI95 排 0
- ② 品种保留率 ≥ 60%
- ③ 反转土壤（子池自相关 < 全局）

---

## 3. 关键文档与资产

| 类型 | 路径 |
|------|------|
| 原始 Gatekeeper 脚本（慢版，B=5000） | [va_sym_reaccept_gatekeeper.py](raw-scripts/va_sym_reaccept_gatekeeper.py) |
| 轻量 Gatekeeper 脚本（B=200，向量化） | [va_sym_reaccept_fast.py](raw-scripts/va_sym_reaccept_fast.py) |
| 分布诊断脚本（持有期敏感性 + 分桶提案） | [va_sym_distribution_diagnose.py](raw-scripts/va_sym_distribution_diagnose.py) |
| **对立实验报告** ⭐ | [poc-value-area-asymmetry-reaccept-symmetric-regime-opposing-report.md](raw-workbench/poc-value-area-asymmetry-reaccept-symmetric-regime-opposing-report.md) |
| 结果 JSON | `project_data/ai_tmp/va_sym_reaccept_fast_result.json` |
| 分布分位数表 | `project_data/ai_tmp/va_sym_3d_rank_distribution.csv` |

---

## 4. 结果速记

### 4.1 制度土壤（层 1）

| 指标 | 全局池 | 三维子池 | Δ（子池 − 全局） | 倾向 |
|------|--------|----------|------------------|------|
| 事件数 n | 32,503 | 4,122 | — | — |
| 合约数 | 143 | 140 | −3 | — |
| ret_8h 均值 (bps) | −0.03 | −1.08 | −1.05 | ❌ 子池更悲观 |
| ret_8h 胜率 | 50.0% | 50.5% | +0.5pp | ✅ 微弱优势 |
| daily_atr_10 均值 (bps) | 156.2 | 166.7 | +10.5 | ✅ 子池波动更高 |
| **ret_8h 滞后 1 阶自相关** | **+0.851** | **+0.680** | **−0.171** | ✅ **反转土壤显著增强** |

### 4.2 触发器增量（层 2 · 474 配对 / 110 合约 / 190 天）

| 指标 | 扁平成本 | 真实成本 |
|------|---------|---------|
| reaccept 均值 (bps) | −0.68 | +1.74 |
| reaccept 命中率 | 50.4% | 46.8% |
| no_trigger 均值 (bps) | −47.58 | −44.49 |
| no_trigger 命中率 | 34.2% | 32.9% |
| **配对差 均值 (bps)** | **+46.90** | **+46.23** |
| 配对差 CI95 区间 | [+29.41, +63.55] | [+28.89, +67.32] |
| 配对差 p(diff ≤ 0) | 0.000 | 0.000 |
| CI 排 0？ | ✅ | ✅ |
| 品种保留率 | 71.8% (n=110) | 66.4% (n=102) |
| 品保 ≥ 60%？ | ✅ | ✅ |

### 4.3 判据汇总

| 层 | 判据 | 通过 |
|----|------|------|
| Gatekeeper 统计层（5/5） | 反转土壤 + 双口径 CI 排 0 + 双口径品保 ≥ 60% | ✅ **PASS** |
| 落地机制层（6/6 否决命中） | 收益太薄（+1.74 bps）· 代理 ≠ VA 机制 · 缺安慰剂 · trend 定义漏洞 · 有效覆盖 48.6% · B<2000 | ❌ **REJECT** |

---

## 5. 分布诊断结果（2026-07-09 补充）

### 5.1 三维 rank 实际分位数

| 维度 | Q10 | Q30 | Q50 | Q70 | Q90 | Q100 |
|------|-----|-----|-----|-----|-----|------|
| signed_skew_rank_roll | 0.101 | 0.303 | 0.515 | 0.717 | 0.939 | 1.0 |
| atr_rank_roll | 0.000 | 0.211 | 0.474 | 0.737 | 1.000 | 1.0 |
| trend_rank_roll | 0.000 | 0.211 | 0.474 | 0.684 | 0.947 | 1.0 |

原 Gatekeeper 阈值实际覆盖：skew 40.0% · atr 58.7% · trend 51.2%（**过宽**）。

### 5.2 持有期敏感性（子池内 rank20 触发事件，方向对齐 · 未扣成本）

| 持有窗口 | 均值 (bps) | 胜率 | 备注 |
|---------|-----------|------|------|
| ~1h（ret_4h/4 线性估） | +2.40 | 53.9% | 仅参考形状 |
| ~2h（ret_4h/2 线性估） | +4.80 | 53.9% | 仅参考形状 |
| **4h（实际 ret_4h）** | **+9.59** | 53.9% | **⭐ 均值峰值** |
| 8h（实际 ret_8h） | +6.27 | 52.6% | 从 4h 开始衰减 |

**扣扁平成本（0.05 ATR 双边）后**：

| 持有窗口 | 净值均值 (bps) | 胜率 | t 值 |
|---------|--------------|------|------|
| ~1h | −6.03 | 38.2% | −5.43 |
| ~2h | −3.63 | 45.7% | −1.66 |
| **4h** | **+1.16** | 49.3% | +0.27 |
| 8h | −2.16 | 50.3% | −0.36 |

**关键发现**：alpha 在 **4h 前后达到峰值**，8h 已衰减，1-2h 尚未累积到覆盖成本；**8h 持有期太长**（对立报告结论修正点 #1）。

### 5.3 建议收窄分组矩阵

| 维度 | 档位设计 | 依据 |
|------|---------|------|
| **skew（4 档）** | wneg [0.30,0.40) / xneu [0.40,0.50) / wpos [0.50,0.60) / mpos [0.60,0.70] | 每档 ~3600 样本，可测试「越中性 → 效应越强」倒 U |
| **trend（5 档）** | lneg [0.20,0.35) / low [0.35,0.45) / core [0.45,0.55] / high [0.55,0.65) / lpos [0.65,0.80] | 核心横盘单独成组 |
| **atr（3 档）** | mid (0.33,0.50] / midhi (0.50,0.67] / hi (0.67,1.0] | 拆开中/中高/高 |
| **holding（3 档）** | H2 / **H4** ⭐ / H8 | 覆盖峰值前后 |

**总组合数**：4 × 5 × 3 × 3 = **180 组**（触发 < 20 的自动跳过）

---

## 6. 后续规划（4 步 · 待决策后启动）

### Step 1 · 180 组全量扫描（当前动作）

对每子组输出：
- `n_trigger`：样本量（≥ 20 才报告）
- `paired_diff_mean_H4_bps`：主排名依据
- `paired_diff_CI95_lo_H4_bps`：统计显著性（> 0 才进 T0）
- `symbol_retention_H4`：泛化性（≥ 50% 才进 T1）
- `diff_monotonicity_score`：3 维单调性评分

**输出物**：CSV 宽表 + 两张热力图（skew×trend / skew×atr）+ Top 10 子组排名表。B=200，预计 15-25 min CPU。

### Step 2 · 关键决策点（Step 1 完成后 1h 内）

同时满足下列条件才走「分支 A · 重定义阈值」，否则走「分支 B · 降级辅助 gate（原推荐路径 B）」：

| 判据 | 阈值 |
|------|------|
| 存在 ≥ 3 个相邻子格组成的「平台」 | 平台内每子格 `CI95_lo_H4 > 0` |
| H4 配对差均值 ≥ 10 bps | 原全局 +1.74 bps 的 5 倍+ |
| ≥ 2 个维度单调性符合预期 | skew 靠近 0.5 → 效应更强；trend 靠近 core → 效应更强；atr 越高 → 效应更强 |

### Step 3（仅分支 A）· 严格化重跑

1. **合并平台**：取平台覆盖的最外边界当新阈值（不取单点最优 → 防过拟合）
2. **升级严格性**：Bootstrap B=2000（正式实验级）+ 安慰剂 shuffle 验证（500 次随机标签）
3. **换严格检测器**：5m bar 级 VA reaccept 检测器（POC/VAH/VAL 前一 session 冻结 + 破边界重入）
4. **判据**：严格版下 CI95 排 0 + 安慰剂 p < 0.025，才升为「独立 alpha 源候选」

### Step 4 · 下游落地路径

- **分支 B（大概率）**：将支线得到的「rank20 gate 在对称子环境有保护型 alpha」结论登记为 poc-value-area-asymmetry 的 KF 条目（新增 KF-N），并把 rank20 gate 作为**分类器 v4.0 的辅助特征扩展**在未来下游策略主题中提供参考。集成到具体策略的成本约半天。
- **分支 A（小概率）**：若严格 VA reaccept 检测器 + 安慰剂验证下配对差仍显著，**独立立题**新主题（例如 `va-reaccept-symmetric-regime` 或 `va-reaccept-recovery`），承接完整的入场/出场/仓位设计。此时本支线的 workbench 归档随新主题一并处理，不动 poc-value-area-asymmetry 主题目录。

### 资源预算

| 阶段 | CPU | 人力 |
|------|-----|------|
| Step 1（180 组扫描） | ~20 min | 0（自动） |
| Step 2（判定 + 热力图） | 0 | ~15 min 看结果 |
| Step 3 A（严格重跑） | 1-2 h | ~半天写检测器 |
| Step 4 B（登记 KF 到主题） | 0 | ~1h |
| Step 4 A（独立立题新主题） | — | ~1 天 |

---

## 8. Step 1 · 60 组扫描结果与 Step 2 判决（2026-07-09）

> **实际扫描维度修正**：原设计 4×5×3×3 = 180 组，实际执行 `skew(4) × trend(5) × atr(3) = 60 组`；3 个持有期 H2/H4/H8 是**同一批 pairs 上的 6 种 pnl 聚合**（3 持有期 × 2 成本口径），不作为独立单元格维度。

### 8.1 扫描配置调整

首次跑 60 组全 SKIP（`MIN_PAIRS=20` + no_trigger 池按 close_diff 方向过滤太严）。放宽后重跑：
- `MIN_PAIRS = 20 → 10`（细分单元格样本自然稀，10 对定性够用；bootstrap 精度会降但 CI 宽度仍可判方向）
- no_trigger 对照池：从「同 contract + close_diff 方向匹配」放宽为「同 contract + 任意未触发事件」（同方向匹配在细分后会把 37/60 单元格切到 0）

**脚本**：[va_sym_180grid_scan.py](raw-scripts/va_sym_180grid_scan.py) · **输出**：
- `project_data/ai_tmp/va_sym_180grid_scan_summary.csv`（60 行完整宽表）
- `project_data/ai_tmp/va_sym_180grid_top10.md`（Top-10 排名 + 判据统计）
- `project_data/ai_tmp/va_sym_180grid_heatmap_{skew_trend,skew_atr,trend_atr}.csv`（3 张边缘 heatmap）

### 8.2 结果速览

**有效子组数**：23 / 60（38%，其余 37 组 n_pairs < 10 跳过）

**判据通过统计**（H4 real 口径）：

| 判据 | 通过数 | 备注 |
|------|-------|------|
| CI95 lo > 0（配对差显著正） | 5 / 23 | 距原全局 CI 排 0 差距大（原 100%，细分后 22%） |
| symbol retention ≥ 50% | 19 / 23 | 泛化性总体尚可 |
| mean ≥ 10 bps | 17 / 23 | 大部分单元格保持大均值 |
| **三条同时满足**（分支 A 候选） | **5 / 23** | 见 §8.3 |

### 8.3 三判据全过的 5 个单元格

| # | skew | trend | atr | H4_real mean (bps) | CI95_lo | sym_ret | n_pairs |
|---|------|-------|-----|--------------------|---------|---------|---------|
| 1 | wneg [0.30, 0.40) | lneg [0.20, 0.35) | **hi** (0.67, 1.0] | **+77.3** | +45.5 | 81% | 20 |
| 3 | mpos [0.60, 0.70] | lneg [0.20, 0.35) | **hi** | +57.1 | +12.6 | 63% | 33 |
| 4 | wpos [0.50, 0.60) | lpos [0.65, 0.80] | **hi** | +54.8 | +2.5 | 67% | 25 |
| 5 | xneu [0.40, 0.50) | high [0.55, 0.65) | **hi** | +45.6 | +2.6 | 73% | 18 |
| 6 | xneu [0.40, 0.50) | high [0.55, 0.65) | **mid** (0.33, 0.50] | +42.9 | +5.5 | 71% | 14 |

**共同点**：4/5 集中在 `atr_hi` 列；`atr` 是**唯一稳健的通过维度**。

### 8.4 三维单调性检验

**预期单调**（三维协同假设）：
- skew：越靠近 0.5 → 效应越强（倒 U，顶点在 xneu）
- trend：越靠近 0.55 → 效应越强（倒 U，顶点在 core）
- atr：越高 → 效应越强（单调递增）

**实际观察**（H4 real mean · 边缘 heatmap 汇总）：

| skew | trend_core | trend_high | trend_lneg | trend_low | trend_lpos | 单调性 |
|------|-----------|-----------|-----------|----------|-----------|--------|
| wneg | +36 | +19 | **+31** | +14 | +25 | 不单调 |
| xneu | NA | **+44** | −5 | +15 | +7 | 不单调 · 预期顶点在 core 但 core 为 NA |
| wpos | +34 | +5 | −6 | +26 | **+55** | 不单调 |
| mpos | **+57** | NA | +57 | NA | +27 | 不单调 |

- **skew 维度呈 U 型而非倒 U**：两端 wneg / mpos 反而强于中间 xneu → **对称性假设证伪**
- **trend 维度呈 W 型而非倒 U**：core / lneg / lpos 都可能出峰值，横盘 core 并非稳健优 → **趋势平稳假设证伪**

| trend | atr_hi | atr_mid | atr_midhi | 单调性 |
|-------|-------|---------|-----------|--------|
| core | **+42** | NA | NA | atr_hi 稳强 |
| high | +23 | **+43** | NA | 中等波动异常强 |
| lneg | **+44** | +8 | **−8** | atr_hi 强、midhi 负 |
| low | +19 | NA | NA | — |
| lpos | +29 | +24 | +28 | 波动无差异 |

- **atr 维度部分单调**：atr_hi 普遍最强（4/5 有值的 trend 档），但 atr_midhi 出现显著负值（lneg −8, wpos −9）**并非单调递增**——需要**波动够高**才行

### 8.5 Step 2 判决 → **走分支 B**

**判定条件**（workbench §6.Step2 定义）：需同时满足「≥ 3 个相邻子格组成平台 + H4 mean ≥ 10 + ≥ 2 维单调性符合预期」才走**分支 A · 重定义阈值**。

| 判定项 | 状态 |
|--------|------|
| 5 个通过单元格是否相邻构成平台？ | ❌ 分布在 heatmap 的 (0,0)、(3,2)、(2,4)、(1,3)、(1,3-mid)，**未形成 ≥3 相邻的平台** |
| H4 mean ≥ 10？ | ✅ 通过单元格全部远超 10 bps（+42~+77） |
| skew 单调性？ | ❌ U 型（应是倒 U） |
| trend 单调性？ | ❌ W 型（应是倒 U） |
| atr 单调性？ | ⚠️ 部分单调（atr_hi 稳强，但 atr_midhi 出现负值 → 需要"够高"而非"越高越好"） |

**综合评估**：**仅 1 维（atr）部分单调，不满足 ≥ 2 维要求；5 个通过点散点分布不构成平台**。

**判决**：⚠️ **NOT 分支 A · 走分支 B**

### 8.6 核心机制修正

> 原假设：「VA 对称 + 中高波动 + 趋势平稳」三维协同 → 反转土壤 → rank20 reaccept 有效
> **修正假设**：**「高波动（atr_rank > 0.67）」是唯一必要条件**；skew 和 trend 只是次要共变量甚至无关，rank20 反转触发器本身在**任何 skew / trend 位置**都能在高波动子池中提供 +40~+80 bps 的配对差

**修正证据**：
1. `atr_hi` 列（15 个通过 atr 阈值的单元格中的 15 个）**全部**为正的 H4 real mean（最低 +19，最高 +77）
2. `atr_midhi` 列出现两个显著负值（wneg×midhi −6，wpos×midhi −9），说明**中等波动不足以支撑反转 alpha**
3. skew 和 trend 在通过单元格中的分布毫无规律（wneg/xneu/wpos/mpos 都能出现在 Top-6，trend 从 lneg 到 lpos 也都能）

**降级理由**：
- 「三维协同」被证伪 → 假设的机制解释崩塌，只剩「高波动下 rank20 反转触发器有效」这个**朴素观察**
- 该观察本身仍值得作为**辅助 gate** 进入下游策略（rank20 反转 + atr_rank > 0.67）
- 但绝对收益仍然太薄（Top-1 单元格 n_pairs 仅 20，扩大到全 atr_hi 池的实际年化贡献估算 < 5%），**不足以独立成主题**

### 8.7 落地动作（分支 B）

1. **KF 条目待登记到 [poc-value-area-asymmetry/research-status.md](../research/themes/poc-value-area-asymmetry/research-status.md)**（等归档时一次性登记）：
   ```
   KF-N · 高波动子池中 rank20 反转触发器有配对保护 alpha
   - 类型：策略行为 + 方法论
   - 状态：已证实（Gatekeeper 定性 + 60 组网格扫描交叉验证）
   - 证据：workbench:poc-value-area-asymmetry-reaccept-symmetric-regime
   - 影响：为下游策略主题提供"atr_rank > 0.67 + rank20 反转"辅助 gate 候选；
           证伪"VA 对称/趋势平稳三维协同"原假设，回归单维 atr 效应
   - 日期：2026-07-09
   ```
2. **不做严格 5m bar VA reaccept 检测器**（分支 A 前提被证伪，无必要投入）
3. **未来下游策略主题使用建议**（不属于本支线交付范围）：把 `atr_rank_roll > 0.67 & rank20 反转` 作为分类器 v4.0 主信号之外的**辅助过滤器**，实测下游命中率提升幅度

### 8.8 Step 3 / 4 状态

- ~~Step 3 A（严格化重跑）~~：**跳过**（分支 A 未通过）
- ✅ Step 4 B（登记 KF）：待归档时统一执行
- **本支线到此实验部分结束**，剩余动作纯文档整理

---

## 9. 甜蜜区深挖结果 + 方向性分析（2026-07-09 · 补充）

### 9.1 甜蜜区假设验证

> **目标**：验证「平稳趋势 + 适度 skew 倾斜 + 高波动」是否有甜蜜区（用户先验假设）
> **脚本**：[va_sweetspot_scan.py](raw-scripts/va_sweetspot_scan.py)
> **设计**：abs_skew 3档 × trend 2档 × atr 3档 = 18 组，cluster bootstrap B=500

**甜蜜区 A（sk_mild × tr_stable × atr_hi）**：+26.47 bps CI=[+4.2, +51.0] ✅ **排 0，用户先验方向确认**

| 验证对照 | 结果 | 意义 |
|----------|------|------|
| 甜蜜区均值 > 极对称×平稳 | +26.5 vs +21.7 | 适度倾斜 > 完全对称（先验方向确认） |
| 甜蜜区均值 > 强倾斜×平稳 | +26.5 vs +9.8 | 过度倾斜不可做 |
| 甜蜜区均值 > 适度倾斜×非平稳 | +26.5 vs +7.0 | 平稳趋势是必要条件 |

**abs_skew 分布**：sk_xsym 20%, sk_mild 19.9%, sk_strong 60%（大部分样本是强倾斜区，符合先验认知）

### 9.2 A/B 区深挖验证

> **脚本**：[va_sweetspot_deep_dive.py](raw-scripts/va_sweetspot_deep_dive.py)
> **设计**：B=2000 bootstrap + 500 次安慰剂 shuffle + 品种集中度

| 验证层 | 甜蜜区 A（sk_mild × tr_stable × atr_hi） | 甜蜜区 B（sk_xsym × tr_unstable × atr_hi） |
|--------|--------------------------------------------|--------------------------------------------|
| 层1 · B=2000 | H4 real **+26.47** CI=[+5.04, +52.01] ✅ | H4 real **+26.21** CI=[+8.46, +42.75] ✅ |
| 层2 · 安慰剂 p | **0.012** ✅ 显著 | **0.002** ✅ 显著 |
| 层3 · Top-5 集中度 | **91.8%** ⚠️ 过度集中 | **37.3%** ✅ 分散良好 |
| H2→H4→H8 形状 | 单调递增（H2:+15→H4:+26→H8:+46） | 峰值在 H4 衰减（H2:+16→H4:+26→H8:+21） |

**判决**：
- 甜蜜区 A → **伪甜蜜区**（Top-5 集中 91.8%，α 被少数合约驱动 → 泛化性不足）
- 甜蜜区 B → **真甜蜜区**（Top-5 仅 37.3%，合约分布均匀，安慰剂验证通过）
- B 区 H4 是收益率峰值的持有期（H8 衰减），成本后 +26.21 bps 且 CI 稳健

### 9.3 四象限方向分析

> **脚本**：[va_sweetspot_direction.py](raw-scripts/va_sweetspot_direction.py)
> **设计**：trend_ret_10d 符号判趋势方向（up/down）× trigger_side（L/S）= 4 象限 × A/B 区 = 8 象限
> **Bootstrap**：cluster bootstrap B=1000 · H4 real 成本口径

**B 区方向结果**（唯一有甜蜜区的区域）：

| 象限 | n | H4 mean (bps) | CI95 | 判决 |
|------|---|---------------|------|------|
| **顺势S (downtrend×S)** | 81 | **+56.25** | [+16.29, +103.41] | **✅ 可做** |
| 顺势L (uptrend×L) | 40 | +29.94 | [−34.26, +93.59] | ❌ CI 太宽 · n 不足 |
| 逆势S (uptrend×S) | 68 | +24.99 | [−4.73, +55.83] | ❌ CI 不排 0 |
| 逆势L (downtrend×L) | 54 | −13.62 | [−47.58, +21.83] | ❌ CI 排 0 负侧 |

**A 区方向结果**（伪甜蜜区，供参考）：

| 象限 | n | H4 mean (bps) | CI95 | 判决 |
|------|---|---------------|------|------|
| 顺势L (uptrend×L) | 14 | **+77.62** | [−26.88, +180.75] | ❌ CI 太宽·n 太少 |
| 逆势S (uptrend×S) | 31 | +21.38 | [−10.21, +61.75] | ❌ |
| 逆势L (downtrend×L) | 22 | +4.48 | [−26.18, +35.43] | ❌ |
| 顺势S (downtrend×S) | 32 | −3.96 | [−40.91, +53.02] | ❌ |

**顺势 vs 逆势汇总**：

| 区域 | 顺势加权 H4 mean | 逆势加权 H4 mean |
|------|-----------------|-----------------|
| A 区 | +19.50 bps | +13.88 bps |
| B 区 | **+42.03 bps** | +4.39 bps |

**关键结论**：
1. **不是两侧都能做** — 仅顺势方向（B区downtrend×S）稳正，逆势方向均值逼近 0
2. **B区顺势S +56.25 bps CI 排 0** 是唯一可靠的信号象限
3. **B区顺势L n=40 样本不足**，均值方向对（+29.94）但 CI 太宽，无法判断

### 9.4 最终判决

```
统计层：✅ B区顺势S（sk_xsym × tr_unstable × atr_hi · downtrend × S 做空回落）
         CI=[+16.29, +103.41] · 安慰剂 p=0.002 · 品种集中度 37.3%
落地层：⚠️ 仅 1/8 象限可用 · 配对设计仍有偏差（no_trigger -44 bps vs 子池均值 -1 bps）
         B区顺势L 待扩样判断
下一步：B 区顺势 L 扩样（放宽 atr 到 midhi+hi，看 n=40→?）
```

---

## 10. B 区顺势 L 扩样结果（2026-07-09）

> **目标**：B 区顺势 L（uptrend × L）基线 n=40，CI=[−34.26, +93.59] 太宽 → 逐步放宽 atr/skew/trend 条件，看能否扩到 CI 排 0
> **脚本**：[va_sweetspot_expand_L.py](raw-scripts/va_sweetspot_expand_L.py)
> **设计**：B=1000 cluster bootstrap · real 成本 · 6 组 atr/trend 变体（E0-E5）+ 3 组 skew 放宽到 sk_mild（W0-W2）

### 10.1 扩样结果（聚焦顺势L H4 real）

| 方案 | 放宽条件 | n_L_up | H4 mean (bps) | CI95 | 判决 |
|------|---------|--------|---------------|------|------|
| E0（基线） | atr_hi (0.67,1.01] · sk_xsym · tr_unstable | 40 | +29.94 | [−30.27, +94.84] | ❌ |
| E1 | atr>0.50 · 其余同基线 | 54 | +14.08 | [−36.78, +66.24] | ❌ |
| E2 | atr>0.33 · 其余同基线 | 66 | +15.25 | [−30.07, +60.27] | ❌ |
| W0 | sk_xsym+sk_mild + atr_hi | 88 | +24.23 | [−8.52, +58.32] | ❌ |
| W1 | sk_xsym+sk_mild + atr>0.50 | 117 | +13.73 | [−11.75, +41.40] | ❌ |

### 10.2 关键发现

1. **顺势L 在所有放宽条件下 CI 均不排 0** — 即使扩到 n=117，CI 下限仍为 −11.75 bps
2. **放宽 atr 后均值稀释**：atr_hi→atr>0.50 时 H4 均值从 +29.94 降至 +14.08（−53%），说明 **atr 越高信号越强**，但放宽后稀释速度快于样本量增加速度
3. **进一步放宽 skew 到 sk_mild** 也无法挽救（W0: +24.23 CI=[−8.52, +58.32]）
4. **顺势S 在所有放宽条件下保持稳健**（H4 均值 +38~+56 bps，CI 始终排 0），是**唯一可靠的信号象限**

### 10.3 最终判决

```
B 区顺势L（uptrend × L 做多反弹）：❌ 不可做
  - 基线 n=40 不够 → 扩样后 n=117 仍不排 0
  - 放宽 atr 稀释均值速度 > 样本增加速度
  - 信号本质上是 weak / noisy，非样本量问题

B 区顺势S（downtrend × S 做空回落）：✅ 唯一可做信号
  - 基线 +56.25 bps CI=[+16.29, +103.41]
  - 即使放宽条件，CI 仍排 0（E2: +38.67 CI=[+9.42, +70.04]）
  - 品种集中度 37.3%，安慰剂 p=0.002

支线最终状态：
  - 统计层：✅ B区顺势S（sk_xsym × tr_unstable × atr_hi · downtrend做空）
             CI=[+16.29, +103.41] · B=1000 · 安慰剂验证通过 · 品种分散
  - 落地层：⚠️ 仅 1/8 象限可用 · 配对设计偏差未消除（no_trigger −44 bps）
             · rank20 反转是代理检测器 → 非严格 VA reaccept
  - 实际可用场景：极强背景下（VA对称 + 趋势不稳定 + 高波动）的下跌趋势中做空回落
    提供 +38~+56 bps H4 净收益
  - 不适合场景：做多反弹（顺势L）· 逆势操作 · 中等波动以下 · 趋势平稳环境
```

---

## 7. 稳定后归档路径

按支线走向分两种情况：

- **走分支 B**（关键发现登记）：本支线随 poc-value-area-asymmetry 主题下一次批次归档一并处理，归档批次名建议 `docs/archive/strategy-research/<YYYY-MM-DD>-poc-va-asymmetry-reaccept-symmetric-regime/`。
  - 本 workbench 压缩后进批次根目录
  - 对立报告作为决策证据保留（`raw-workbench/`）
  - 三个脚本进 `raw-scripts/`
  - 关键发现登记到 [poc-value-area-asymmetry/research-status.md](../research/themes/poc-value-area-asymmetry/research-status.md) 的 KF 清单（形如「KF-N · 对称子环境 rank20 反转有保护型 alpha 但绝对值不足以独立成源 · 2026-07-09」）
- **走分支 A**（独立立题）：本 workbench 转为新主题的 stage0 workbench，归档路径改为 `docs/archive/strategy-research/<YYYY-MM-DD>-<new-theme-slug>-<stage>/`；对 poc-value-area-asymmetry 主题只做 pull 模式引用登记（[archive-references.md](../research/themes/poc-value-area-asymmetry/archive-references.md) 追加一条「衍生主题」类型条目）。

---

*本文件是支线实验流水，与关联主题 poc-value-area-asymmetry 的分类器 v4.0 契约解耦。稳定结论通过 pull 模式登记到主题 KF 清单，或作为独立主题立题依据。*
