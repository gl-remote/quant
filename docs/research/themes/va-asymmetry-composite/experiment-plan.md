# va-asymmetry-composite · 实验计划

> 类型：Experiment Plan
> 版本：v0.1（立题版 · 阶段 0 未启动）
> 最近更新：2026-07-09
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](research-status.md)
> 策略数学契约：[strategy-math-spec.md](strategy-math-spec.md) v0.1

本计划验证「poc-value-area-asymmetry 分类器 + 塑形 + 组合优化 → 可实盘完整策略」
的命题。按五阶段进行，任一阶段 gatekeeper fail，则冻结主题或跳过该方向。

## 0. 全局设定（所有阶段共用）

### 0.1 数据

| 数据 | 来源 | 说明 |
|:---|:---|:---|
| 分类器 timeline | `project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet` | 143 合约 · 36625 events · 含 3 维 rank + tier |
| 合约规格 | `workspace/common/contract_specs.py` | 乘数 / tick_size / slip_tick / 佣金率 |
| Symbol 工具 | `workspace/common/symbol_utils.py` | 品种前缀 · 合约解析 |
| 市场数据（可选） | `project_data/market_data/csv/*.tqsdk.5m.csv` | 阶段 0 复现不需要，阶段 3+ Walk-Forward 用 |

**时间范围**：分类器 timeline 覆盖的全部区间（通常 2023-09 ~ 2026-06，以实际数据为准）。
**合约范围**：timeline.parquet 中出现的 143 合约（20 品种前缀）。

### 0.2 模拟时钟 & 执行

- 交易时钟：1h bar close（与分类器同频）
- 成交价：entry = `close_t`（理论），exit = 目标价 / close（SL/TIME）
- 工程化阶段（阶段 4）：切换为 `open_{t+1}` + 滑点，并与 vnpy BacktestEngine 交叉验证
- 持仓并发：允许多品种并发；单合约 8h dedup；总名义 ≤ 100% 权益（§7.2 压仓）

### 0.3 成本（硬约束）

- **默认**：realistic-cost（`contract_specs.py` × ATR 倍率校验）
- **Debug 用**：扁平 ATR 成本（`--flat-cost-debug`，显式命名，默认关闭）
- 所有最终判据必用 realistic-cost

### 0.4 统计判据（跨阶段通用模板）

| 判据层 | 说明 | 方法 |
|:---|:---|:---|
| 净夏普 / 年化收益 | 策略层面 | 日度权益曲线（按 trade-level 聚合） |
| MaxDD | 策略层面 | 日度权益曲线最大回撤 |
| Paired 显著性 | 方案 vs baseline | 同一批 event 配对 diff 的 date-cluster bootstrap |
| ν_implied | 是否真 alpha | strategy-math-spec.md §9 式（μ − σ²/2 > 0） |
| 品种保留率 | 泛化性 | (单品种正收益的品种数) / (总参与品种数) · 按 A/B/C 类分组报告 |
| 参数平台宽度 | 过拟合防护 | 最优 vs 次优方案净夏普差 < 30% 判为"平台"（稳），> 50% 判"尖峰"（过拟合风险） |
| Bonferroni 校正 | 多重比较 | 阶段 0 family=1 · 阶段 1 family=9（3 方向 × 3 候选，不含 baseline）· 阶段 2 family=通过数的组合数 |

### 0.5 对照基线（每阶段必跑）

- **B0 · 等权全品种 5 档（塑形基线）**：5 档保留 × S1 全品种 × W0 等权 × VW0 多空等权 → 直接对应 archive:2026-07-09-poc-va-shaping 的最优口径，所有方案必须与 B0 做 paired 对照

---

## 阶段 0 · 立题复现（Gatekeeper 1 · ✅ 通过后才可阶段 1）

### 0.1 目标

复现 archive:2026-07-09-poc-va-shaping 的起点口径，确认数据链完整。
**无搜索自由度**（只跑 1 个方案：B0）。

### 0.2 运行配置（1 个）

