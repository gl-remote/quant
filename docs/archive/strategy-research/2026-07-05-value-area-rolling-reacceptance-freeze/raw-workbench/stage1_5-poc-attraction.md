# 阶段 1.5 · POC 回归属性专项研究 · 实验报告

> 类型：Stage Report
> 状态：研究中
> 创建时间：2026-07-05
> 触发来源：阶段 1 发现 POC 天然回归属性 ~0.55 >> VA reacceptance 结构 edge +0.03
> 关联计划：[value-area-rolling-reacceptance-experiment-plan.md](value-area-rolling-reacceptance-experiment-plan.md#阶段-15poc-回归属性专项研究阶段-1-触发的新增阶段)
> 关联阶段 1：[value-area-rolling-reacceptance-stage1-direction-info.md](value-area-rolling-reacceptance-stage1-direction-info.md)
> 关联主题：[../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md](../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md)

## 1. 触发背景

阶段 1 引入 distance-matched baseline 后，观察到 POC 到达率的三层分解：

| 成分 | 数值（black 板块）| 归因 |
|------|-----------------|------|
| 完全随机 baseline | 0.547 | POC 天然回归属性 |
| distance-matched baseline | 0.601 | + 位置靠近 POC 的加成 |
| VA reacceptance 结构 | 0.629 | + 结构 edge |

POC 的天然回归属性（~0.55）远远大于 VA reacceptance 的独立结构贡献
（~+0.03），量级差约 20:1。在把 reacceptance 作为策略主入场信号之前，
必须先独立回答"POC 本身是不是一个稳定的、可利用的回归目标"，否则整个
策略定位可能建立在错误的 alpha 归因上。

## 2. 研究目标

**核心问题**：POC 是不是一个稳定的、可参数化的、可利用的回归目标？

**5 个子问题**：

1. **距离-到达率函数形状**：不同距离档下 reach_rate 如何变化？
2. **时间尺度**：不同 N 下的到达率曲线，是否存在典型回归时间？
3. **POC 触及后行为**：到达 POC 后的价格分布（穿越 / 反弹 / 震荡）
4. **POC 稳定性**：POC 跳变前后回归属性一致性
5. **触发器对比**：reacceptance vs 其他候选触发器的相对价值

## 3. 实验设置

### 3.1 数据 & 品种

- 复用阶段 1 的 5m CSV（70 合约，5 板块）
- 前一交易日 fixed-window POC/VA（与阶段 1 一致）

### 3.2 子实验 A：距离-到达率函数

对每个品种：
- 对每根 bar (idx > 0, date ∈ profile 有效期)，计算 `distance = |close - poc| / tick` 与 `side = sign(poc - close)`
- 按距离桶分组：`{0-2, 3-5, 6-10, 11-20, 21-40, 41-80, 80+}` ticks
- 对每桶统计：`reach_rate(N)` for N ∈ {5, 10, 20, 40, 80, 160}
- 输出：(sector, distance_bucket) → 曲线 { N: reach_rate }

**观察点**：
- 曲线形状是否单调 / 有拐点 / 有平台
- 板块间函数形状差异

### 3.3 子实验 B：POC 触及后行为

对每个"首次触及 POC"事件（distance 从 > 0 变为 <= 0）：
- 记录触及后 20 bar 的价格分布
- 分类：`through`（穿越到另一侧）/ `reject`（反弹回原侧）/ `oscillate`（震荡）
- 判定阈值：触及后 20 bar 内 max|close - poc| < 3 ticks → oscillate；
  20 bar 后 close 处于同侧 → reject；异侧 → through

**观察点**：
- through 占比高 → POC 不适合作为止盈目标
- reject 占比高 → POC 是天然反弹位，止盈合理
- oscillate 高 → POC 附近波动大，需要多 bar 缓冲

### 3.4 子实验 C：POC 稳定性

- POC 跳变定义：`|poc_today - poc_yesterday| >= 5 ticks`
- 分离数据：稳定日（跳变距离 < 5）vs 跳变日
- 对两组分别计算距离-到达率函数，观察差异

**观察点**：
- 稳定日 vs 跳变日回归属性是否一致
- 跳变后 1-3 天的回归属性演化

### 3.5 子实验 D：触发器对比

在同一距离桶内，对比多种触发器的下 N bar 到达率：

- **T1: reacceptance**（阶段 1 定义）
- **T2: 长实体拒绝**：一根 bar 从 VA 外向 POC 方向长实体收盘（body ≥ ATR × 0.5）
- **T3: 成交量脉冲**：volume ≥ 20 bar MA × 2
- **T4: 简单距离阈值**：距离 = distance_bucket 且往 POC 方向的 close（无其他条件）
- **T5: 无触发（distance-matched baseline）**：距离 = distance_bucket 的任意 close

对比所有 T 的 reach_rate（N=20）与 T5 差值，识别哪种触发器 edge 最强。

## 4. 执行状态

- [x] 子实验 A：距离-到达率函数（ticks 版本）[rolling_reacceptance_stage1_5_A_distance_reach.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A_distance_reach.py)
- [x] 子实验 A（ATR 修正版本）[rolling_reacceptance_stage1_5_A_distance_reach_atr.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A_distance_reach_atr.py)
- [x] 子实验 A2：Reacceptance 事件的 ATR 距离档分布 [rolling_reacceptance_stage1_5_A2_reacceptance_distance.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A2_reacceptance_distance.py)
- [x] 子实验 A3：期望值 / R:R 计算 [rolling_reacceptance_stage1_5_A3_expected_value.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A3_expected_value.py)
- [x] 子实验 A4：多结构敏感性 [rolling_reacceptance_stage1_5_A4_multi_structure.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A4_multi_structure.py)
- [x] 子实验 A5：多锚点引力对比（证伪 POC 特殊性）[rolling_reacceptance_stage1_5_A5_multi_anchor.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A5_multi_anchor.py)
- [x] 子实验 A5b：Reacceptance 事件下多锚点对比 [rolling_reacceptance_stage1_5_A5b_reacc_multi_anchor.py](../../scripts/analysis/rolling_reacceptance_stage1_5_A5b_reacc_multi_anchor.py)
- [ ] 子实验 B：POC 触及后行为
- [ ] 子实验 C：POC 稳定性
- [ ] 子实验 D：触发器对比
- [ ] 结论汇总 & 主题定位决策

原始结果：
- ticks 版本：[stage1_5_A_distance_reach.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A_distance_reach.md)
- **ATR 版本（主结论）**：[stage1_5_A_distance_reach_atr.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A_distance_reach_atr.md)
- **A2 Reacceptance 分布**：[stage1_5_A2_reacceptance_distance_dist.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A2_reacceptance_distance_dist.md)
- **A3 期望值 / R:R**：[stage1_5_A3_expected_value.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A3_expected_value.md)
- **A4 多结构敏感性**：[stage1_5_A4_multi_structure.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A4_multi_structure.md)
- **A5 多锚点对比**：[stage1_5_A5_multi_anchor.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A5_multi_anchor.md)
- **A5b Reacceptance 下多锚点**：[stage1_5_A5b_reacc_multi_anchor.md](../../project_data/analysis/rolling_reacceptance_stage1_5/stage1_5_A5b_reacc_multi_anchor.md)

## 5. 子实验 A 结果

### 5.1 板块 × 距离(ticks) · N=20 到达率总表

（事件加权，共 5 板块 70 合约，样本量 15-224k 每桶）

| 距离 (ticks) | agri_czce | agri_dce | black | energy_chem | **metals** |
|-------------|-----------|----------|-------|-------------|-----------|
| 0-2 | 0.914 | 0.906 | 0.926 | 0.936 | 0.933 |
| 3-5 | 0.734 | 0.700 | 0.749 | 0.778 | 0.771 |
| 6-10 | 0.523 | 0.455 | 0.513 | 0.573 | 0.517 |
| 11-20 | 0.329 | 0.276 | 0.272 | 0.362 | 0.356 |
| 21-40 | 0.133 | 0.137 | **0.086** | 0.208 | **0.255** |
| 41-80 | 0.036 | 0.045 | 0.019 | 0.083 | **0.171** |
| 80+ | 0.005 | 0.022 | 0.013 | 0.030 | **0.081** |

### 5.1.5 ⚠️ ATR 修正后重大反转：板块差异消失

用户提出："tick 是绝对单位，跨品种不可比，未考虑波动率。距离近可能受
随机波动影响较大。"该怀疑被数据完全证实。

**ATR 单位下的板块聚合表（N=20）**：

| 距离(ATR) | agri_czce | agri_dce | black | energy_chem | metals |
|----------|-----------|----------|-------|-------------|--------|
| 0-0.2 | 0.967 | 0.963 | 0.975 | 0.960 | 0.954 |
| 0.2-0.5 | 0.926 | 0.922 | 0.935 | 0.922 | 0.916 |
| 0.5-1.0 | 0.798 | 0.812 | 0.820 | 0.803 | 0.790 |
| 1.0-1.5 | 0.663 | 0.664 | 0.688 | 0.674 | 0.638 |
| 1.5-2.5 | 0.492 | 0.489 | 0.512 | 0.505 | 0.493 |
| 2.5-4.0 | 0.294 | 0.272 | 0.280 | 0.284 | 0.285 |
| 4.0+ | 0.087 | 0.063 | 0.053 | 0.085 | 0.091 |

**结论完全反转**：跨板块最大差异只有 3-5 个百分点。之前 ticks 版本看
到的 "metals 远距离特权"、"black 中距离塌陷" 全部是**波动率异质性的
假象**。

**关键证据**：SHFE.rb 平均 ATR=6 ticks，SHFE.au 平均 ATR=49 ticks，
差 8 倍。ticks 版本把两者放到同一距离桶，等于把 "rb 一个 ATR" 与
"au 1/8 个 ATR" 归并——难度完全不同。

**新的核心结论**：

> **POC 距离-到达率函数是波动率归一化的普适规律，与板块无关。**
> 在 ATR 单位下，5 板块曲线几乎完全重合。

这个发现比 ticks 版本更有价值：意味着策略可以用**同一套 ATR 参数**跨
品种通用，不需要品种特定参数。

### 5.2 关键观察（基于 ATR 版本）

**观察 1：近距离（< 0.5 ATR）→ 红利区**

- 0-0.2 ATR: 96%+ 到达
- 0.2-0.5 ATR: 92%+ 到达
- 5 板块几乎无差异，说明这是"日内波动足以覆盖的距离"，本质是随机
  漂移就够了，不是 POC 独特引力

**观察 2：中距离（0.5-1.5 ATR）→ 过近区**

- 0.5-1.0 ATR: 79-82% 到达
- 1.0-1.5 ATR: 64-69% 到达
- 到达率仍高但已明显低于 100%，是"日内典型波动能触及"的距离
- baseline 太高，触发器很难产生显著 edge

**观察 3：策略甜蜜区（1.5-2.5 ATR）→ 49-51%**

- 到达率约一半，是"需要接近 2 倍日内典型波动才能触及"
- 5 板块完全一致（49.2% / 48.9% / 51.2% / 50.5% / 49.3%）
- **这是策略最有价值的距离档**：baseline 中等，触发器差异有意义

**观察 4：远距离衰减**

- 2.5-4.0 ATR: 27-29% 到达（仍有希望但明显衰减）
- 4.0+ ATR: 5-9% 到达（垃圾区，本质是"极端事件才能触及"）

**观察 5：时间尺度**

固定距离 1.5-2.5 ATR（甜蜜区），black 板块 reach_rate 随 N 演化：

```
N=5:  0.199 → N=10: 0.372 → N=20: 0.558 → N=40: 0.691 → N=80: 0.802 → N=160: 0.867
```

- N=5-40 阶段线性增长，边际收益一致
- N=80 之后进入平台期
- **典型 POC 回归时间：N=20-80 bar**（5m 数据即 100-400 分钟）
- 与 ticks 版本结论一致，但 ATR 版本的时间尺度略长（因甜蜜区距离本身更远）

**观察 6：距离衰减在 ATR 单位下更平滑**

以 black 板块 N=20 为例：

```
距离(ATR): 0.1, 0.35, 0.75, 1.25, 2.0, 3.25, 5.0
reach_rate: 0.975, 0.935, 0.820, 0.688, 0.512, 0.280, 0.05
```

不像 ticks 版本那种"两段式（20 ticks 悬崖）"，ATR 单位下是**平滑衰减**。
这符合直觉：距离越远，需要越多倍波动去覆盖，回归概率单调递减。

**"引力半径"重新定义**：约 **2.5 ATR**（对应 black rb 约 15 ticks，对
应 metals au 约 120 ticks）—— 超过这个距离，POC 引力就不足以战胜噪声。

### 5.3 策略含义（基于 ATR 版本）

**关键距离档划分（ATR 单位，跨板块普适）**：

| 距离档 (ATR) | 到达率 (N=20) | 策略含义 |
|-------------|--------------|---------|
| 0-0.5 | 92-97% | **红利区**：日内噪声足以触及，不需策略 |
| 0.5-1.5 | 64-82% | **过近区**：baseline 过高，触发器 edge 空间小 |
| 1.5-2.5 | ~49-51% | **策略甜蜜区**：baseline 均衡，触发器差异有意义 |
| 2.5-4.0 | ~28% | **远距离**：需强触发器，可选布局 |
| 4.0+ | <10% | **垃圾区**：不做 POC 回归策略 |

**对 VA reacceptance 策略的重新审视**：

阶段 1 结构 edge +0.03 必须放在 **ATR 距离档**上评估：

- reacceptance 事件在 VA 边界（VAL/VAH），距 POC 约 0.5 VA 宽度
- 一天 VA 宽度典型是 1-2 ATR（volume 集中区）
- 所以 reacceptance 事件平均距 POC 约 **0.5-1.0 ATR**（过近区）
- baseline 到达率 79-82%，+0.03 结构 edge 相对占比约 3.7%
- **不算高价值，因为 baseline 本身已经 80%**

**修正后的策略定位提示**：

- **策略不应聚焦 reacceptance 触发**：baseline 太高，edge 空间被压缩
- **策略应主动寻找 1.5-2.5 ATR 距离档的入场机会**：baseline 中等，触发
  器差异可产生真实 alpha
- **策略参数应用 ATR 单位**：距离阈值、止损、止盈都按 ATR 归一化，跨
  品种通用，不需要品种特定参数
- **主题定位需要重大 pivot**：从"VA reacceptance"转向"距离-触发器"框架

**新的策略框架草案**：

```
1. 计算 POC 与 ATR
2. 距离档判定：|close - POC| / ATR 落在哪个档
3. 只在 1.5-2.5 ATR 档（甜蜜区）寻找入场
4. 触发器：reacceptance / 长实体拒绝 / 成交量脉冲（子实验 D 待定）
5. 目标：POC（baseline 49-51%，加触发器 edge）
6. 时间预算：40-80 bar
7. 止损：距离档 + 1 ATR
```

这个框架比原来的 VA reacceptance 主导框架更接近真实 alpha 来源。

### 5.4 A2 补充：Reacceptance 事件的 ATR 距离档分布（关键修正）

前一小节 5.3 假设 "reacceptance 事件平均落在 0.5-1.0 ATR 过近区"。子
实验 A2 直接验证该假设，**结果颠覆推断**：

#### 5.4.1 事件分布：分散、不集中在过近区

| 板块 | 总事件 | <0.5 ATR (红利+近红利) | 0.5-1.5 ATR (过近区) | 1.5-2.5 ATR (甜蜜区) | 2.5+ ATR (远) |
|------|-------|---------------------|---------------------|--------------------|--------------|
| black | 1150 | 24.3% | 33.8% | 17.0% | **24.9%** |
| agri_czce | 1170 | 18.4% | 28.6% | 21.3% | **31.6%** |
| agri_dce | 1922 | 16.8% | 31.8% | 22.9% | **28.5%** |
| energy_chem | 934 | 20.3% | 28.8% | 17.3% | **33.7%** |
| **metals** | 995 | 19.9% | 21.2% | 14.3% | **44.6%** |

reacceptance 事件的分布是**双峰型**：一峰在过近区（~30%），另一峰在
**远距离 2.5+ ATR**（25-45%）。metals 尤其显著，近半事件落在远距离。

平均距离（板块）：

- black 1.78 ATR （中位 1.20）
- agri_czce 2.02 ATR（中位 1.60）
- agri_dce 2.06 ATR（中位 1.54）
- energy_chem 2.32 ATR（中位 1.55）
- metals **3.04 ATR**（中位 2.08）—— 最远

#### 5.4.2 Reacceptance edge 在不同距离档的分布

各距离档下 reacceptance 事件 reach_rate 相对 baseline 的 Δ (N=20)：

| sector | 0-0.5 ATR | 0.5-1.5 ATR | 1.5-2.5 ATR | 2.5-4.0 ATR | 4.0+ ATR |
|--------|-----------|-------------|-------------|-------------|----------|
| agri_czce | +0.033~+0.041 | -0.020~+0.008 | -0.026 | **+0.053** | **+0.086** |
| agri_dce | -0.032~+0.017 | -0.073~+0.003 | -0.004 | -0.009 | **+0.037** |
| black | -0.006~+0.009 | -0.037~+0.008 | +0.019 | +0.001 | **+0.070** |
| energy_chem | +0.023~+0.040 | -0.016~+0.059 | +0.008 | -0.035 | **+0.096** |
| metals | +0.003~+0.055 | +0.025~+0.034 | **+0.049** | **+0.061** | +0.039 |

**关键洞察**：

1. **近距离档（<1.5 ATR）**：reacceptance edge 几乎为零或负 → 触发器
   在此无附加价值，baseline 本身已高
2. **远距离档（4.0+ ATR）**：**reacceptance edge 最大 (+0.04~+0.10)**，
   相对 baseline 5-9% 的相对提升达 **40-100%**
3. **甜蜜区（1.5-2.5 ATR）**：只有 metals 有显著 +0.049 edge，其他板块
   微弱

#### 5.4.3 策略推断的重大修正

**5.3 的推断错了一半**：

- ✅ "reacceptance 在过近区 baseline 高、edge 空间小" 正确
- ❌ "reacceptance 事件平均落在过近区" **错误** —— 实际近半事件在
  远距离，且远距离才是 reacceptance 的真正价值区

**修正后的策略框架**：

```
1. 计算 POC 与 ATR
2. 距离档判定：|close - POC| / ATR
3. 主入场：远距离 (2.5+ ATR) 检测 reacceptance 事件
   - baseline 极低（5-30%）→ 到达 POC 就是大 R:R
   - reacceptance edge 最强（+0.04~+0.10 绝对，40-100% 相对）
   - 事件数量充足（板块 25-45% 分布于此）
4. 次入场：甜蜜区 (1.5-2.5 ATR) 仅 metals（+0.049 edge）
5. 排除：近距离 (<1.5 ATR) reacceptance 无 edge
6. 目标：POC
7. 时间预算：远距离 N=40-80 bar，甜蜜区 N=40 bar
8. 止损：距离档 + 1 ATR
```

**这是本次研究到目前为止最有实用价值的定位**。之前主题 README 论证
的 "rolling 追踪 POC 跳变"仍然成立，但作用点从"精确定位 VAL/VAH 供
reacceptance 触发"变为"精确定位远距离 POC 供大 R:R 布局"。

**metals 板块特殊性**：44.6% 事件落远距离 + 甜蜜区仍有 +0.049 edge。
metals 是**唯一在双距离档都可行的板块**，可以作为策略的"主战场"。

### 5.5 A3 期望值验证：真实交易语义下的最终结论

5.4 结论"远距离 reacceptance 有 +40-100% 相对 edge"只是 reach_rate 层
面的观察。真实策略还要考虑止损、成本、时间限制。A3 用真实交易路径模拟
（stop_atr 反向止损 / POC 止盈 / 80 bar 时间限制 / 0.1 ATR 双边成本）
计算每距离档的**期望净收益**（单位 ATR）。

#### 5.5.1 Stop=1.5 ATR 下的关键结果（reacceptance 事件）

| sector | 0-0.5 | 0.5-1.0 | 1.0-1.5 | 1.5-2.5 | 2.5-4.0 | **4.0+** |
|--------|-------|---------|---------|---------|---------|----------|
| agri_czce | -0.17 | -0.28 | -0.19 | -0.36 | -0.06 | **+0.15** |
| agri_dce | -0.21 | -0.11 | -0.23 | **+0.03** | -0.44 | **+0.05** |
| **black** | -0.16 | -0.22 | -0.07 | -0.11 | -0.24 | **+0.24** |
| **energy_chem** | -0.18 | -0.09 | -0.12 | -0.34 | -0.16 | **+0.48** |
| ⚠️ metals | -0.27 | -0.29 | -0.18 | -0.04 | -0.09 | **-0.39** |

**核心发现**：绝大多数距离档 × 板块组合成本后为负期望，**只有远距离
档 (4.0+ ATR) + 大止损 (1.5 ATR) 组合有实质正期望**，且 **metals 是
唯一例外，远距离档反而是最差的**。

#### 5.5.2 唯一稳定盈利的策略雏形

**距离档 4.0+ ATR + stop=1.5 ATR + POC 目标**：

| sector | reacc pnl_net | baseline pnl_net | Δ (reacc - baseline) | reacc 胜率 |
|--------|--------------|-----------------|--------------------|-----------|
| **energy_chem** | **+0.483 ATR** | +0.068 | **+0.415** | 28.2% |
| **black** | **+0.238 ATR** | -0.228 | **+0.466** | 23.8% |
| agri_czce | +0.145 | +0.130 | +0.014 | 27.8% |
| agri_dce | +0.054 | -0.209 | +0.264 | 20.0% |
| **metals** | **-0.392** | -0.106 | **-0.286** ⚠️ | 15.1% |

**最强组合**：**energy_chem 远距离档 reacceptance**，每笔期望 +0.483
ATR，相对 distance-matched baseline 的 edge 是 +0.415 ATR。**black 板
块 +0.238 ATR 每笔，相对 baseline edge 是 +0.466 ATR**（baseline 本身
亏损 -0.228，reacceptance 把负期望翻正）。

#### 5.5.3 Metals 陷阱：波动率异质性再作祟

**metals 在远距离档反而最差 (-0.392 ATR)**，与 A2 的 reach_rate 观察
（远距离 +0.039 edge）不一致。原因：

- metals 事件在 4.0+ 档占 285 个（其他板块 122-240），大量来自 au
- au tick=0.02、avg_atr≈1，4+ ATR 距离意味着 ~200 ticks
- 4+ ATR reach_rate 只有 15.1%，即使到 POC 也吃不下 1.5 ATR 止损的
  86.5% 亏损

**这暴露了 A2 结论的局限**：reach_rate 增加不等于期望收益增加。**A/A2
把 metals 归为"最强板块"是 reach_rate 层面的假象**，真实盈利要看 PnL
分布，而 au 的高波动率杀掉了远距离交易。

**Metals 应被排除或拆分处理**（cu/al/ag vs au 分离）。

#### 5.5.4 Stop 敏感性

不同 stop 下同一距离档的表现差异巨大：

- **stop=0.5**：全部距离档都是负期望，胜率高但每笔盈利不足以覆盖成本
- **stop=1.0**：中距离档（1.5-2.5）在 agri_dce/black/metals 边际盈利
- **stop=1.5**：**最好的选择**，远距离档转正，中距离档略负但接近平衡

**Stop=1.0 是"陷阱区"**（black 2.5-4.0 档 stop=1.0 时 Δ=-0.376 极差）：
止损太宽让胜率降低但没换来足够收益，止损太紧又杀掉 edge。

#### 5.5.5 策略最终定位（基于 A3 数据）

> ⚠️ **本节结论受限于 A3 的最简交易结构**（单一 POC 目标 + 固定 stop +
> 无部分止盈）。更复杂结构下盈利地图会显著变化，见 §5.5.7 保留意见。

**唯一可行策略雏形**（从 5.4 修正后进一步收紧）：

```
条件：
  - 距离档 4.0+ ATR
  - reacceptance 触发（bar close 从 VA 外穿回内）
  - Stop = 1.5 ATR（反向）
  - 目标 = POC（同方向）
  - 时间限制 = 80 bar
  - 假设成本 = 0.1 ATR/笔双边

生效板块（按期望降序）：
  1. energy_chem: +0.483 ATR/笔（TA/MA/OI/sc）
  2. black:       +0.238 ATR/笔（rb/i/hc/FG）
  3. agri_czce:   +0.145 ATR/笔（SR/CF/RM）
  4. agri_dce:    +0.054 ATR/笔（m/p/y/c/cs，边际）

禁用板块：
  ⚠️ metals: -0.392 ATR/笔（主要因 au 波动率异常）
```

**样本量警告**：4.0+ 档 reacceptance 事件每板块 120-285 个，跨 3-5 年
多合约。**信度中等，需要样本外验证**（阶段 5 的时间维度 OOS 必做）。

#### 5.5.6 与 A2 结论的重要修正

A2 的关键错误："metals 是策略主战场"—— 基于 reach_rate 相对 baseline
的 edge。A3 用真实 PnL 揭示了：

- reach_rate edge ≠ 期望收益 edge
- 高波动率品种（au）在远距离档到达率虽有相对提升，但因绝对波动大，止损
  成本吃掉一切盈利
- **策略选品必须基于成本后期望净值**，不能只看 reach_rate

**给主 spec 的强制约束**：所有后续阶段的判据必须使用 "成本后期望净值"，
不能仅用 reach_rate 或 win_rate。

#### 5.5.7 ⚠️ 交易结构敏感性保留意见

**A3 的结论"只有远距离档 + stop=1.5 ATR 值得做" 是特定交易结构下的结论**，
不是本质规律。A3 假设了四个约束：

1. 单一目标 POC（不到 POC 全部算失败）
2. 固定 stop（全程不动）
3. 无部分止盈 / 无移仓
4. 80 bar 硬性时间死线

真实策略可以有更复杂的止盈止损结构，会显著改变盈利地图：

| 结构变量 | 对哪个距离档的影响 |
|---------|------------------|
| 部分止盈（scaling out） | **可能让 1.5-2.5 ATR 甜蜜区从负期望翻正** |
| 移动止损 / breakeven | 远距离档保本，把 timeout 尾部损失砍掉 |
| VA 中位 / 半程目标 | 绕开"必到 POC"的硬约束，近距离档可能激活 |
| 分级 stop（距离自适应） | 近档紧 stop、远档宽 stop，替代"一刀切 1.5 ATR" |
| 时间衰减部分退出 | 减少 timeout 拖尾亏损 |

**推演举例**：1.5-2.5 ATR 甜蜜区，A3 原本期望约 -0.09 ATR；若加"到半路
先兑现 50%，剩下追 POC"：新期望粗算 **+0.09 ATR**（翻正）。

**方法论修正**：**"策略定位"应该是"结构 × 距离档"二维联合优化**，不是
"固定结构下的距离档筛选"。A3 的 §5.5.5 "唯一可行策略雏形" 应该重述为
**"最简结构下的基线策略雏形"**，避免锚定过早。

**建议后续动作**：新增子实验 A4，用少数距离档 × 4-6 种交易结构做初筛，
把"结构选择敏感性"量化，再决定策略最终框架。A4 的成本估计 2-4 小时，
在决定策略主结构前必做。

**给阶段 4/5 的强制约束**：rolling vs fixed-window 对照必须在**最优
结构下**做，不能在 A3 的最简结构下判定 rolling 优劣。否则 rolling 的
真实价值可能因结构选择不当被埋没。

### 5.6 A4 多结构敏感性验证

对同一批 reacceptance 事件，用 6 种交易结构模拟：

| 代号 | 结构 |
|------|------|
| S1_baseline | 固定 stop=1.5 ATR + 目标 POC + 80 bar timeout（A3 默认） |
| S2_partial_50 | 半路先平 50% + 剩下 BE stop + 目标 POC |
| S3_breakeven | 初始 stop=1.5 + 走 1 ATR 后 stop 上移到 BE + 目标 POC |
| S4_midpoint | 目标改为 entry-POC 中点 + stop=1.5 |
| S5_tiered_stop | stop 随距离档动态（近 0.5 / 中 1.0-1.5 / 远 2.0） |
| S6_time_decay | 40 bar 检查 + pnl > 0.3 ATR 早退 + stop=1.5 |

#### 5.6.1 每板块最优结构 × 期望净值（4+ ATR 档）

| 板块 | 最优结构 | 最优期望 | 最差期望 | 敏感性 (max-min) |
|------|---------|---------|---------|-----------------|
| **energy_chem** | S1_baseline | **+0.483** | -2.006 (S4) | **2.489** |
| **black** | S1_baseline | **+0.238** | -1.487 (S4) | **1.725** |
| agri_czce | **S5_tiered_stop** | **+0.290** | -1.247 (S4) | **1.537** |
| agri_dce | S5_tiered_stop | +0.086 | -1.556 (S4) | 1.641 |
| ⚠️ metals | S6_time_decay | -0.245 | -2.296 (S4) | 2.051 |

**核心发现**：

- **结构敏感性最高达 2.5 ATR/笔**（energy_chem 4+ 档）—— 选错结构的
  惩罚远大于选错距离档
- **agri_czce 4+ 档在 S5 tiered stop 下期望 +0.290，翻倍于 S1 (+0.145)**
- **agri_dce 4+ 档在 S5 下从 +0.054 抬到 +0.086**
- **metals 4+ 档在所有 6 种结构下都亏损**，最好 S6_time_decay 仍然 -0.245，
  确认 metals 远距离档禁用

#### 5.6.2 中距离档（2-4 ATR）的新入口

A3 结论"只有 4+ 档值得做"被 A4 部分修正：

| 板块 | S1 (2-4) | S3 breakeven (2-4) | 变化 |
|------|---------|-------------------|------|
| **metals** | -0.014 | **+0.038** | **翻正** |
| agri_czce | -0.152 | -0.086 | 改善 -0.066 |
| agri_dce | -0.260 | -0.204 | 改善 -0.056 |
| black | -0.172 | -0.208 | 略差 |
| energy_chem | -0.243 | -0.254 | 微差 |

**metals 2-4 档 + S3 breakeven** 是新增可考虑组合（+0.038 ATR/笔）。
但幅度小，可能样本外脆弱。

#### 5.6.3 结构选择的普适规律

跨板块观察 6 种结构的表现：

- **S1（基线）**：4+ 档最强（远距离靠"能到 POC 就大赚"）
- **S2（部分止盈）**：**几乎全档都差** —— 稀释了 winner，无法覆盖 loser
- **S3（BE trailing）**：中距离档小幅改善，远距离档反而拖累（提前 BE 让部分 winner 变 breakeven）
- **S4（中位目标）**：**灾难** —— 各档全线负期望，最差 -2.3 ATR/笔
- **S5（分级 stop）**：农产品远距离改善，其他板块中性
- **S6（时间衰减）**：与 S1 几乎相同，metals 上略优

**教训**：

- **"部分止盈直觉"是陷阱**：稀释稀有 winner 的盈利，远比固定目标差
- **"缩小目标至中点"是双输**：更远的止损相对更近的目标，风险回报变差
- **BE trailing 只在中距离档有意义**：远距离档 BE 触发后剩下的 winner 概率太低

#### 5.6.4 最终策略地图（多结构考量）

**主战场（4+ ATR 档）**：

| 板块 | 结构 | 期望 |
|------|-----|------|
| energy_chem | **S1_baseline** | **+0.483 ATR/笔** |
| agri_czce | **S5_tiered_stop** | **+0.290 ATR/笔** |
| black | **S1_baseline** | **+0.238 ATR/笔** |
| agri_dce | S5_tiered_stop | +0.086 ATR/笔（边际） |
| metals | ❌ 全禁用 | 最好 -0.245 |

**次战场（2-4 ATR 档）**：

| 板块 | 结构 | 期望 |
|------|-----|------|
| metals | S3_breakeven | +0.038 ATR/笔（弱）|
| 其他板块 | — | 都负 |

**禁用组合**：

- S2 部分止盈（全档普遍拖累）
- S4 中位目标（全档灾难）
- 0-1 / 1-2 ATR 档所有结构（近距离档 baseline 太高，reacceptance 无 edge）

#### 5.6.5 对主题定位的最终修正

**验证用户直觉**：结构敏感性远大于距离档选择，A3 的"最简结构下的距离档
筛选"不能作为策略定位定论。

**修正后的策略框架草案**（多结构考量）：

```
入场：距离档 4+ ATR + reacceptance 事件
生效板块：energy_chem / black / agri_czce / agri_dce
禁用板块：metals

结构（因板块而异）：
  energy_chem: S1 baseline (fixed stop 1.5 + POC + 80 bar)
  black:       S1 baseline
  agri_czce:   S5 tiered stop (远档 stop=2.0 ATR)
  agri_dce:    S5 tiered stop

次入场（低优先级）：距离档 2-4 ATR + reacceptance
  仅 metals 板块 + S3 breakeven，期望 +0.038 ATR/笔
```

**给主 spec 与后续阶段的强制约束**：

- 阶段 2 判据必须涵盖至少 S1/S3/S5 三种结构
- 阶段 4 rolling vs fixed-window 对照必须在**每板块的最优结构下**做
  （不是统一的 S1）
- 阶段 5 时间 OOS 只测最优结构组合，不重新扫结构

**开放问题**：

- 是否有"S5 + S3 组合结构"（近档紧 stop + 中档 BE trailing + 远档宽 stop）？
- 目标能否不用绝对 POC 而用"最强 volume 位"（例如 rolling POC 追踪版本）？
  这直接对应主题原假设"rolling POC 更精准"
- au 是否需要单独处理（tick=0.02 是异常值）？子实验 D 之前可先小样本验证

### 5.7 A5 多锚点对比：⚠️ POC 特殊性证伪

用户提出保留意见："既然 POC 引力这么显著，那非 POC 价格点是否也有相同
的距离-回归规律？"这是必要的证伪实验，直接检验 A/A2/A3/A4 全部隐含的
"POC 是特殊引力点"假设。

对同一批 bar，用 7 种锚点计算距离-到达率函数：

- **POC**：前日 volume 分布众数（主）
- **VAH / VAL**：前日 VA 上下边界
- **RunnerUpPOC**：前日 volume 第 2 大桶（距 POC ≥3 ticks）
- **PrevClose**：前日收盘价（时间锚，非分布）
- **PrevMid**：前日 (H+L)/2（对称时间锚）
- **PriceMedian**：前日 close 序列中位数（非 volume 加权分布）

#### 5.7.1 结果：所有锚点到达率完全重合

跨板块聚合 · N=20 到达率：

| anchor | 0-0.5 | 0.5-1.0 | 1.0-1.5 | 1.5-2.5 | 2.5-4.0 | **4.0+** |
|--------|-------|---------|---------|---------|---------|----------|
| **POC** | 0.933 | 0.807 | 0.665 | 0.494 | 0.280 | **0.075** |
| VAH | 0.933 | 0.809 | 0.671 | 0.489 | 0.280 | 0.072 |
| VAL | 0.933 | 0.808 | 0.671 | 0.486 | 0.275 | 0.067 |
| RunnerUpPOC | 0.935 | 0.808 | 0.670 | 0.497 | 0.288 | 0.071 |
| **PrevClose** | 0.934 | 0.814 | 0.675 | 0.497 | 0.283 | **0.083** |
| PrevMid | 0.928 | 0.791 | 0.659 | 0.494 | 0.281 | 0.072 |
| PriceMedian | 0.934 | 0.809 | 0.668 | 0.500 | 0.291 | 0.072 |

**7 个锚点到达率跨全部距离档差异 ≤ 0.02**。POC 在 4.0+ 档甚至**略低于
PrevClose**（0.075 vs 0.083）。

**结论：POC 没有独特引力属性**。之前 A/A2/A3/A4 归因为"POC 引力"的规律，
实际上是**价格均值回归的普遍现象**，与锚点选择无关。

#### 5.7.2 对整个 stage 1.5 的归因修正

**旧归因（A/A2/A3/A4 隐含）**：POC 是共识价格 → 有独特引力 → 价格倾向
于回归到 POC → 策略可以用 POC 做目标

**新归因（A5 确认）**：**价格有普遍均值回归属性**，"任何合理定义的日内
价格锚点"都是"合理均值估计"，都能作为回归目标。POC 不特殊。

**保留成立的部分**：

- 距离-到达率函数（A）：**成立**，只是归因换成"价格均值回归"
- ATR 归一化的普适性（A）：**成立**，波动率归一化后跨品种可比
- reacceptance 相对 baseline 的 edge（A2）：**依然成立**，因为 baseline
  已经包含 POC 引力（也就是均值回归 baseline），reacceptance 的 +0.03
  ~ +0.10 是独立于此的结构 edge
- 结构敏感性（A4）：**完全独立于 POC 假设**，依然成立

**需要重构的部分**：

- 主题原假设 "POC/VA reacceptance 有独立结构 edge" 需要修正为
  "reacceptance 事件是均值回归的有效触发器，而非'POC 引力'的入口"
- rolling POC 追踪的价值需要重新论证：不是"追踪跳变的共识价格"，而是
  "追踪最优的均值回归目标"（但 A5 说各种锚点都差不多，rolling 追踪的
  独特性也被质疑）

#### 5.7.3 策略框架的进一步修正

**A4 后的策略框架**：
> 入场：4+ ATR 档 + reacceptance，目标 POC，stop 因板块不同

**A5 后的策略框架**（更松散、更普适）：

```
入场：距离档 4+ ATR (ATR 单位) + 某种"回归触发器"
     - Reacceptance 是候选之一（A2 说 +0.03 ~ +0.10 edge）
     - 但也可能有其他更好的触发器（Stage D 待验证）

目标：任意"日内合理价格锚"，POC 是其中之一但不唯一
     - PrevClose 在远距离档到达率还略高于 POC
     - 策略可以用"多锚点平均"或"最近锚点"作为目标

止损与结构：A4 的结论完全独立成立
```

**策略从"POC 追踪型"降级为"均值回归型 + reacceptance 触发"**。

#### 5.7.4 对 rolling vs fixed-window 主题假设的冲击

主题 README §8 论证 rolling POC 相对 fixed-window POC 的价值（追踪
POC 跳变）。**A5 后这个论证的前提被弱化**：

- 如果 POC 不特殊，那"追踪 POC 跳变"的价值也就不特殊
- rolling 的价值可能是"更好地追踪当前均值回归目标"，但目标是什么都可
  接受（POC / PrevClose / 加权中位数）

**阶段 4（rolling vs fixed-window 对照）需要重构判据**：
- 原判据："rolling POC 是否比 fixed-window POC 更好"
- 新判据："rolling 均值锚（不限 POC）是否比 fixed-window 均值锚更好"
- 且需要对比 rolling POC vs rolling PrevClose vs rolling 其他锚

#### 5.7.5 一个仍然开放的重要问题

A5 只测了**无条件到达率**（所有 bar）。**reacceptance 事件下不同锚点
的到达率是否也重合**尚未验证。

猜测：**可能不重合**。因为 reacceptance 是 VA 边界的事件，与 POC 位置
天然相关；而 PrevClose 与 reacceptance 定义无关。**下一步应做 A5b：对
reacceptance 事件测各锚点的到达率**，验证 reacceptance 是否对 POC 有
选择性偏好。

若 A5b 显示 reacceptance 事件下 POC 到达率显著高于其他锚点 → POC 与
reacceptance 有耦合价值，主题假设部分成立
若 A5b 显示 reacceptance 事件下所有锚点到达率仍重合 → reacceptance
只是普遍均值回归的触发器，与 POC 无耦合，主题假设完全失败

### 5.8 A5b：Reacceptance 事件下 POC 也没有特殊性 —— 主题假设完全失败

跨板块聚合 · reacceptance 事件下各锚点到达率：

| anchor | 0-0.5 | 0.5-1.0 | 1.0-1.5 | 1.5-2.5 | 2.5-4.0 | **4.0+** |
|--------|-------|---------|---------|---------|---------|----------|
| POC | 0.929 | 0.788 | 0.618 | 0.489 | 0.278 | **0.126** |
| VAH | 0.950 | 0.805 | 0.664 | 0.402 | 0.262 | 0.106 |
| VAL | 0.931 | 0.805 | 0.714 | 0.408 | 0.261 | 0.094 |
| RunnerUpPOC | 0.943 | 0.798 | 0.679 | 0.513 | 0.265 | 0.103 |
| **PrevClose** | 0.935 | 0.784 | 0.676 | 0.487 | 0.260 | **0.149** |
| PrevMid | 0.927 | 0.791 | 0.630 | 0.467 | 0.288 | 0.122 |
| PriceMedian | 0.926 | 0.779 | 0.661 | 0.508 | 0.322 | 0.096 |

**POC 相对其他锚点差值几乎全部在 -0.05 ~ +0.09 抖动**，没有系统性优势。
关键反转：**4.0+ ATR 档 PrevClose 到达率 0.149 > POC 0.126**（PrevClose
比 POC 高 +0.023）。

**结论**：即使在 reacceptance 事件条件下，POC 仍然不比其他锚点特殊。
**主题假设 "POC/reacceptance 耦合"完全失败**。

#### 5.8.1 主题假设崩塌

对照主题原假设链：

| 假设 | 验证结果 |
|------|---------|
| A. POC/VA 反映共识价格 | 部分成立（volume 分布有意义）|
| B. 滚动刷新能更好捕获共识 | **不成立** — POC 不特殊，追踪的东西不特殊 |
| C. 价格回到 VA 内部有方向信息 | 均值回归成立，但**不是 POC 特有** |
| D. 重新接受深度改善风险空间 | 未直接测；同样依赖 POC 特殊性 |
| E. POC 目标可兑现 | **可兑现但因为均值回归**，任何锚点都可 |
| F. 跨品种普遍成立 | 均值回归普适，但 POC 定位无独特价值 |

主题原本核心 pivot（"用 rolling 追踪 POC 的跳变"）**在 A5/A5b 证伪后
不成立**：既然 POC 不特殊，追踪 POC 的跳变也不特殊。

#### 5.8.2 但 reacceptance edge 依然存在（A2 数据）

**A2 观察 reacceptance 事件相对 distance-matched baseline 的 edge
+0.03 ~ +0.10，A5b 没有推翻这一点**：

- A2 比较的是"reacceptance 事件 vs 同距离档任意 bar"（同一锚点 POC 下）
- A5b 只测"reacceptance 事件下 POC 是否比其他锚点强"

**两者不冲突**：reacceptance 是有效的均值回归触发器（edge 独立于锚点
选择），但**不是 POC 特有的触发器**。

**新解读**：reacceptance 事件 = 波动率大幅偏离后收敛回内部的信号，是
**均值回归 timing 的证据**。它触发的不是"回到 POC"，而是"回到某个日
内合理均值"（POC / PrevClose / PriceMedian 都可）。

#### 5.8.3 策略最终定位（A5b 后）

**新的策略假设**：**波动率均值回归 + reacceptance 触发**

```
入场：
  - 触发：reacceptance 事件（bar close 从 VA 外穿回内）
  - 距离档过滤：2.5+ ATR（甜蜜区 & 远距离）
  - 生效板块：energy_chem / black / agri_czce / agri_dce（除 metals）

目标：任意合理日内均值锚
  - 候选：POC / PrevClose / PriceMedian
  - PrevClose 在远距离档略优于 POC（4.0+ 档 0.149 vs 0.126）
  - 或用"离入场最近的可用锚"（自适应）

结构：A4 结论保留
  - 4+ ATR 档：S1 baseline（多数板块）/ S5 tiered stop（农产品）
  - 2-4 ATR 档：S3 breakeven（metals 弱正）

止损：1.5 ATR ~ 2.0 ATR，与 A4 一致
时间限制：80 bar
```

**主题从"VA rolling reacceptance"降级为"均值回归 + reacceptance 触发器"**。

#### 5.8.4 对 Rolling 假设的最终判决

主题 README §8 的 jump-process 论证（rolling POC > fixed POC）**逻辑
基础被移除**：既然 POC 不特殊，rolling POC 追踪的独特性也就不存在。

**但 rolling 本身可能仍有价值**（作为均值锚的估计工具）：

- rolling 20-bar 中位数 vs fixed-window 20-bar 中位数：谁更好？
- 但这已经不是主题原本的问题，是**均值估计方法论问题**

**建议**：
- 阶段 4（rolling vs fixed）判据完全重构 → 变为"哪种均值估计方法在
  reacceptance 触发下期望净值最优"
- 不再假设 POC 是唯一目标 → 至少对比 3 种锚（POC / PrevClose / PriceMedian）
- 判据基于 A3/A4 的期望净值口径，不再用 reach_rate

#### 5.8.5 主题命运三种可能

1. **Pivot 为"波动率均值回归策略"**（推荐）
   - 抛弃 POC 中心地位
   - 保留 reacceptance 作为触发器
   - 用最简均值锚（PrevClose）作为目标
   - 主题需要**重写 README + spec**

2. **接受 fixed-window，放弃 rolling**
   - 主题原本 pivot 意图不成立
   - 退回到前主题 value-area-reacceptance 的 fixed-window 路径
   - 但前主题已冻结，等于承认整个 rolling 主题失败

3. **主题冻结 + feature-only 出口**
   - reacceptance edge 保留，交给其他策略作为特征
   - 主题层不再作为独立策略研究
   - 与前主题命运相同

**决策依赖**：需要用户决定策略研究是"追寻 alpha 到底"（选 1，pivot）还
是"接受主题失败"（选 3，冻结）。选 2 意义不大（前主题已经在这条路上失败）。

## 6. 子实验 B 结果

_待补充。_

## 7. 子实验 C 结果

_待补充。_

## 8. 子实验 D 结果

_待补充。_

## 9. 结论与主题定位建议

_全部子实验完成后填充。回答：_

- POC 是否值得作为策略核心目标？
- 距离-到达率函数是否可参数化用于策略退出？
- POC 触及后是穿越还是反弹主导？（决定"POC 目标"的止盈逻辑）
- POC 稳定日与跳变日是否需要区别对待？
- reacceptance 相对其他触发器的位置：主触发器 / 候选之一 / 淘汰？
- 主题定位建议（保持 / pivot 到 POC 主导 / 大重定位）

### 9.1 强制前置约束（用户在 A3 后提出）

在 §9 结论落地之前，必须先解决 §5.5.7 提出的**交易结构敏感性问题**：

> A3 的距离档筛选是"最简结构下的结论"。策略定位应是"结构 × 距离档"
> 二维联合优化，不能只在最简结构下判定。

**后续子实验必须**：

- 明确当前使用的交易结构假设（stop 类型、止盈类型、时间处理）
- 至少覆盖 2-3 种主流结构做敏感性对照
- rolling vs fixed-window 对照（阶段 4）必须在**最优结构下**做

**否则 §9 主题定位建议不能定稿**。
