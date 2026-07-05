# 阶段 1 · 方向信息（Gatekeeper）· 实验报告

> 类型：Stage Report
> 状态：已完成
> 创建时间：2026-07-05
> 完成时间：2026-07-05
> 关联计划：[value-area-rolling-reacceptance-experiment-plan.md](value-area-rolling-reacceptance-experiment-plan.md#阶段-1方向信息成本最低gatekeeper)
> 关联主题：[../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md](../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md)

## 1. 目标

验证"价格从 VA 外侧穿回内侧后，是否有向 POC 的方向 edge"，并识别生效
品种子集与生效边界特征（板块 / 波动率 / 成交量）。

fixed-window 在 jump-process 假设下是最差近似（见主题 README §8），本
阶段结论仅作 gatekeeper：判断"信号是否存在"，不判"信号强度"。

## 2. 实验设置

### 2.1 品种矩阵

现有 `project_data/market_data/csv/` 已覆盖 5 板块 15+ 商品期货品种，
无需额外拉数据。股指期货（CFFEX）当前未接入，本阶段不涵盖，后续如
纳入策略适用范围再补。

| 板块 | 品种 | 合约（5m CSV 已有）|
|------|------|-----------------|
| 黑色 | rb / i / hc / FG | rb 2410/2501/2505, i 2509/2601, hc 2505/2510, FG 2509/2601 |
| 有色 | cu / al / ag / au | cu 2509/2601, al 2509/2601, ag 2509/2601, au 2508/2512 |
| 能化 | sc / TA / MA / OI | sc 2509/2512, TA 2509/2601, MA 2509/2601, OI 2509/2601 |
| 农产品（DCE） | m / p / y / c / cs | m 2501/2505/2601, p 2501/2505/2601, y 2509/2601, c 2601/2603/2605, cs 2601/2603/2605 |
| 农产品（CZCE） | SR / CF / RM | SR 2501/2505/2509/2601, CF 2509/2601, RM 2509/2601 |

### 2.2 数据口径

- 周期：5m
- VA/POC 计算：**前一交易日全日 5m bar** volume profile（fixed-window，
  ratio=0.7）
- 时间窗口：**每合约全部可用数据**
- Volume profile 模式：close-based（每根 bar 的 close 落入对应桶）

### 2.3 事件定义

价格从 VA 外侧穿回内侧的 **bar close** 事件（不看 intra-bar）：

- Reaccept_L：`close_{t-1} <= VAL - 1_tick ∧ close_t >= VAL`
- Reaccept_U：`close_{t-1} >= VAH + 1_tick ∧ close_t <= VAH`

事件时点 `t` 即为"结构入场时点"，方向指向 POC。

### 2.4 观察窗口

事件后 N ∈ {5, 10, 20, 40} bar 内价格是否向 POC 方向移动：

- 指标 1：`reach_rate(N)` — N bar 内 close 至少一次触及 POC 的比例
- 指标 2：`directional_bias(N)` — 事件后 N bar close 均值相对入场价的
  归一化位移（往 POC 方向为正）
- 指标 3：`win_rate(N)` — N bar 内先触 POC（win）还是先穿越对侧 VA
  边界（loss）的胜率

### 2.5 随机基准对照

- **same-direction 基准**：在同一 bar 集合上随机采样入场时点，方向与
  结构入场方向一致
- **random-direction 基准**：在同一 bar 集合上随机采样入场时点，方向
  随机
- **distance-matched 基准（v2 新增）**：对每个结构事件，找同品种、同
  方向、距 POC 距离 ± 3 ticks 内 的候选 bar，随机抽一个作为对照。这
  样排除"结构入场时点天然离 POC 近"的干扰，隔离出 VA reacceptance 结
  构相对 POC 天然吸引力的**独立贡献**。
- 每个基准 seeds ∈ {1..10} 求均值 + 标准差

### 2.6 判据

**双 verdict 体系**：

- `verdict`（相对 same_direction）：结构入场是否优于随机同方向入场。
  受 POC 天然吸引力污染，只能作为初步观察
- `verdict_vs_distance`（相对 distance_matched）：结构 edge 中排除
  POC 距离效应后**残留的结构价值**。这是判断"VA reacceptance 是否有
  独立信息"的核心指标

分档：
- `beyond_poc`：Δstr-dist 在 4 个 N 中 ≥ 3 个为正 & 至少一个 ≥ 0.03
- `marginal`：仅方向对但幅度不达标
- `no_edge_beyond_poc`：与 distance_matched 持平或劣

## 3. 执行状态

- [x] 数据到位（`project_data/market_data/csv/` 已覆盖 5 板块 20 品种约 60 合约）
- [x] 分析脚本开发 [rolling_reacceptance_stage1_direction.py](../../scripts/analysis/rolling_reacceptance_stage1_direction.py)
- [x] DCE.m2601 smoke test 通过
- [x] 全品种批量跑（70 合约）
- [x] 结果汇总 + 生效边界分析

原始结果输出：
- [stage1_direction_report.md](../../project_data/analysis/rolling_reacceptance_stage1/stage1_direction_report.md)
- [stage1_direction_report.json](../../project_data/analysis/rolling_reacceptance_stage1/stage1_direction_report.json)

## 4. 板块聚合结果（双基准）

事件加权平均 reach_rate @ N=20：

| 板块 | 合约数 | 事件 | 结构 | same | random | dist_match | Δ相对same | Δ相对distance |
|------|-------|------|------|------|--------|-----------|-----------|--------------|
| black | 15 | 1169 | 0.629 | 0.539 | 0.547 | **0.601** | +0.090 | **+0.028** |
| energy_chem | 8 | 952 | 0.578 | 0.525 | 0.566 | 0.551 | +0.053 | +0.027 |
| **metals** | 8 | 1011 | 0.522 | 0.522 | 0.536 | **0.467** | +0.000 | **+0.055** |
| agri_czce | 13 | 1184 | 0.576 | 0.567 | 0.556 | 0.547 | +0.009 | **+0.029** |
| agri_dce | 26 | 1967 | 0.546 | 0.539 | 0.559 | 0.536 | +0.007 | +0.010 |

### 4.1 关键发现：POC 吸引力占主导

用户观察成立且被数据证实：**POC 本身的价值回归属性比 VA reacceptance
结构 edge 更显著**。

以 **black 板块**为例分解 0.629 的到达率：

| 成分 | 数值 | 归因 |
|------|------|------|
| 完全随机基准（random_dir） | 0.547 | POC 的**天然回归属性**（在同品种的任意时点） |
| distance-matched baseline | 0.601 | POC 吸引力 + **"离 POC 近"的位置优势** |
| 结构入场 | 0.629 | 上述两者 + **VA reacceptance 独立结构 edge** |

三部分量级：
- POC 天然回归：**~0.547**（占绝对大头）
- "位置靠近 POC"的加成：+0.054
- **VA reacceptance 独立贡献：+0.028**（真正的结构 edge）

**结论**：之前 vs same_direction 显示的 +0.090 中，**约 2/3 来自 POC
距离效应**（结构入场时点天然离 POC 近），**只有约 1/3 是真正的结构价值**。

### 4.2 板块画像重构

用 distance-matched baseline 修正后，板块排名彻底变化：

| 板块 | 旧判定（vs same） | 新判定（vs distance） | 备注 |
|------|-----------------|--------------------|------|
| **metals** | 无信号 (+0.000) | **最强 (+0.055)** | 之前被 POC 距离效应完全掩盖 |
| agri_czce | 弱 (+0.009) | 中 (+0.029) | 之前判无信号，其实有边际 edge |
| **black** | 强 (+0.090) | **弱-中 (+0.028)** | 表观最强 → 实为距离效应主导 |
| energy_chem | 中 (+0.053) | 中 (+0.027) | 一半是距离效应 |
| agri_dce | 弱 (+0.007) | 弱 (+0.010) | 两个视角都弱 |

**为什么 metals 反转**：SHFE.au 平均距 POC 154 ticks（黄金 tick=0.02），
距离远处的到达率极低（distance_matched 0.388）；reacceptance 事件
后到达率抬高到 0.474，**相对提升 +0.086 是 distance 场景下的巨大改善**，
但因为绝对值仍低于 same_direction（0.510），被"平均到 POC 的距离"这
个变量掩盖了。metals 的真正 edge 是"reacceptance 让远距离入场也能
到 POC"，是**关于距离-到达率函数形状的改变**，而不是简单的 baseline 抬升。

## 5. 逐合约 verdict 分布

判定标准：n_events ≥ 30 且 Δ(struct-same) 在 4 个 N 中 ≥ 3 个为正 & 至少
一个 N 上 Δ ≥ 0.03 → `signal`；仅方向对但幅度不达标 → `weak`；否则
`no_signal`；样本不足 → `insufficient`。

| 板块 | signal | weak | no_signal | insufficient | 总数 |
|------|--------|------|-----------|--------------|-----|
| black | 8 | 0 | 6 | 1 | 15 |
| metals | 4 | 0 | 4 | 0 | 8 |
| energy_chem | 3 | 0 | 5 | 0 | 8 |
| agri_dce | 5 | 0 | 21 | 0 | 26 |
| agri_czce | 0 | 0 | 13 | 0 | 13 |

生效合约（signal）：

- **黑色**：rb 2401/2405/2410/2501/2605, i 2509/2601, FG 2509/2601（8/15，53%）
- **有色**：cu 2509, al 2509/2601, ag 2509（4/8，50%）
- **能化**：MA 2601, OI 2509, TA 2601 —（3/8，38%；TA 边缘）
- **农产品 DCE**：cs 2605, m 2405/2409/2601, p 2409/2509（5/26，19%）
- **农产品 CZCE**：0/13

## 6. 关键观察

### 6.1 跨 N 一致规律：慢速回归

几乎所有合约 N=5 差值为负（结构入场短期反而不如随机），N=20 起转正，
N=40 达到峰值。举例：

- SHFE.rb2401: Δ N=5 -0.001 → N=10 +0.059 → N=20 +0.151 → N=40 +0.229
- CZCE.FG509:  Δ N=5 -0.034 → N=10 +0.056 → N=20 +0.148 → N=40 +0.202
- DCE.m2601:   Δ N=5 -0.014 → N=10 +0.085 → N=20 +0.211 → N=40 +0.283

含义：**VA reacceptance 后的方向 edge 是慢速回归型**，与"POC 是订单流
堆积释放"直觉吻合。策略退出需要 20-40 bar（5m 数据即 100-200 分钟）
才能兑现。短时止损会杀掉真正的 edge。

### 6.2 生效边界：偏向工业品

黑色 + 有色 (cu/al/ag) + 能化 (OI/MA) 三个板块贡献了大部分 signal。
共同特征：

- 工业品种，日盘外盘都活跃，成交量高
- 板块波动率相对适中（不是 au/sc 这种事件驱动强的品种）
- 与产业库存 / 现货流通挂钩，"共识价格"概念在这些品种上更实体化

农产品（尤其 CZCE 白糖 SR / 郑州系）大量 no_signal，可能与：

- 白糖 / 棉花受政策 / 收储影响，共识不容易在 VA 中形成
- CZCE 5m 数据分钟切片不同（郑商所交易时段规则）—— 需要检查是否
  数据边界效应

### 6.3 metals 板块的两极分化

黄金 au、白银 ag 表现完全不同：

- ag 2509 有 signal，Δ N=20 +0.094
- au 2508/2512 均 no_signal，甚至 au 2512 Δ N=20 -0.167（显著劣于随机）

黄金作为"事件驱动 + 全球宏观"品种，日内 VA reacceptance 逻辑很可能
不成立。这印证了策略"共识价格"逻辑在实体驱动品种上更贴合。

### 6.4 农产品 DCE vs CZCE 差异

DCE 农产品有 5/26 signal（m/p/cs 部分合约），CZCE 农产品 0/13。
可能原因：

- DCE 品种更工业化（豆粕 → 饲料，玉米 → 淀粉产业）
- CZCE 主要品种（SR/CF）政策色彩更浓

## 7. 结论

- **一句话结论**：POC 天然的价值回归属性 (~0.55 到达率基线) 是主要 edge
  来源；VA reacceptance 结构的独立贡献只在部分板块上约 +0.03-0.06，需
  要与 POC 距离效应显式分离才能真实评估。
- **POC 吸引力 vs 结构 edge 分解**（以 black +0.090 为例）：
  - ~0.547 POC 天然回归（占绝对大头）
  - +0.054 距离效应（结构入场时点天然离 POC 近）
  - **+0.028 真正的 VA reacceptance 独立结构贡献**（约 1/3）
- **修正后的生效品种子集**（`beyond_poc` 判据）：
  - 最强：**metals**（+0.055）— cu, al, ag, au 都有独立结构 edge
  - 中：agri_czce（+0.029）、black（+0.028）、energy_chem（+0.027）
  - 弱：agri_dce（+0.010）
- **退出路径判定**：**明确的板块 / 品种子集有强信号**（第三档保持）
  但生效板块与 vs same_direction 判定**不同** —— 应以 vs distance 为准
- **是否进入阶段 2-3**：**进入**，但阶段 2-3 的所有判据必须使用
  distance-matched baseline 或在报告中同时展示两种基准
- **对策略设计的核心提示**：
  - 策略不能简单地在"任何离 POC 远的地方"入场并期望到 POC —— 这在
    metals 上不成立（离 POC 远时到达率反而更低）
  - VA reacceptance 的独立价值主要体现在**"重塑距离-到达率函数"**，而
    不是"再上一个高的到达率 baseline"
  - 结构入场比"随便找个距离相近的时点入场"高的部分（~+0.03）才是真
    edge，这个量级决定了策略预期收益空间

### 7.1 附加发现（给主 spec）

- **观察窗口 N**：短期止损（N ≤ 10）会杀掉 edge，策略退出应给至少
  N=20-40 bar 的时间预算
- **随机基准差异**：random-direction 基准并未系统性优于 same-direction，
  说明方向判定本身没有反向偏差；结构 edge 是"选对时点"而非"反着做"
- **必须使用 distance-matched baseline**：POC 天然回归属性太强，任何
  不分离距离效应的评估都会大幅高估结构 edge。这个原则应写入主 spec，
  贯穿后续所有阶段

### 7.2 方法论更新（写入 experiment-plan）

- 阶段 2 的 POC 到达率评估必须同时展示 vs distance_matched baseline
- 阶段 3 的深度分桶分析要注意 "深度改善 MFE" vs "只是离 POC 更近了"
  的区分（可能是同一效应的不同侧面）
- 阶段 4 的 rolling vs fixed-window 对照，两种锚方案都应保留 distance-
  matched baseline 做双重对照
- 阶段 5 的时间 OOS 判据基于 vs distance 差值