```
方案 = B0
  品种筛选 = S1（全品种 5 档）
  强度加权 = W0（等权）
  多空权重 = VW0（等权）
  塑形 = 基线（多头 SL1.0·8h · 空头 SL2.5·10h · No Trailing · No TP）
  风控 = 2% 单笔 · 100% 名义（FIFO 压仓）
```

### 0.3 Gatekeeper 判据（阶段 0 通过条件）

| 指标 | 阈值 | 对应 archive 口径 |
|:---|:---:|:---|
| 年化净收益（B0） | ≥ 12% | archive 年化 15.45%（允许压缩后掉 22%） |
| 净夏普（B0） | ≥ 1.8 | archive Sharpe 2.23（允许掉 19%） |
| MaxDD（B0） | ≤ 10% | archive MaxDD −7.51%（允许放宽 33%） |
| 月度胜率 | ≥ 70% | archive 83%（允许掉 16pp） |
| 单笔 IR | ≥ 0.25 | archive 0.30（允许掉 17%） |

**全部通过 → 阶段 1；任一 fail → 诊断**：
- 若差异来自分类器版本（v4.0 vs archive 用的过渡版）：微调分类器字段映射
- 若差异来自成本口径（realistic-cost 更严）：检查 contract_specs 映射
- 若差异来自名义暴露压缩（archive 日均 653% vs 本主题 100%）：做暴露敏感性三档（§0.4 缓解项）

### 0.4 阶段 0 输出

- workbench：`docs/workbench/va-asymmetry-composite-stage0-baseline.md`
- 数据：`project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet`（按 strategy-math-spec.md §10 字段）
- 诊断：B0 与 archive 的逐指标对比表 + 差异归因

---

## 阶段 1 · 三大方向 Gatekeeper 独立扫描（✅ 每方向独立 ≥ 0.2 夏普增量 → 阶段 2）

### 1.0 总设计

每个方向独立跑 2-3 个候选（不含 baseline），每方向只跑自己的自由度，
其余方向全锁 baseline（S1 × W0 × VW0）。
合计运行数 = 1 (B0) + 1 (S2) + 3 (W1/W2/W3) + 2 (VW1/VW2) = **7 个配置**
（Bonferroni family=6，α=0.05/6=0.0083）。

### 1.1 C.1 · 品种筛选（2 配置）

| ID | 配置 · 其余固定为 S1/W0/VW0 | 判据（vs B0 paired） |
|:---:|:---|:---|
| B0 | S1 全品种 5 档 | — （baseline） |
| **S2** | A/B/C 三类 tier 映射（strategy-math-spec.md §4.1） | ✅ 通过条件：净夏普增量 ≥ 0.2 · p_boot ≤ 0.0083 · ν_implied > 0 |

**若 S2 通过**：后续阶段默认品种方案 = S2；**若 fail**：跳过品种筛选，全阶段固定 S1。

**补验项（S2 是否通过都要跑）· L_seg2_low_flat × C 类农产品**：
- 仅对 C 类 16 品种启用 L_seg2_low_flat
- 对比「C 类启用 vs 不启用」C 类的净 PnL diff
- 若 mean_C_diff > 0 且 p ≤ 0.05 → C 类白名单追加 L_seg2_low_flat

### 1.2 C.2 · 信号强度加权（4 配置）

| ID | 配置 · 其余固定为 阶段1 胜出的 S* / VW0 | 判据（vs 阶段1 C.1 胜出方案 paired） |
|:---:|:---|:---|
| W0 | 等权 | — （对照 baseline） |
| W1 | Skew 距离（strategy-math-spec.md §5.1 W1） | ✅ 通过：净夏普增量 ≥ 0.2 · p_boot ≤ 0.0083 |
| W2 | ATR 匹配（strategy-math-spec.md §5.1 W2） | 同上 |
| **W3** | 三维乘积（strategy-math-spec.md §5.1 W3）· 默认 | ✅ 通过：净夏普增量 ≥ 0.2 · p_boot ≤ 0.0083 |

取 W1/W2/W3 中的**最优**（若多个都通过，用净夏普最高的）。
若最优 vs W0 增量 < 0.2 → 该方向跳过，固定 W0。

### 1.3 C.3 · 多空权重（3 配置）

