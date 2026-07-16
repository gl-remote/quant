# strength-factor-screening · 实验计划

> 类型：Research / 实验矩阵
> 状态：v0.1 · 2026-07-16 立题
> 上游：shaping-theory §2.22.7（候选清单）· §5.5（阶段 2d 待启动路径）
> 依赖文档：screening-methodology.md v0.5（筛选流程 · 判据 · 边界）

## 1. 实验目标

按 `screening-methodology.md` §四 十步流程，逐一验证"能识别 $|\nu|/\sigma$ 强段"的候选因子。
每一个候选先通过**六个工程边界 gate** + **十步流程**再判 accept / reject。

**首战目标**：找到至少 1 个玉米 1h 上的 accept 因子，作为下游子主题（OOS / 跨品种 / 实盘）的种子。

## 2. 候选强度识别信号总清单

来源：shaping-theory §2.22.7 + §5.5，加上主题方法论分类补充：

| # | 因子家族 | 具体候选 | 视角 | 首战数据 |
|---|---|---|---|---|
| **F1** | 波动率制度切换 | ATR 拐点（20 bar EMA 上穿下穿）| B（回归器）| 已有 ATR 数据 |
| **F2** | 波动率制度切换 | GARCH regime state（HMM 2-state）| A（分类器）| 需拟合 |
| **F3** | 波动率制度切换 | Realized volatility 突破 $N \cdot \sigma$（N=1.5/2.0）| A（分类器）| 已有价格 |
| **F4** | 结构突破 | 关键位破位（Donchian 20 bar）+ 量价背离 | A（分类器）| 已有价量 |
| **F5** | 结构突破 | Hurst 指数窗口 $H_{60} > 0.60$ | B（回归器）| `research.hurst` |
| **F6** | 结构突破 | ATR·Hurst 融合（$H \cdot \text{ATR}$ 归一）| B（回归器）| `research.hurst` |
| **F7** | 板块共振 | 同板块 $\ge 3$ 品种同向 aligned（前 60min）| A（分类器）| 需 5+ 品种数据 |
| **F8** | 板块共振 | 板块 |ν|/σ 加权均值 $\ge$ 阈值 | B（回归器）| 需 5+ 品种数据 |
| **F9** | 事件驱动 | 宏观数据发布后 30/60/120 min flag | A（分类器）| 需 econ calendar |
| **F10** | 事件驱动 | 库存报告 / OPEC / 政策事件 flag | A（分类器）| 需事件库 |
| **F11** | 单一窗口回归 · **理论证伪对照** | 20h 窗口直接回归 $\|\nu\|/\sigma$ | B（回归器）| 已有价格 |
| **F12** | 事前融合 | F1 + F5 + F7 加权融合 | B（回归器）| 组合信号 |

**说明**：F11 是"预期失败"的对照——shaping-theory §2.23.5.5 已证明 20h 窗口回归 $se \approx 0.224$，
远超 $se_{\text{target}} \approx 0.047$，Gate 1 必挂。**列入实验清单是为了主动跑一次，
把它作为"证伪已完成"的登记档案**，供后续 AI 或研究者查证。

## 3. 首战优先级

**首战策略**：**广度优先，先跑简单单信号，再上组合**。
一次开跑 3–5 个候选，任一 accept 立即启动下游 OOS；全部 reject 则复盘归因，
决定"回炉换识别路径" or "结论层报告：玉米 1h 通道 B 无 accept 因子"。

### Wave 1（本轮 · 单信号）

| 优先级 | 候选 | 视角 | 预期结论 | 立项目的 |
|---|---|---|---|---|
| ⭐⭐⭐ | **F5** Hurst 窗口 | B | 边缘（$se \approx 0.05$）| 最直接对齐 §2.12.4 实测 |
| ⭐⭐⭐ | **F3** Realized vol 突破 | A | 命中率 60–70% · 边缘 | 传统波动率突破的强度识别效力 |
| ⭐⭐ | **F1** ATR 拐点 | B | $se$ 高、可能失败 | 单指标波动率的粗糙度上限验证 |
| ⭐ | **F11** 窗口回归 | B | 必失败（对照）| 归档 shaping-theory §2.23.5.5 证伪 |

**共通实验参数**：