| ID | 配置 · 其余固定为 阶段1 C.1 胜出 S* × C.2 胜出 W* | 判据（vs C.1+C.2 基线 paired） |
|:---:|:---|:---|
| VW0 | 多空等权 1:1 | — （对照 baseline） |
| **VW1** | IR 比例（strategy-math-spec.md §5.2 VW1）· 默认 | ✅ 通过：净夏普增量 ≥ 0.2 · p_boot ≤ 0.0083 |
| VW2 | 频率平衡（strategy-math-spec.md §5.2 VW2） | ✅ 通过：净夏普增量 ≥ 0.2 · p_boot ≤ 0.0083 |

取 VW1/VW2 中的最优。若最优 vs VW0 增量 < 0.2 → 该方向跳过，固定 VW0。

### 1.4 阶段 1 汇总判决

| 场景 | 后续动作 |
|:---|:---|
| ≥ 2 个方向独立通过（增量 ≥ 0.2） | ✅ 进入阶段 2，联合搜索 |
| 1 个方向通过 | 追加阶段 1.5：只对该方向做 3 档平台宽度检查（±30%），若平台宽度 OK → 阶段 2 其余 2 方向 baseline + 该方向最优；否则回退 B0 + 尝试单方向 |
| 0 个方向通过 | ⚠️ 判定：alpha 已被 B0 吃满，组合层无增量 → 主题降级为「B0 直接工程化」，跳过阶段 2-3 进入阶段 4（但需降低预期：夏普 ~2.0），或主题冻结 |

### 1.5 阶段 1 输出

- workbench：`docs/workbench/va-asymmetry-composite-stage1-gatekeepers.md`
- 数据：`project_data/ai_tmp/va_composite_stage1_*.trades.parquet`（每配置一份）
- 汇总表：7 配置 × 12 指标矩阵（夏普 / 年化 / MaxDD / 月度胜率 / 品种保留率 / ν_implied / p_boot / w_strength 分布 / 多空贡献度 / 压仓比例 / 成本 ATR 倍率 / 交易数）
- 每方向 vs baseline 的 paired CI 与 bootstrap p 值

---

## 阶段 2 · 最优组合搜索（✅ 夏普 ≥ 2.5 且 年化 ≥ 18% → 阶段 3）

### 2.1 搜索空间

设阶段 1 通过了 N 个方向（N = 1 / 2 / 3）：

| 场景 | 搜索空间 | 配置数 |
|:---|:---|:---:|
| N=3（3 方向都通过） | C.1 × C.2 × C.3 = （S1/S2）×（W0/W最优/W次优）×（VW0/VW最优/VW次优）· 其中 baseline + 每方向加入次优（若次优增量 ≥ 0.15） | 2×3×3=18（若都有次优）或更小 |
| N=2（2 方向通过） | 仅在通过的 2 方向上做 3×3（含 baseline + 2 档平台），第 3 方向固定阶段 1 的 baseline | 9 |
| N=1（1 方向通过） | 单方向 3 档平台（最优 ±30%）：例如 W3 的 clamp 下限 [0.1/0.2/0.3] × 斜率乘数 [0.8/1.0/1.2] | 9 |

**Bonferroni 搜索空间封顶 27 配置**（超过时砍去「次优 + 平台外沿」组合）。

### 2.2 三大额外检查（每配置必做）

**检查 A · 参数平台宽度**：
- Top-5 配置的净夏普极差 / Top-1 净夏普 ≤ 30% → 平台 OK
- 若极差 > 50% → 过拟合风险标记，需要更多样本外容错（阶段 3 阈值放宽）

**检查 B · 反事实随机对照（structural-shaping-alpha KF-1 / value-area 家族反例）**：
- 对最优方案做 20 次 dirandom 方向随机（分类器 tier 不变，方向以 50%/50% 随机翻转）
- 最优方案净夏普 > 95% 分位 dirandom → 通过（不是方向运气）

**检查 C · ν_implied 分层检查**：
- 按 tier × 品种类型分层报告 ν_implied
- ≥ 70% 层级 ν_implied > 0 且 p(ν>0) ≥ 0.90 → 通过（不是某一 tier/类型单独撑）