- 品种 · 玉米 (`DCE.c2601` / `c2603` / `c2605`）
- 周期 · 1h
- 成本 · $c_{\text{side}} = 0.077$ ATR
- 塑形容器 · $K_S^\ast = 3.0$、$K_T^\ast = 9.0$、$\tau^\ast = 0.647$（KF-27 反解 · 由 `research.optimizer` 自动生成，不硬编码）
- 评估集 · 3 合约合并、去掉首尾 $W=20$ bar
- Bootstrap · $B_{\text{boot}} = 5000$、cluster = (symbol, contract)、seed = 42

**产出**：每个候选一份 `docs/workbench/strength-factor-screening/candidate-<slug>.md`，
含 Step 0–10 全部登记内容。

### Wave 2（Wave 1 后 · 组合与跨品种）

Wave 1 有 accept → 启动 Wave 2；全部 reject → 复盘归因决定是否启动。

| 优先级 | 候选 | 视角 | 触发条件 |
|---|---|---|---|
| ⭐⭐⭐ | **F12** F1+F5+F7 融合（如果 F5 边缘）| B | Wave 1 有 ≥ 1 个边缘（$se \approx se_{\text{target}}$）|
| ⭐⭐ | **F7** 板块共振 | A | 需先拉齐同板块 5+ 品种数据 |
| ⭐⭐ | **F4** Donchian + 量价背离 | A | Wave 1 F3 accept 时才优先 |
| ⭐ | **F9/F10** 事件驱动 | A | 事件库准备到位 |

### Wave 3（Wave 1/2 accept → 跨品种扩展）

用板块预估表（shaping-theory §2.23.6.5）挑同一板块相似 $se_{\text{target}}$ 的品种：

- 农产品同类：豆粕 / 豆油 / 棕榈油（$se_{\text{target}} \approx 0.045$）
- 黑色系：螺纹 / 铁矿（$se_{\text{target}} \approx 0.054$）
- 有色：铜 / 铝（$se_{\text{target}} \approx 0.033$）

**跨品种规则**：Wave 1/2 accept 的因子在新品种上必须**独立完整跑一遍** Step 0–10，
不允许"直接套用玉米 1h 阈值"。

## 4. 每个候选的实验执行清单

按 methodology §四 Step 0–10：

- [ ] **Step 0** · 立项登记（workbench 候选卡）
- [ ] **Step 1** · 参数准备（KF-27 反解 + $x_{\min}$ / $se_{\text{target}}$）
- [ ] **§五 边界 gate** · $K_S$ 下限 / $T/T^\ast$ / $\sigma_D \pm 30\%$
- [ ] **§六 视角选择** · A / B 明确登记（禁止后改）
- [ ] **Step 2** · Gate 0 · `verify_causality_by_truncation`
- [ ] **Step 3** · 真值构造（$W = 20$，1h）
- [ ] **Step 4** · Gate 1 · 视角 A 命中率 / 视角 B se 精度（含 bootstrap 严格版）
- [ ] **Step 5** · Gate 2 · 覆盖率 $N_{\text{year}} \ge 0.70 \cdot N_{\text{year}}^\ast$
- [ ] **Step 6** · Gate 3 · Spearman r（视角 B 才有）
- [ ] **Step 7** · 终审 `run_screening()`
- [ ] **Step 8** · 反模式清单人工复查
- [ ] **Step 9** · 方向偏向审计
- [ ] **Step 10** · accept 后写入 `research-status.md` KF 清单

## 5. 反例登记规则

任何 reject 的因子必须写入 `docs/workbench/strength-factor-screening/rejected_factors.md`，
按 methodology Step 7 的四种情形分类：

- Gate 0 失败 · 因果性泄漏（附泄漏样本 index）
- Gate 1 失败 · SE 不达标（附 $\widehat{se}$ 与 $se_{\text{target}}$ 差距）
- Gate 2 失败 · 覆盖率过低（附 $N_{\text{year}}$ 与 ratio）
- Gate 3 失败 · 秩相关过低（附 $\widehat{r}$ · 打"精度好但方向错"标签）
- 方向审计失败 · 转投通道 A（附 bias 标签）

一年 review 一次反例池，观察是否有共通失败模式（如"某类因子普遍在 Gate 3 挂 → 说明真值窗口 W 选择有问题"）。

## 6. 里程碑

| 里程碑 | 判据 | 后续动作 |
|---|---|---|
| M1 · Wave 1 完整跑通 | 4 候选各产出一份 workbench 候选卡 | 汇总归因，判断进 M2 or 复盘 |
| M2 · 首个 accept 因子 | 任一候选通过 Step 0–10 | 启 Wave 2 + 启 OOS 子主题 |
| M3 · OOS 稳定 | accept 因子在 2/3 OOS 窗口 $\widehat{se} \le 1.2 \cdot se_{\text{target}}$ | 启跨品种扩展 |
| M4 · 跨品种可复现 | 至少 2 品种独立通过 Step 0–10 | 交付下游工程主题 |
| M5 · 全部 Wave 1 reject 归零 | 若 M1 无 accept、复盘无出路 | 主题归档反例登记，报告结论 |

## 7. 与其他主题的接口

- **上游**：`theme:structural-shaping-alpha` · 提供 $(\mu_D, \sigma_D)$ / 塑形容器 / $x_{\min}$ / $se_{\text{target}}$
- **下游**：暂无（本主题的 accept 是终点，直接进入策略工程）
- **横向**：若 Wave 2 F9/F10 需要事件库，可能新建 `event-catalog` 主题

## 8. 版本变更

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-07-16 | v0.1 | 首发 · 12 候选清单 + Wave 1-3 优先级 + 里程碑 M1-M5 |