### 2.3 Gatekeeper 判据

| 指标 | 阈值 | 说明 |
|:---|:---:|:---|
| 最优方案净夏普 | ≥ **2.5** | 相对 B0 增量 ≥ 0.7 |
| 最优方案年化净收益 | ≥ **18%** | |
| 最优方案 MaxDD | ≤ **8%** | 优于 B0 的 10% |
| Top-5 夏普极差 / Top-1 | ≤ 30% | 平台宽度 OK（防尖峰） |
| 反事实 dirandom 分位 | ≥ 95% | 不是方向运气 |
| ν_implied 分层通过率 | ≥ 70% tiers | 不是单 tier 撑 |
| 品种保留率（A/B/C 类分别） | ≥ 70% | 泛化 OK |

**全部通过 → 阶段 3；否则**：
- 放宽搜索空间（加入未通过方向的 baseline 版本）
- 仍不行 → 阶段降级，以 B0 + 单方向最优 进入阶段 4（夏普预期 ~2.0）

### 2.4 塑形平台敏感性检查（阶段 2 末尾 · 必做，不计入搜索空间）

在最优组合方案上单独微调塑形参数 ±30%（不计入多重比较）：

| 参数 | 基线 | Low | Mid | High |
|:---|:---:|:---:|:---:|:---:|
| K_L^SL（多头 SL 倍数） | 1.0 | 0.7 | 1.0 | 1.3 |
| H_L（多头持仓期 h） | 8 | 6 | 8 | 10 |
| K_S^SL（空头 SL 倍数） | 2.5 | 2.0 | 2.5 | 3.0 |
| H_S（空头持仓期 h） | 10 | 8 | 10 | 12 |

3^4 = 81 配置只做**描述性**（不做 gatekeeper），输出参数热力图，
确认「最优塑形在平台内」（若最优方案恰好处于平台外沿 → 警告：塑形可能欠优）。

### 2.5 阶段 2 输出

- workbench：`docs/workbench/va-asymmetry-composite-stage2-combination-search.md`
- 数据：`project_data/ai_tmp/va_composite_stage2_*.trades.parquet`（每配置一份）
- 汇总：搜索空间结果矩阵 + 平台热力图 + dirandom 分布 + ν_implied 分层表
- **策略 v1.0 参数表**（供 strategy-math-spec.md v1.0 冻结）：最优方案的 S/W/VW 配置 + 塑形参数最终值

---

## 阶段 3 · 样本外双维度验证（✅ 双维度都通过才可实盘）

### 3.1 品种维度 OOS（Leave-Group-Out · LGO）

按 A/B/C 三类品种做 3-fold：

| Fold | 训练组（开发/调参） | 验证组（测试） |
|:---|:---|:---|
| 1 | A + B | C（农产品有色主流） |
| 2 | A + C | B（化工建材黑色） |
| 3 | B + C | A（金融贵金属） |

**训练流程**：每 fold 用训练组数据跑阶段 2 的完整流程 → 得到该 fold 的最优方案
（品种映射 / 权重公式 / 多空比），再在验证组上零调参跑一遍。

### 3.2 时间维度 OOS（Time Split · TS）

按日历时间前 60% / 后 40% 切分：

| Split | 训练组 | 验证组 | 说明 |
|:---|:---|:---|:---|
| TS | 前 60% 日期 | 后 40% 日期 | 若 timeline 覆盖 ~33 个月，则训练 ~20 个月，验证 ~13 个月 |

**训练流程同 LGO**：训练组跑阶段 2 全流程 → 验证组零调参。

### 3.3 Gatekeeper 判据（硬）

| 判据 | 品种 LGO（3-fold 平均） | 时间 TS |
|:---|:---:|:---:|
| 验证组正收益品种占比 | ≥ **60%**（每 fold 单独 ≥ 50%） | — |
| 验证组净夏普劣化幅度 | ≤ 25%（训练夏普 × 0.75 ≤ 验证夏普） | ≤ 25% |
| 验证组年化净收益 | ≥ 10% | ≥ 10% |
| 验证组 MaxDD | ≤ 12% | ≤ 12% |
| ν_implied（验证组） | > 0 · p ≥ 0.90（fold 间 ≥ 2/3 通过） | > 0 · p ≥ 0.90 |

**双维度都通过 → 阶段 4（工程化）**
**仅一维通过**：在该维度上分析塌陷原因（制度变化？品种类型漂移？），
若原因明确且可做 filter → 追加 filter 后重返阶段 3；否则主题降级为「样本内 OK，
实盘谨慎」，仅进模拟盘。
**双维度都 fail**：主题冻结（或降级为白皮书，不做实盘）。

### 3.4 阶段 3 输出

- workbench：`docs/workbench/va-asymmetry-composite-stage3-oos-validation.md`
- 数据：`project_data/ai_tmp/va_composite_stage3_*`（fold 与 split 分开）
- 汇总：LGO 3-fold 表 + TS 前后段对比表 + 每 fold/split 的 ν_implied 分层 + 塌陷归因（若 fail）
- **策略参数表 v1.1**：若某 fold/split 需要追加制度 filter → 并入最终参数；否则直接沿用阶段 2 v1.0 参数冻结

---

## 阶段 4 · 工程化与模拟盘设计（✅ 代码化 + vnpy 交叉验证 + 报表）

### 4.1 实现内容

1. **策略类**：`workspace/strategies/va_asymmetry_composite.py`
   - 继承 vnpy BacktestEngine 接口（或项目内部 Strategy 基类）
   - 按 strategy-math-spec.md v1.0 实现 classifier 判定 + 塑形 + 压仓
   - 分类器调用：`workspace/strategies/classifiers/poc_va.py`（已在 poc-value-area-asymmetry 阶段 4 提取）

2. **回测 Runner**：支持 CLI `uv run python ... --strategy va_asymmetry_composite --start ... --end ...`
   - 输出 trade_clearings parquet（§10 字段）+ 权益曲线 + 风控报表
   - 内置：realistic-cost、date-cluster bootstrap、ν_implied 分层归因

3. **交叉验证**：用项目内部的向量化模拟（阶段 0-3 用）与 vnpy BacktestEngine 各跑一份，
   对 trade-level PnL 差异 < 1bp（99% 交易上）视为通过

4. **模拟盘报表模板**：
   - 日度：权益曲线 / 持仓明细 / 暴露度 / 压仓比 / 成本 ATR 倍率
   - 月度：收益归因（按 tier / 品种类型 / 多空）· 品种保留率滚动更新
   - 季度：OOS 更新检查（滚动 Walk-Forward · 与阶段 3 TS 对齐）

### 4.2 阶段 4 输出

- 代码：`workspace/strategies/va_asymmetry_composite.py` + 对应 runner
- 文档：`implementation-notes.md` 从占位版 → 完整版（数据结构 / 缓存 / 性能 / 桥接）
- 文档：`parameter-selection-spec.md` 从占位版 → 完整版（分层 / 判据 / 回填格式）
- 文档：`strategy-math-spec.md` v0.1 → **v1.0（冻结）**
- workbench：`docs/workbench/va-asymmetry-composite-stage4-engineering.md`
- 归档准备：代码 + workbench 在分支完成后，按 quant-research-layout 的归档原子步骤归档到 `docs/archive/strategy-research/<YYYY-MM-DD>-va-asymmetry-composite-<阶段名>/`

---

## 时间线（节点）

| 阶段 | 估计启动 | 工作量 |
|:---|:---|:---|
| 阶段 0 · 立题复现 | 立题后立即 | 几小时 |
| 阶段 1 · 三大方向 Gatekeeper | 阶段 0 通过次日 | 半天 ~ 1 天 |
| 阶段 2 · 最优组合搜索 | 阶段 1 通过次日 | 1 ~ 2 天 |
| 阶段 3 · OOS 双维度 | 阶段 2 通过次日 | 半天 |
| 阶段 4 · 工程化 | 阶段 3 通过次日 | 2 ~ 3 天 |

**任一阶段 gatekeeper fail，按该阶段「否则」分支处理**（跳过 / 降级 / 冻结），
不硬推进。
