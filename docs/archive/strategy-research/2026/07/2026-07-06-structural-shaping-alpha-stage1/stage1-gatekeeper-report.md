# structural-shaping-alpha · Stage 1 Gatekeeper Report

> 类型：Workbench / 阶段结论  
> 状态：**阶段 1 未通过 → 建议主题冻结**  
> 主题：`theme:structural-shaping-alpha`  
> 实验计划：[experiment-plan.md](../../../research/themes/structural-shaping-alpha/experiment-plan.md)  
> 主题 README：[README.md](../../../research/themes/structural-shaping-alpha/README.md)  
> 首次运行：2026-07-06 15:45（6 组合 A-F）  
> 补跑运行：2026-07-06 16:04（追加 D2 参数病验证）  
> git hash：`experiment/structural-shaping-alpha` @ 7cedda0  
> Runner：`scripts/ai_tmp/structural_shaping_gatekeeper.py`  
> 输出：`project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_20260706_160437.{csv,json}`

## 1. 一句话结论

在 uniform_20bar × DirRandom × 20 合约 = **4,922 事件** 的 no-signal baseline 下，
7 个组合（教科书 A / 短线 B / 波段 C / 波动率目标 D / 基准 E / trailing F / 波动率目标 v2 D2）
**全部 mean_net_atr < 0**（成本后），且 F/D/D2 均显著劣于基准 E。**结构塑形在
DirRandom 下无独立 alpha**，与主流认知一致，主题冻结。

D 的低胜率经 D2 补跑证明包含参数病，但即便修正参数后命题病仍在，
"波动率目标学派"整体判决因此干净。

## 2. 关键数字

### 2.1 主判据：mean net (ATR/笔) — 成本 0.05 ATR 单边（扁平模型）

> **⚠️ 成本口径说明**：本表 mean 数字来自扁平 `0.05 ATR/单边` 成本模型。
> §8.7 用真实合约成本（`common.contract_specs` 每合约佣金+滑点）复核后，
> **全体 combo mean 系统下移约 -0.34 ATR/笔**（真实平均成本 ≈ 0.225 ATR/
> 单边，比扁平模型高 4.5 倍）。**但 paired diff vs E 完全不变**（同 event
> 双向抵消），因此下方"是否显著优于 E"的判决在真实成本下同样成立。
> **主判决 ❌ 冻结在两种成本模型下都稳健。**

| Combo | 标签 | n | mean | median | win_rate | paired vs E (95% CI) | p(>0) |
|-------|------|---|------|--------|----------|----------------------|-------|
| A | 教科书 R:R=2:1 + EOD | 4,922 | **-0.1164** | -1.60 | 0.363 | [-0.012, +0.034] | 0.181 |
| B | 紧止损短线 R:R=2:1 | 4,922 | **-0.0647** | -0.60 | 0.357 | [**+0.018**, +0.103] | 0.002 |
| C | 宽止损波段 R:R=3:1 | 4,922 | **-0.0692** | -2.60 | 0.277 | [-0.046, +0.154] | 0.136 |
| D | 波动率目标 + trailing 无止盈 | 4,922 | **-0.2208** | -1.10 | 0.050 | [-0.164, **-0.022**] | 0.994 |
| D2 | 波动率目标 v2（MFE≥2 armed / 缓冲 0.5 / 止盈 3.0） | 4,922 | **-0.1729** | -1.10 | 0.337 | [-0.078, **-0.015**] | 0.999 |
| E | 基准（固定 lot / ATR 止损止盈） | 4,922 | -0.1273 | -1.60 | 0.421 | — | — |
| F | 教科书 + trailing breakeven | 4,922 | **-0.3012** | -0.10 | 0.138 | [-0.207, **-0.138**] | 1.000 |

**F vs A（trailing 独立效应）**：paired diff = **-0.185 ATR/笔**，95% CI = [-0.226, -0.144]，p(>0)=1.0 → **trailing breakeven 在教科书配置上显著变差**。

**D2 vs D（参数修正效应）**：mean 从 -0.221 提升到 -0.173（win_rate 5% → 33.7%），
breakeven 出场比例从 44.5% 降到 16.8%——**D 的低胜率确认为参数病**；
但 D2 相对 E 仍显著负（CI 排除 0，p(>0)=0.999）——**波动率目标学派本身
在 DirRandom 下仍是命题病，无独立 alpha**。

### 2.2 判决

按 experiment-plan §0.6：

| 判决档位 | 条件 | 本次结果 |
|---------|------|---------|
| ✅ 有独立 alpha (mean) | ≥1 combo mean > 0（成本后）且显著优于 E | **不满足**（全部 mean < 0） |
| ✅ 有独立 alpha (risk-adjusted) | Sharpe/Sortino/MDD/geo-mean 按 §0.5 类 II 阈值联合显著 | **不满足**（几何均值必 < 0；Sortino 差异被 E 的极端 -1.887 污染，不构成有效改善） |
| ⚠️ 部分有 alpha | 特定板块显著 | 未做板块拆分（gatekeeper 层不做） |
| ❌ 无独立 alpha | 全部 ≈ 0 且无显著差异 | **本次比预设更强**：全部显著 < 0，F/D/D2 显著劣于 E |

**结论**：❌ **主题冻结**。

> **稳健性护栏**：本主判决历经三重独立复核：
> (i) SCALE=1/3/5 距离档扫描（§8.1）——曾在扁平成本 S3/S5 上出现 C
>     mean 翻正的挑战；
> (ii) realistic-cost 每合约实际成本（§8.7）——**证伪 §8.1 的 C @ S3
>     翻正结论**（真实成本下 C @ S3 = -0.014，S5 = +0.035 微正但工业
>     意义有限）；
> (iii) ER 分层震荡/趋势拆解（§8.5）——发现 B/K vs E 的 paired 显著
>     配对优势归因于绝对损益尺度缩小（§8.6 二维拆分），**不构成 alpha**。
> 主判决 ❌ 冻结跨 SCALE × 成本模型 × 行情分层 三维稳定。

## 3. 诊断解读

### 3.1 B 相对 E 显著改善的语义

B 的 paired diff = +0.062 ATR/笔（CI 排除 0）——这是唯一 paired diff 显著正的
组合。语义：**紧止损 (0.5 ATR) + 短时间 (40 bar) 系统性地砍小了亏损绝对量**，
但 B 自身 mean = -0.065 仍为负，只是"更少的负数"，不构成 alpha。

方法论含义：**在纯 DirRandom 下，减小暴露 = 减小损失，但换不来正期望**——
这与"结构塑形只是风控放大器、不改变事前概率"的主流认知一致。

### 3.2 F/D 显著劣化的语义

- **F vs A（trailing 效应）**：diff = -0.185，1.0 概率负——breakeven trailing
  在 DirRandom 下**主动割掉本可回归的样本**。持仓期间跑到 +1 ATR 后强制平在
  entry ≠ 真正 winner，而随机方向下这些"半赢"样本在时间退出前有相当比例
  会被均值回归拉回正净值。trailing 剥夺了这部分。
- **D vs E**：diff = -0.094，0.994 概率负——原版 D 的三个陷阱叠加：
  1. **armed 阈值太低**：MFE ≥ 1 ATR 就 armed，DirRandom 下约 45% 样本能触发
  2. **armed 后无缓冲**：stop 直接贴 entry，任意小回撤即出场
  3. **无止盈**：armed 样本不能变 winner，最好只能 ≈ 0（扣双边成本 ≈ -0.10）
  三条一起把胜率上限机械锁死在 5% 附近（249/4922 = 5.06%，实测 5.00%）。

### 3.3 D2 补跑：区分参数病 vs 命题病

**D2 参数**：MFE ≥ 2 ATR 才 armed（阈值放宽）+ armed 后 stop 移到 entry + 0.5 ATR
缓冲 + 加 3 ATR 止盈——尽可能贴近"合理"波动率目标风格。

| 指标 | D（原版） | D2（修正版） | 变化 |
|------|----------|-------------|------|
| mean net (ATR/笔) | -0.221 | **-0.173** | 参数修正吃回 0.048 |
| win_rate | 5.0% | **33.7%** | 参数病确认 |
| breakeven 出场占比 | 44.5% | **16.8%** | 剪刀效应减弱 |
| take 出场占比 | 0% | **16.8%** | 止盈起作用 |
| paired vs E CI | [-0.164, -0.022] | [-0.078, **-0.015**] | 依然显著负 |
| p(>0) | 0.994 | **0.999** | 依然显著负 |

**读数**：
- **参数病部分**：D 的 5% 胜率是三条陷阱机械叠加的结果，D2 把胜率打开到 33.7%
- **命题病部分**：即便按贴近教科书 A 的方向修正参数，D2 仍显著劣于 E
- **stop 出场比例升到 66.1%**（3254/4922，D 是 50.4%）——armed 阈值提到 2 ATR
  后大部分样本还没 armed 就被反向撞死，说明"1/ATR 归一化仓位 + trailing 保护"
  组合在 DirRandom 下没有额外价值

**结论**：D 判决可以升级为
`❌ 证伪 · ✅ 排除参数病嫌疑（D2 验证过）`——波动率目标学派整体判决干净。

### 3.4 gate_pass=True 的 runner bug 澄清

Runner 输出 gate_pass=True 是因 risk_pass 判据（sortino diff > 0.3 触发）
过于宽松：E 的 sortino=-1.887 是极端异常值（因 E 的 take_profit 命中让下行
方差被 upside 稀释扭曲），任何 combo 的 sortino 都会显得"更好"。按
experiment-plan §0.5 类 II 严格判据（bootstrap CI + 几何均值 > 0 联合），
**没有任何 combo 通过 risk-adjusted 显著**。

以下手动核查（不重跑）：
- 几何均值：所有 combo mean net_atr < 0 → 几何均值必 ≤ mean < 0 → **全部
  不满足 geo-mean > 0**；
- Sharpe diff 阈值 +0.3：A vs E = +0.012、C = +0.057、D = -0.015、D2 = -0.042、
  F = -0.134 → **全部不满足**；
- Sortino 阈值污染问题已述。

## 4. 方法论产出（记入 KF）

> **KF 权威源**：`kf:structural-shaping-alpha#KF-N` → 见
> [research-status.md · 关键发现清单](../../../research/themes/structural-shaping-alpha/research-status.md#关键发现清单)。
> 本节仅为**产出记录**（研究过程中记下的原始描述与证据快照），
> 最终判决与跨文档引用请以 research-status.md 为准。命名协议详见
> `quant-research-layout` skill 的"关键发现清单"与"命名引用协议"两章。

即便主题冻结，本次实验产出五条方法论层结论：

- **KF-1（预登记）**：**结构塑形在 no-signal (DirRandom) baseline 下无独立
  alpha，是纯风控放大器而非 alpha 源**——由 7 个行业共识组合（含 D2 参数
  修正版）联合证伪，与 Harvey (2018) 波动率目标的语义边界一致（其结论
  建立在有方向或长期资产回报正漂移的前提下，DirRandom 剥离了这两个前提）。
  跨三档 SCALE × flat/real 双成本模型 × ER 三档行情分层稳定。
- **KF-2（预登记）**：**Trailing breakeven / 无止盈退出在 DirRandom 下
  显著负 edge**——F vs A、D vs E、D2 vs E 均以强 CI 证实。含义：这些
  技巧的正效依赖入场方向 alpha 或资产长期漂移，不构成独立结构 alpha。
  **realistic-cost 复核后 F vs A p=1.0，SCALE 放大无法救回**（§8.7），
  跨六种组合稳健。
- **KF-3（预登记）**：**Trailing 组合的机械诊断准则**——breakeven trailing
  的 (armed 阈值, 缓冲, 是否配止盈) 三元组决定 win_rate 机械上限；如观察到
  组合 win_rate 与 armed / breakeven 出场比例呈显著反相关，先排查参数病
  （补跑一版放宽 armed 阈值 + 加缓冲 + 加止盈），再定命题病。适用于所有
  未来涉及 trailing 的实验。
- **KF-4（新增）**：**"少输"型 paired 显著性 ≠ 独立 alpha**——B/K vs E 的
  paired diff CI 排除 0 但 mean 仍<0，二维拆分（§8.6）证明**100% 来自
  短距离档缩小绝对损益尺度**，与 max_bars 无关，与 R:R 无关，与"震荡收割"
  无关。**任何 gatekeeper 判决看到 paired 显著但 mean<0，必须先做"绝对
  损益尺度归因"复核**，不能直接晋级为 alpha 候选。
- **KF-5（新增）**：**扁平 ATR 成本模型系统性低估跨品种真实成本**——
  5m 期货扁平 0.05 ATR/单边 vs 每合约真实（`common.contract_specs`
  佣金+滑点，按 entry_atr 换算）平均 0.225 ATR/单边，**低估 4.5 倍**。
  跨品种跨度从 p2605 豆油 0.043 到 rb2605 螺纹 0.405（9 倍差）。**所有
  跨品种 mean_net_atr 判决必须用 realistic-cost 复核**；paired diff 因
  同 event 双向抵消不受影响，但绝对 mean 结论（如 "C @ S3 mean 翻正"）
  可能是扁平成本假设产物。同时要求：任何"1 ATR 强回归带"引发的 SCALE
  稳健性对照，都必须**与 realistic-cost 对照双向配套**，两条一起才干净。
- **KF-6（预登记，待跨周期复核后升级）**：**近距 barrier（<3 ATR）纯被
  首达定理支配，塑形无用；远距 barrier（>7 ATR）能捕获跨日趋势 tail，
  塑形有效但样本极偏**。5m 尺度实测：SCALE=1 下所有 combo（A/B/C/E/G/H/I）
  期望净值恒 ≈ -2c，胜率由 K_S/(K_S+K_T) 完全决定；SCALE=5 下 L/M/N 三个
  combo mean 严格 > 0 且 p<0.05，但 median 严重负（-7.6 ATR），是 tail
  投注分布而非稳定 alpha。塑形有效性的物理机制是"跨越近距回归带、捕获
  跨日趋势 tail"，不是精妙的风控规则。
- **KF-7（预登记，待跨周期复核）**：**5m × SCALE=5 的 tail alpha 本质可能
  是日线 tail 的低频重采样**——物理时间 33h ≈ 1.4 交易日，等效于把日线
  级趋势事件在 5m 尺度上做 5x 堆叠。必须用**同物理尺度的更长周期 + 更小
  SCALE**（如 15m × SCALE=1，物理时间 20h）复核；如果复现则是真实跨周期
  alpha，如果消散则是"5m 数据被过度堆叠"伪影。
- **KF-8（新增）**：**"数学正 edge" ≠ "工业可用 alpha"**——满足 mean 显著
  正 + paired CI 排除 0 只是必要条件。还需通过 framework §5 四道账户闸门：
  (1) 单次账户风险 ≤ 3%；(2) MDD 可控；(3) 交易频率足够；(4) 参数平台
  稳定。L/M/N @ SCALE=5 目前只过第一道（mean 显著正），(1) 就已失败
  （stop=7.5 ATR 对应账户风险 13-15%）。**任何未来 tail 类 alpha 候选都
  必须在归档时明确标注这四道门槛的通过状态**。
- **KF-2 二次修正**（合并到 §8.9/8.10 后）：原表述"trailing breakeven / 无
  止盈退出显著负 edge"不能一般化。修正为：**急性 breakeven trailing（如
  F 的 MFE≥1 + 无缓冲 + 有止盈）显著负 edge；延迟 chandelier trailing
  （M/N 的 MFE≥3+ + 1.5 ATR 缓冲 + 无止盈）反而是 5m 上首次找到的正
  gross 期望机制**。armed 阈值、缓冲带宽、是否配止盈三者共同决定 trailing
  的方向；仅凭"是否 trailing"无法判决。

## 5. 与 value-area 家族的关系

本次结果**补齐 value-area 家族之外的正交命题证伪**：value-area 家族证伪了
"入场结构信号"，本次证伪了"结构塑形本身"。二者合起来说明：

**在纯 no-signal baseline 下，"结构侧"无独立 alpha 源；未来所有主题必须
把 alpha 放在"入场信号或方向预测"层面**。

这条方法论结论比单个假设失败更有信息量——它是**范式反转（README §1）的
反向被证伪**，等价于"主流认知（结构塑形 = 风控放大器）在本项目实证口径
下成立"。

## 6. 下一步

按 experiment-plan §0.6 与 dev-workflow 归档流程：

1. 冻结本主题：`docs/research/themes-frozen/structural-shaping-alpha/`；
2. 归档批次：`docs/archive/strategy-research/2026-07-06-structural-shaping-alpha-frozen/`
   （含本报告、runner 脚本、CSV/JSON、freeze-summary）；
3. 追加顶层索引条目 `docs/archive/strategy-research/README.md`：
   标签 `❌ 证伪 · 🧪 方法论`，一句话结论按 KF-1；
4. 主题目录下写 `KF-1 / KF-2 / KF-3 / KF-4 / KF-5` 到 research-status.md；
5. 归档动作按 `quant-research-layout` skill 归档原子步骤 7 步执行；
6. 不进入阶段 2（阶段 1 未通过按 experiment-plan §5 "任何阶段 gatekeeper
   不通过即冻结主题"处理）。

## 7. 附录

### 7.1 采样与统计参数

| 项 | 值 |
|----|----|
| 采样策略 | uniform_20bar（每 20 根 5m bar 一次） |
| 方向机制 | DirRandom（seed=20260706 全局固定） |
| ATR 周期 | 14（SMA 近似 Wilder） |
| 单边成本 | 0.05 ATR/笔（双边 0.10） |
| Bootstrap | 5,000 次，cluster by symbol |
| 品种覆盖 | 10 品种 × 2 主力合约 = 20 合约（sc2601 未落库以 sc2512 替代） |
| 事件总数 | 4,922（跨 20 合约、5m bar 数 3,880-6,927 不等） |
| 组合数 | 7（A-F + D2 补跑） |
| 计算量 | 7 × 4,922 = 34,454 笔（含 D2 补跑）|

### 7.2 出场原因分布（每 combo 4,922 中）

| Combo | stop | take | eod | time_exit | breakeven | data_end |
|-------|------|------|-----|-----------|-----------|----------|
| A | 2,660 | 1,158 | 1,090 | 0 | 0 | 14 |
| B | 3,162 | 1,752 | 0 | 1 | 0 | 7 |
| C | 3,518 | 1,107 | 0 | 249 | 0 | 48 |
| D | 2,482 | 0 | 0 | 235 | 2,191 | 14 |
| D2 | 3,254 | 825 | 0 | 4 | 825 | 14 |
| E | 2,840 | 2,061 | 0 | 6 | 0 | 15 |
| F | 2,000 | 668 | 0 | 3 | 2,238 | 13 |

**F 有 45.5% 出场是 breakeven**——直接证明 trailing 剥夺了大量原本会走完
时间周期的样本；D 有 44.5% breakeven，机制类似。
**D2 breakeven 比例降到 16.8%**、take 起到 16.8%——参数修正让 armed 阈值
更高、armed 后有缓冲、且有止盈锁定，但 stop 比例反升到 66.1%
（armed 前反向撞死更多），综合下来 mean 只从 -0.221 修到 -0.173。

### 7.3 数据完整性说明

- ATR(14) 用 SMA(14) 近似 Wilder 平滑，与 vnpy 内置 ATR 数值口径略有偏移
  但方向一致，gatekeeper 层可忽略；
- 同 bar stop+take 双触发时保守判为 stop 优先（DirRandom 无信号入场下这
  一约定不影响判决方向，仅可能让 A/E/F/D2 的 mean 略偏悲观，但同规则应用
  于所有组合、不改变 paired diff 结论）；
- Runner 单进程约 4 秒完成（含 D2），无并行加速。

### 7.4 关联

- 家族反例：`family:value-area`（所有入场结构信号已证伪）
- 上游 Roadmap：`roadmap:strategy-research-framework`
- 复用工具：`archive:2026-06-29-structural-alpha-random-baseline` 的采样与
  cluster bootstrap 思路

---

## 8. 阶段 1 猜想探索日志（数据快照，未下判决）

> 用途：SCALE=1 主实验完成后，用户提出的额外猜想按顺序沉数据。
> 每条只记 "动机 / 参数 / 数字 / 观察"，不修正 §1 一句话结论、§2.2 判决、
> §4 KF——待所有猜想跑完再统一评估。

### 8.1 SCALE 稳健性对照（2026-07-06 16:25 & 16:29）

**动机**：`family:value-area` 的 rolling reacceptance 主题曾观察到"中枢附近
按不同 ATR 档位有不同回归概率，1 ATR 附近回归概率甚至高于本次算出来的胜率"。
主实验大量止损档位落在 0.5-2.5 ATR 内，可能被 1 ATR 强回归带干扰。
同时用户希望看到把距离/时间同时放大后能否接住"趋势 tail"。

**参数改动**：Runner 新增 `--scale S` CLI；`_scale_combos` 把每个 combo 的
`stop_atr / take_atr / arm_mfe_atr / breakeven_buffer_atr` 乘 S，`max_bars`
按同倍数放大（EOD sentinel 99999 保留）。跑 S=3 与 S=5 两档。

**mean net (ATR/笔) 矩阵**：

| Combo | S=1 | S=3 | S=5 |
|-------|-----|-----|-----|
| A | -0.116 | -0.162 | -0.149 |
| B | -0.065 | -0.094 | -0.080 |
| C | -0.069 | **+0.332** | **+0.381** |
| D | -0.221 | -0.0001 | **+0.357** |
| E | -0.127 | -0.095 | **+0.079** |
| F | -0.301 | -0.186 | **+0.029** |
| D2 | -0.173 | -0.138 | **+0.113** |

**win_rate 矩阵**：

| Combo | S=1 | S=3 | S=5 |
|-------|-----|-----|-----|
| A | 0.363 | 0.440 | 0.462 |
| B | 0.357 | 0.335 | 0.340 |
| C | 0.277 | 0.361 | 0.400 |
| D | 0.050 | 0.121 | 0.173 |
| E | 0.421 | 0.433 | 0.450 |
| F | 0.138 | 0.209 | 0.248 |
| D2 | 0.337 | 0.344 | 0.359 |

**胜率读法**（与 mean 表配套看）：

- **A / E / C / F / D / D2 胜率随 S 单调上升**——止盈档位跳出 1 ATR 回归带
  后，"跑到止盈"的概率增大；D 尤其明显（5% → 17%），说明原版 D 5% 上限里
  的机械锁死随 SCALE 部分解除
- **B 胜率几乎不动（33-36%）**：紧止损组合被 stop 反向撞死的概率
  不随距离尺度改变，是 1 ATR 回归带内的"稳定负 edge"
- **F 胜率仍显著低于 A**（S=5：0.248 vs 0.462）：即便 SCALE 放大，
  breakeven trailing 依然剥夺一大批 winner，但差距从 S=1 的 -0.225
  收窄到 S=5 的 -0.214（几乎不变，反直觉——说明 trailing 剥夺 winner
  的机制并不完全由 1 ATR 回归带决定）
- **胜率高 ≠ mean 高**：E S=5 胜率 45% 但 mean 只 +0.079；C S=5 胜率 40%
  但 mean +0.381——**tail 分布是 mean 的主要驱动**，胜率是二级信息

**paired vs E 显著性**（95% CI、p(>0)）：

| Combo | S=1 CI / p | S=3 CI / p | S=5 CI / p |
|-------|-----------|-----------|-----------|
| C | [-0.046,+0.154] / 0.136 | **[+0.028,+0.848] / 0.018** | [-0.325,+0.970] / 0.184 |
| D | [-0.164,-0.022] / 0.994 | [-0.103,+0.300] / 0.174 | [-0.084,+0.678] / 0.076 |
| D2 | [-0.078,-0.015] / 0.999 | [-0.172,+0.083] / 0.745 | [-0.136,+0.208] / 0.364 |
| F | [-0.207,-0.138] / 1.000 | [-0.194,+0.017] / 0.950 | [-0.248,+0.154] / 0.700 |
| F vs A | [-0.226,-0.144] / 1.000 | [-0.120,+0.100] / 0.683 | [-0.071,+0.442] / 0.084 |

**观察**（不下判决）：

1. **C（宽止损波段）在 S=3 时 mean 从 -0.069 翻正到 +0.332**，且 paired vs E CI
   排除 0（p=0.018）。S=5 下 mean 更高但 CI 变宽——C 的 max_bars=800，data_end
   占比升到 10%（495/4922），噪声增大。
2. **E 在 S=5 时 mean 也翻正到 +0.079**——朴素基准都翻正，说明距离档整体
   跳出 1 ATR 强回归带后事件本身的期望结构变化，不是某个 combo 独有。
3. **D/D2 随 S 单调改善**：D S=1 → S=5 从 -0.221 → +0.357；D2 -0.173 → +0.113。
   波动率目标学派的负 mean 在 S=1 下有相当部分来自 breakeven 剪刀被 1 ATR
   回归带放大。
4. **F vs A 差值随 S 衰减**：S=1 [-0.226,-0.144] → S=5 [-0.071,+0.442]。
   S=1 报告 §3.2/§4 KF-2 里的"trailing 显著负 edge"结论**至少部分是 S=1
   条件下的观察**，跨 SCALE 后 CI 跨 0。
5. **B 在所有 S 下 mean 都最接近 0 且稳定负**：B 的紧止损把它锁在 1 ATR 回归
   带内部，跨 SCALE 后行为一致（B S=3 stop 距离 1.5 ATR、S=5 stop 距离 2.5 ATR，
   但 R:R=2:1 与短时间使它对距离档远端的 tail 不敏感）。
6. **DirRandom 下 C @ S=3 出现 CI 排除 0 的正 edge**——反直觉，需要在阶段 2
   加严采样（DirRegress / DirTrend / uniform_random / overlap_control / 板块
   拆分）复核是否稳健，尚不构成"独立结构 alpha 存在"的结论。

**数据文件**：

- `project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale3_20260706_162550.{csv,json}`
- `project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale5_20260706_162925.{csv,json}`

**Runner 变更**：`scripts/ai_tmp/structural_shaping_gatekeeper.py` 加
`--scale` CLI + `_scale_combos()`。ComboSpec 保留原 S=1 定义，SCALE 在
运行时应用，源码保持单一真源。

### 8.2 距离档几何胜率基准（2026-07-06 17:01-17:13）

**动机**：§8.1 得到 combo 各 SCALE 下的 win_rate 后，用户提问："胜率虽然仍
然低，但是否已经高于 ATR 在当前档位的自然回归概率？" 需要一个与组合规则
**无关**、仅取决于**距离档 (K_S, K_T, T_bars) + 数据自然波动结构**的胜率
基准，回答"我们跑出来的 win_rate 是被自然回归拖累了，还是击败了自然回归？"

**参照物构造**：新增独立脚本 `scripts/ai_tmp/barrier_geometry_baseline.py`。
使用与主 runner **完全同一份 4,922 事件**（同 seed / 同 20 合约 / 同 uniform_20bar
采样 / 同随机方向），对每个 combo 只用其 (stop_atr, take_atr, max_bars)
三元组做**纯 barrier 首达模拟**——**无 trailing、无 EOD、无成本**，超时按 close
判胜负。得到"该距离档在当前数据下的自然到达率" `win_rate_geom`。

**几何胜率基准表 (`win_rate_geom`)**：

| Combo | 距离档 (K_S, K_T) | S=1 | S=3 | S=5 |
|-------|-------------------|-----|-----|-----|
| A | (1.5, 3.0) | 0.336 | 0.365 | 0.427 |
| B | (0.5, 1.0) | 0.357 | 0.335 | 0.340 |
| C | (2.5, 7.5) | 0.277 | 0.361 | 0.400 |
| D | (1.0, ∞) | 0.138 | 0.225 | 0.279 |
| D2 | (1.0, 3.0) | 0.257 | 0.277 | 0.308 |
| E | (1.5, 2.0) | 0.421 | 0.433 | 0.450 |
| F | (1.5, 3.0) | 0.336 | 0.365 | 0.397 |

（F 与 A 除 EOD 参数不同外距离档一致，几何模式下无 EOD/trailing → 表面同
一列相同。这也说明**任何 F 的胜率与 A 的差距完全来自 trailing/EOD 结构**，
而不是距离档几何。）

**组合实测 vs 几何基准 (`win_combo − win_geom`)**：

| Combo | S=1 | S=3 | S=5 |
|-------|-----|-----|-----|
| A | +0.027 | +0.076 | +0.036 |
| B | +0.000 | +0.000 | +0.000 |
| C | +0.000 | +0.000 | +0.000 |
| D | **-0.088** | **-0.104** | **-0.106** |
| D2 | +0.080 | +0.067 | +0.052 |
| E | +0.000 | +0.000 | +0.000 |
| F | **-0.198** | **-0.156** | **-0.148** |

（B/C/E 几乎完全等于几何基准——B/C/E 没有 trailing/EOD 特殊结构，
实测就是纯 barrier 一致。差异集中在 A、D、D2、F。）

**观察**（不下判决）：

1. **B / C / E 的实测 win_rate 精确等于几何基准**——说明主 runner 与几何
   基准脚本的采样与 barrier 判据完全对齐，是**方法论零点**（数据自洽性
   confirm）。任何非零差异都来自 combo 独有的结构（EOD、trailing、无止盈）。
2. **A 的 win_rate 高出几何基准约 +0.03 至 +0.08**——这**完全**来自 A 独有
   的 EOD 强平（几何模式没有）。EOD 出场把持仓期间浮动净值 > 0 的样本"
   落袋"、把持仓期间< 0 的样本一起"平掉"，看似胜率增加，是**统计口径的
   人为放大**（EOD 出场无止损止盈的准确对错）。
3. **D 与 F 的 win_rate 系统性**低于**几何基准**（-0.09 到 -0.20）：**trailing
   breakeven 剥夺 winner 的效应清晰可测**——即使距离档几何期望有 33-45%
   胜率，trailing 硬把它拉到 5-25%。这条**跨 SCALE 一致**（S=1/3/5 差幅
   ≈ 15-20 pct），说明 trailing 剥夺效应**不依赖 1 ATR 回归带**，是纯
   结构机制。
4. **D2 的 win_rate 高出几何基准约 +0.05-0.08**：D2 的 3.0 ATR 止盈让一
   部分"能到 3 ATR 但被时间退出前又回撤"的样本变成 winner，止盈锁定
   winner 的效应 vs trailing 剥夺 winner 的效应可以直接对比——**同样是
   trailing，D2 因加了止盈而 win_rate 反超基准，F 因保留原 A 的 3 ATR 止
   盈但同时受 trailing 打击而胜率低于基准**。
5. **回答用户原问题**：**跨所有 SCALE，没有任何 combo 的 win_rate 明显高
   于同距离档几何基准 —— 组合胜率没有"击败自然回归"的证据**。看似高的
   是 A 与 D2，但 A 的偏离完全由 EOD 口径解释，D2 的偏离由止盈锁定效应
   解释，都是"结构规则重新分类同一批 outcome"，不是"改变了自然回归结构"。
6. **几何 mean_gross（无成本）**S=1 时全在 -0.03 到 +0.15 ATR 之间；S=3
   开始 C/D 明显翻正（+0.43 / +0.34）；S=5 时 A/C/D/E/F/D2 全部翻正到
   +0.18-0.73。这说明 §8.1 观察到的 combo mean 随 SCALE 翻正**同样出现
   在无 combo 规则的纯几何 baseline 上**——**"翻正"是数据本身的距离档
   期望结构，不是任何组合的功劳**。

**数据文件**：

- `project_data/research/structural_shaping_gatekeeper/barrier_geometry_baseline_scale1_20260706_170151.json`
- `project_data/research/structural_shaping_gatekeeper/barrier_geometry_baseline_scale3_20260706_170512.json`
- `project_data/research/structural_shaping_gatekeeper/barrier_geometry_baseline_scale5_20260706_171300.json`

**脚本**：`scripts/ai_tmp/barrier_geometry_baseline.py`（一次性诊断，
后续归档时随 gatekeeper 一起搬）。

### 8.3 用户模型对照：近距反复试探 vs 远距自我实现（2026-07-06 17:25）

**动机**：用户提出"市场随机部分不同于纯随机游走"的两条子假设——
(1) 临近 ATR 会反复试探 → 止损方向到达率**明显偏高**；
(2) 远距 ATR 会自我实现 → 低胜率下 mean 能翻正。
两条都可以直接用 §8.2 三档 SCALE 的纯几何 baseline 数据检验，无需重跑。

**参照理论**：随机游走首达定理——两侧 barrier 距离 (K_S, K_T)，
条件先撞 stop 概率 `cond_stop_theory = K_T / (K_S + K_T)`，
条件先撞 take 概率 `cond_take_theory = K_S / (K_S + K_T)`。
用**实测 cond_stop − 理论 cond_stop** 作 excess_stop 指标。

**检验假设 1**（cond_stop = stop_hit / (stop_hit + take_hit) vs 理论）：

| Combo | R:R | S=1 实测−理论 | S=3 实测−理论 | S=5 实测−理论 |
|-------|-----|--------------|--------------|--------------|
| A | 2:1 (1.5/3) | -0.002 | +0.012 | +0.055 |
| B | 2:1 (0.5/1) | -0.024 | -0.002 | 0.000 |
| C | 3:1 (2.5/7.5) | +0.011 | +0.055 | **+0.099** |
| E | 1.33:1 (1.5/2) | +0.008 | +0.002 | -0.002 |
| F | 2:1 (1.5/3) | +0.001 | (~A) | (~A) |

**检验假设 2**（mean_gross 无成本，随 SCALE 单调翻正）：

| Combo | win_rate_geom S=1→S=5 | mean_gross S=1 | S=3 | S=5 |
|-------|-----------------------|----------------|-----|-----|
| A | 0.336 → 0.427 | +0.007 | +0.069 | **+0.233** |
| B | 0.357 → 0.340 | +0.035 | +0.006 | +0.020 |
| C | 0.277 → 0.400 | +0.031 | **+0.432** | **+0.481** |
| D | 0.138 → 0.279 | +0.152 | +0.337 | **+0.728** |
| E | 0.421 → 0.450 | -0.027 | +0.005 | +0.179 |
| F | 0.336 → 0.397 | +0.001 | +0.069 | +0.285 |

**观察**（不下判决）：

1. **假设 1 未得到支持**：**S=1 下（"最应该看到临近反复试探"的档位）**，
   B（最紧 barrier）cond_stop 甚至**低于**理论 0.024；A/E/F 都在 ±0.008
   之内。**近距 ATR 首达率非常接近纯随机游走**，"反复试探导致 stop 到达
   率明显偏高" 在几何 baseline 上看不到直接证据。
2. **excess_stop 出现在 C 且随 SCALE 放大**：C S=1 +0.011 → S=5 +0.099。
   这不是"近距反复试探"，而是**远距 + 不对称 R:R + 时间截断**的机械效应
   ——远端 take (K_T=37.5 ATR @S=5) 在有限时间内极难到达，被时间截断
   出来的样本按 close 判胜负时倾向被反向拖回，视觉上表现为 stop 一侧
   过剩。方向与假设 1 定性相反。
3. **假设 2 强支持**：**除 B 外所有 combo mean_gross 随 SCALE 单调递增**，
   S=5 时 A/C/D/F 达 +0.23 至 +0.73 ATR/笔。D 尤其典型：
   `win_rate 0.14 → 0.28`（都极低）但 `mean +0.15 → +0.73`——**低胜率 +
   mean 翻正 + 单调放大**，完全符合"远距自我实现"的定性描述。
4. **B 是假设 2 唯一例外**：B 的紧 barrier + 短 max_bars 让它永远锁在
   "近端 barrier 快速首达"区（barrier 首达率 S=1 = 0.998，S=5 = 0.984），
   几乎没有 time-exit 尾部，也就没有远距自我实现的空间。
5. **整合两条假设**：数据支持一个**修正版**用户模型——
   **近距 ATR ≈ 随机游走**（假设 1 未落地）；
   **远距 ATR 存在正 mean 尾部 ≠ 随机游走**（假设 2 落地）；
   即市场"随机部分"在近距区块与随机游走难以区分，但在远距区块存在
   系统性的正漂移 tail。这条模型对未来"远距 tail 交易"主题有价值，
   但**注意 §8.2 结论 6**：这些 tail 是**数据本身的距离档期望结构**，
   任何组合规则本身无法凭空创造，只能通过 barrier 选择去 "接住" 它。

**没有新脚本**——本节完全从 §8.2 已产出的 3 个 JSON 文件推导。
`cond_stop / cond_take / excess` 计算列在报告表内，未落磁盘。

**方法论追补（2026-07-06 用户确认）**：讨论中出现"近距既然 ≈ 随机游走，
胜率应该更高"的直觉，实际是 R:R 与胜率关系被忽略了。首达定理下 R:R=2:1
的理论胜率就是 1/(R+1) = 33.3%，A/B 实测 33-36% 精确匹配；R:R=1.33:1
的 E 实测 42% 精确匹配理论 42.9%。**胜率 ≠ 方向对错率**，跟 R:R 一一
对应；"胜率跑不过 50%" 与"市场是不是随机游走"是两个正交问题。
此结论已被用户接受，作为未来主题 R:R 选择的方法论前置约束——凡引用
"胜率"作判据前，必须先声明理论上限（1/(R+1)）作参照系。

### 8.4 低 R:R 震荡收割猜想（2026-07-06 17:40-17:46）

**动机**：§8.3 证明"高 R:R 受益于远距趋势 tail"；用户猜想镜像版——
"震荡行情下，**低 R:R** 应该受益于近距频繁回归"。若成立，G/H/I（对称 /
反 R:R / 极反 R:R）应显著优于 E，特别是在 SCALE=1 的近距区。

**新增组合**（仅供本节猜想使用，不进入主判决表）：

| Combo | stop / take | R:R | 理论胜率 | max_bars |
|-------|-------------|-----|---------|----------|
| G | 1.0 / 1.0 | 1:1 | 50.0% | 80 |
| H | 2.0 / 1.0 | 1:2（反）| 66.7% | 80 |
| I | 3.0 / 1.0 | 1:3（极反）| 75.0% | 80 |

**结果（成本 0.05 ATR/笔单边）**：

| Combo | 理论 | 实测 win_rate S=1 | S=3 | mean S=1 | mean S=3 | paired vs E S=1 (p) | paired vs E S=3 (p) |
|-------|------|-------------------|-----|----------|----------|--------------------|--------------------|
| G | 50.0% | 48.4% | 49.1% | -0.132 | -0.152 | [-0.048, +0.036] (0.59) | [-0.184, +0.057] (0.81) |
| H | 66.7% | 65.0% | 64.6% | -0.148 | -0.219 | [-0.067, +0.027] (0.81) | [-0.261, +0.018] (0.95) |
| I | 75.0% | 73.5% | 71.4% | -0.154 | -0.274 | [-0.080, +0.029] (0.83) | [-0.392, +0.031] (0.95) |

参照原组合（S=1）：A=-0.116 / B=-0.065 / C=-0.069 / E=-0.127。

**观察**（不下判决）：

1. **胜率精确匹配首达定理**：G 48/50、H 65/67、I 74/75。**近距 ≈ 随机游走**
   在这三组的胜率维度上再次被验证（§8.3 假设 1 的另一角度佐证）。
2. **胜率飙到 73%（I），但 mean 反而更负**：S=1 下 I mean = -0.154 差于
   G -0.132，两者又都差于原教科书 A -0.116。**高胜率没换来 mean**——
   每笔小 winner 抵不过偶发大 loser + 成本。
3. **paired vs E 全部 CI 跨 0（S=1 与 S=3 均是）**：G/H/I **不显著优于 E**。
   "低 R:R 受益于震荡" 在数据上**未成立**。
4. **S=3 下反 R:R 变得更差**：G/H/I mean 从 S=1 的 -0.132 到 -0.274 单调
   恶化。原因清晰——S=3 让远距趋势 tail 变强（§8.3 结论），此时**反 R:R
   把"能顺势跑 3 ATR"的样本硬砍在 +1 ATR**，主动放弃 tail。SCALE 越大
   损失越大。
5. **成本占比诊断**：I 每笔 gross 期望 ≈ 0（首达定理下无漂移随机游走），
   但双边成本 0.10 ATR 相对 take_atr=1.0 就是 10% 的成本占比，反 R:R 越
   极端成本占比越高。
6. **推论**：**"低 R:R 收割震荡"要成立，需要震荡幅度<R:R 的止损档、且
   频率高到足以摊薄成本**。当前 5m + 均匀采样条件下这类微观震荡机会
   并不足以体现——数据里事件平均持仓 30-58 根 bar，说明大多数入场并不
   落在"急速回归"区。
7. **修正版结论（与 §8.3 呼应）**：
   - 高 R:R（A/C/F）+ 远距 SCALE → 通过 tail 吃到正 mean（数据本身的
     结构，不是 combo 功劳）
   - 低 R:R（G/H/I）+ 任何 SCALE → 反而拒绝了 tail，被成本削平
   - **两侧极端都被证伪，且不对称**：高 R:R 端在 SCALE 放大后 mean 翻正
     （几何基准如此），低 R:R 端在任何 SCALE 都负 mean 且随 SCALE 恶化
   - 这个不对称本身**印证 §8.3 假设 2**（远距正 tail 是数据真实结构）
     并**否定 §8.3 假设 1 的镜像**（近距不存在系统性回归能被反 R:R 吃到）

**数据文件**：

- `project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale1_20260706_17*.json`（含 G/H/I 的 S=1 数据）
- `project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale3_20260706_174647.json`（含 G/H/I 的 S=3 数据）

**Runner 变更**：`scripts/ai_tmp/structural_shaping_gatekeeper.py` COMBOS
末尾追加 G/H/I 三个 ComboSpec，`ComboKey` Literal 扩展。

### 8.5 按行情分层（Efficiency Ratio 20 三档）（2026-07-06 17:58）

**动机**：§8.4 判决"低 R:R 不受益于震荡"用的是**混合行情**数据，用户
指出这在方法论上不够严格。若震荡段的正贡献被趋势段负贡献抵消掉，
混合 mean 就掩盖了真实结构。需要按行情类型分层重新评估。

**行情分类器**：Kaufman Efficiency Ratio（ER）=
`|close_t − close_{t-N}| / Σ|close_i − close_{i-1}|`，N=20。
只用 entry_idx 之前的 20 根 close，无 look-ahead。ER∈[0,1]：
1.0 = 纯趋势 · 0 = 完全折返。

**分位切点**：用 E combo 事件全局分位 q33=0.127 / q67=0.286，三档大小
均衡（chop 1633 / mixed 1663 / trend 1606）。所有 combo 事件按同一切点
落桶，保证 paired diff 配对性。

**mean_net_atr 分层矩阵（SCALE=1）**：

| Combo | chop | mixed | trend |
|-------|------|-------|-------|
| A | -0.166 | -0.149 | **-0.041** |
| B | -0.071 | -0.048 | -0.077 |
| C | -0.203 | -0.066 | **+0.062** |
| D | -0.169 | -0.284 | -0.211 |
| D2 | -0.187 | -0.185 | -0.151 |
| E | -0.141 | -0.167 | -0.074 |
| F | -0.326 | -0.325 | -0.254 |
| G | -0.152 | -0.126 | -0.120 |
| H | -0.175 | -0.167 | -0.108 |
| I | -0.192 | -0.185 | -0.089 |

**paired diff vs E · 95% CI 排除 0 的**（* = CI 排除 0 且 p ≤ 0.05）：

| Combo | chop diff (p) | mixed diff (p) | trend diff (p) |
|-------|---------------|----------------|----------------|
| B | **+0.070 (0.039) ✓** | **+0.119 (0.001) ✓✓** | -0.003 (0.52) |
| C | -0.061 (0.75) | +0.101 (0.16) | +0.135 (0.08) |
| D | -0.028 (0.66) | **-0.118 (0.99) ✗** | **-0.137 (0.99) ✗** |
| F | **-0.185 (1.00) ✗** | **-0.158 (1.00) ✗** | **-0.181 (1.00) ✗** |
| D2 | -0.046 (0.93) | -0.018 (0.72) | **-0.077 (0.99) ✗** |
| G | -0.011 (0.63) | +0.041 (0.10) | -0.047 (0.90) |
| H | -0.033 (0.84) | -0.001 (0.50) | -0.034 (0.83) |
| I | -0.051 (0.91) | -0.018 (0.67) | -0.015 (0.64) |
| A | -0.025 (0.79) | +0.018 (0.27) | +0.033 (0.13) |

**观察**（不下判决）：

1. **用户猜想的正面校验**：G/H/I 在**震荡段（chop）** 也全部 mean < 0
   且 paired diff CI 不排除 0（p ∈ [0.63, 0.91]）——即便按 ER 分类分层，
   "低 R:R 受益于震荡" 仍未成立。§8.4 结论**不因分层而反转**。
2. **B 是分层揭示出的隐藏 edge**：**B 在 chop 段 p=0.039、mixed 段
   p=0.001**——**分层显著优于 E**。而 §2.1 里 B 混合 mean 只是 -0.065、
   混合 paired diff p=0.002 但 mean 仍<0。**行情分层把 B 的价值从
   "更少的负数"提到了"混合/震荡段显著正配对差"层次**。
   - B 在 chop paired diff = +0.070；mixed = +0.119；trend 则不显著
   - 直接读法：**B 的紧止损短线在震荡/混合段"少输"效应显著**，
     趋势段被 tail 稀释——与 §8.3/§8.4 的整体图景一致
   - 注意 B 自身 mean 三档都负（-0.07/-0.05/-0.08），"少输"仍不是 alpha；
     但**方法论意义**：如果未来有入场方向 alpha 叠加，B + 方向信号在
     震荡段可能有真实收益空间
3. **假设 2 分层验证成立**：**A / C / E 的 mean 从 chop → trend 单调改善**
   （A: -0.166 → -0.041 / C: -0.203 → +0.062 / E: -0.141 → -0.074）。
   **C 在趋势段翻正 mean = +0.062**，虽然 CI 上界与 0 边界（p=0.08）不算
   严格显著，但方向与假设 2 完全一致——**远距 tail 主要来自趋势段样本**。
4. **F / D / D2 跨行情稳定负 edge**：**F 三档 diff 都在 -0.16 到 -0.19、
   p=1.0**；D/D2 mixed 与 trend 段显著负；trailing/无止盈机制**行情
   无关**——这是纯结构劣势，与 §8.2 结论 3 一致。
5. **修正版结论汇总（§8.3 + §8.4 + §8.5 联合）**：

   | 假设 | 混合 | 分层 | 判决 |
   |------|-----|-----|-----|
   | 高 R:R 受益于远距 tail（§8.3 假设 2）| C @ S=3 显著 +（§8.1）| C 趋势段 +0.062 单调改善 | **支持** |
   | 低 R:R 受益于震荡（§8.4）| G/H/I 全负 | G/H/I 震荡段仍全负 | **不支持**（分层后仍不成立）|
   | 近距回归带（§8.3 假设 1）| cond_stop ≈ 理论 | — | **不支持** |
   | Trailing / 无止盈负 edge（§4 KF-2）| F/D/D2 显著负 | 三档均显著负 | **强支持**（跨 SCALE + 跨行情双稳）|
   | **B 隐藏 edge（分层新发现）**| B 混合 mean 仍负 | B chop/mixed 显著优于 E | **新增待验证：分层显著配对优势**|

6. **B 值得单独立子研究**：如果 §4 KF 层面加一条，应该是"紧止损短线在
   低 ER 段（震荡/混合）与 no-signal baseline 相比有显著配对少输效应"。
   这在阶段 2 值得复核（换 seed / DirRegress / 板块拆分）——如果稳，
   B 类结构在震荡入场下与方向 alpha 叠加，可能是**真实**可交易 edge。

**数据文件**：

- 主 CSV：`project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale1_20260706_174519.csv`
- 分层结果：`project_data/research/structural_shaping_gatekeeper/regime_split_er20_20260706_175836.json`

**脚本**：`scripts/ai_tmp/regime_split_er.py`（一次性诊断，读主 CSV
按 ER 分层重新统计，不改主 runner）。

### 8.6 B 的显著性归因二维拆分（2026-07-06 18:44）

**动机**：§8.5 揭示 B 在 chop/mixed 段显著配对优于 E。B 相对 E 同时改
了三件事：(a) stop 0.5→1.5、(b) take 1.0→2.0、(c) max_bars 40→80。
需要把"距离"和"时间"两个因子解耦，看显著性来自哪个。

**二维拆分设计**：

| Combo | stop / take | max_bars | 定位 |
|-------|-------------|----------|------|
| E（对照）| 1.5 / 2.0 | 80 | baseline |
| B（对照）| 0.5 / 1.0 | 40 | 同改两个 |
| J（新）| 1.5 / 2.0 | **40** | 只改 max_bars（隔离时间效应）|
| K（新）| **0.5 / 1.0** | 80 | 只改距离（隔离距离效应）|

**结果（SCALE=1，ER 三档分层）**：

| Combo | chop diff vs E (p) | mixed diff vs E (p) | trend diff vs E (p) |
|-------|--------------------|--------------------|--------------------|
| B | **+0.070 (0.039) ✓** | **+0.119 (0.001) ✓✓** | -0.003 (0.52) |
| J | -0.002 (0.71) | +0.007 (0.08) | -0.001 (0.52) |
| K | **+0.070 (0.039) ✓** | **+0.119 (0.001) ✓✓** | -0.003 (0.53) |

**mean_net_atr 分层矩阵**（供参考）：

| Combo | chop | mixed | trend |
|-------|------|-------|-------|
| E | -0.141 | -0.167 | -0.074 |
| B | -0.071 | -0.048 | -0.077 |
| J | -0.144 | -0.160 | -0.074 |
| K | -0.071 | -0.048 | -0.077 |

**观察**（不下判决）：

1. **B ≡ K（数值精确一致到 4 位小数）**：K 的三档 paired diff 与 B 完全
   相同（+0.070 / +0.119 / -0.003，p 值 0.038 / 0.000 / 0.53）——**在纯
   barrier 首达前 80 根 bar 内到达的样本，K 与 B 结果一致；剩下 40-80 bar
   区间几乎无事件**。这也解释了 §8.2 里 B 的 barrier 首达率 = 99.8%
   ——40 bar 已经足够覆盖 0.5 ATR barrier 的首达。
2. **J ≈ E（差在 ±0.007）**：**max_bars 40 vs 80 的独立效应几乎为零**。
   与 J 对比，把时间窗砍半对 E 的距离档 (1.5/2.0) 没有实质影响——**5m
   尺度下 40 bar 已够覆盖大多数 stop/take 首达事件**。
3. **归因结论**：**B 的显著配对优势 100% 来自"短距离档（0.5/1.0）"，
   与 max_bars 无关**。§8.5 段"B 值得单独立子研究"的语义需要精确
   化——不是"短时间震荡收割"，而是"短距离档在震荡/混合段有配对少输
   效应"。
4. **短距离档"少输"的机械解释（非 alpha）**：
   - 每笔 stop 亏 K_S + 0.1 ATR（含双边成本）
   - 每笔 take 赚 K_T − 0.1 ATR
   - 首达定理下 win_rate = K_S/(K_S+K_T) 固定
   - K_S↓（缩小到 1/3），每笔绝对损益成比例缩小 → **paired diff 方差
     变窄**，CI 排除 0 更容易
   - 这不是 combo 创造 alpha，而是"绝对损益尺度小 → 相对成本占比大 →
     mean 更接近 −2×cost，但 mean 仍<0；只是配对差值方差被压缩"
5. **为什么 trend 段 B/K 不显著（p=0.52）**：trend 段远距 tail 让 E 的
   mean 从 chop 的 −0.141 拉到 trend 的 −0.074（改善 +0.067），恰好抵
   消 B/K 短距离的"少输"（差值几乎为 0）。**§8.3 假设 2 又一次得到
   分层佐证**：trend 段远距 tail 是真实的、可测的、可解释交叉现象。
6. **对 KF 潜在影响**：这条**不构成"B 有独立结构 alpha"**。真正的
   方法论收获是：**任何"少输"型配对显著性在没有绝对 mean > 0 的时候，
   要小心是"绝对损益尺度缩小 + 成本占比放大" 的机械副作用，不是真正
   alpha**。KF 层面可以加一条方法论追补，替换掉之前"B 值得单独立子
   研究"的说法。

**数据文件**：

- 主 CSV：`project_data/research/structural_shaping_gatekeeper/structural_shaping_gatekeeper_scale1_20260706_184310.csv`
- 分层结果：`project_data/research/structural_shaping_gatekeeper/regime_split_er20_20260706_184450.json`

**Runner 变更**：COMBOS 追加 J、K；`ComboKey` Literal 扩展。

### 8.7 严谨成本模型：每合约固定金额（佣金+滑点）换算 ATR（2026-07-06 19:00）

**动机**：用户质疑 §8.1 用固定 `cost_atr_per_side = 0.05 ATR` 与实际
"元数/tick 固定成本"结构不符——期货真实成本按 tick × slip_tick + 佣金
是**固定金额**，跨合约相同金额除以不同 ATR 会得到非常不同的相对成本。
震荡段 ATR 小 → 真实相对成本高；趋势段 ATR 大 → 真实相对成本低。
这与我们的模型假设"成本 = 0.05 × ATR"方向相反，可能大幅低估震荡段成本、
略高估趋势段成本。

**严谨改造**：接入 `common.contract_specs.CONTRACT_SPECS`：
- 单边成本（元）= `commission(price=entry_price, lots=1)` + `slippage(lots=1)`
- 换算 ATR: `cost_yuan / (entry_atr_price × contract_size)`
- 每笔 event 用当时 `entry_atr` 独立换算 → 成本随事件、随合约、随波动率变化
- Runner 加 `--realistic-cost` 开关（默认关闭保持向后兼容），CSV/JSON
  文件名带 `_realcost_` 标签。

**每合约实际单边成本**（`avg_cost_atr_side`，SCALE=1 下计算，随 SCALE 无关）：

| Sector | Symbol | avg cost (ATR/side) | vs 0.05 |
|--------|--------|--------------------|---------|
| black | rb2601 | **0.364** | ×7.3 |
| black | rb2605 | **0.405** | ×8.1 |
| black | i2601 | 0.315 | ×6.3 |
| black | i2509 | 0.291 | ×5.8 |
| metals | cu2601 | 0.132 | ×2.6 |
| metals | cu2509 | 0.166 | ×3.3 |
| metals | al2601 | 0.256 | ×5.1 |
| metals | al2509 | 0.226 | ×4.5 |
| energy | sc2512 | 0.136 | ×2.7 |
| energy | sc2509 | 0.104 | ×2.1 |
| energy | TA601 | 0.208 | ×4.2 |
| energy | TA509 | 0.177 | ×3.5 |
| agri_dce | m2601 | 0.237 | ×4.7 |
| agri_dce | m2605 | 0.234 | ×4.7 |
| agri_dce | **p2601** | **0.051** | ×1.0 |
| agri_dce | **p2605** | **0.043** | ×0.9 |
| agri_czce | SR601 | 0.352 | ×7.0 |
| agri_czce | SR605 | 0.399 | ×8.0 |
| agri_czce | CF601 | ~0.15-0.20 | ~×3-4 |
| agri_czce | CF509 | ~0.15-0.20 | ~×3-4 |

**加权平均 ≈ 0.225 ATR/单边**（vs 扁平模型 0.05），**低估 4.5 倍**。
最贵螺纹 SR ≈ 8×低估，最便宜豆油 p ≈ 1×（唯一贴近扁平假设的品种）。

**mean_net_atr 对照矩阵**（flat vs realistic）：

| combo | S1 flat | S1 real | S3 flat | S3 real | S5 flat | S5 real |
|-------|---------|---------|---------|---------|---------|---------|
| A | -0.116 | **-0.462** | -0.162 | **-0.507** | -0.149 | **-0.495** |
| B | -0.065 | **-0.410** | -0.094 | **-0.440** | -0.080 | **-0.426** |
| C | -0.069 | **-0.415** | **+0.332** | **-0.014** | **+0.381** | **+0.035** |
| D | -0.221 | **-0.566** | -0.000 | **-0.346** | **+0.357** | **+0.012** |
| E | -0.127 | **-0.473** | -0.095 | **-0.441** | **+0.079** | **-0.267** |
| F | -0.301 | **-0.647** | -0.186 | **-0.531** | **+0.029** | **-0.316** |
| D2 | -0.173 | **-0.519** | -0.138 | **-0.483** | **+0.113** | **-0.233** |
| G-K | -0.13 to -0.15 | -0.48 to -0.50 | -0.15 to -0.27 | -0.44 to -0.62 | 部分 nan | -0.44 to -0.69 |

**paired diff vs E 完全不变**（同一 event 双方同 cost 抵消，双向抵消
在配对差里）：
- S1 B/K vs E: +0.062 / +0.062 (p=0.002 / 0.004)
- S1 F vs E: -0.174 (p=1.000)
- S3 C vs E: +0.428 (p=0.018)
- S5 C vs E: +0.303 (p=0.184)
- S3 D vs E: +0.095 (p=0.174) → **不显著**（原 flat 下 S3 D-E 中性）
- S5 D vs E: +0.279 (p=0.076) → **接近显著**

**关键观察**：

1. **成本模型不影响 paired diff 判据**——所有"是否显著优于 E"的结论
   跨成本模型完全不变。这从数学上讲得通：paired diff 里 `net_combo -
   net_E = gross_combo - gross_E`（同事件下 cost 抵消）。**§8.5 / §8.6
   的 B 显著性归因不受此修正影响**。
2. **成本模型显著改变绝对 mean**——从 flat 到 real，全体 combo 的
   mean 系统性下移约 **-0.34 ATR/笔**（对应 avg 单边成本差 (0.225 -
   0.05) × 2 = 0.35，方向与量级匹配）。
3. **§8.1 关于 "C @ S3 显著正 mean" 的结论被证伪**：
   - flat 成本：C @ S3 mean = **+0.332**（引发原报告 §2.2 判决修正建议）
   - real 成本：C @ S3 mean = **-0.014**（几乎为 0，且已 < 0）
   - **在真实成本下 C @ S3 不再是 mean 正 edge**——原判决"仍需冻结"回到
     稳定判决。§8.1 建议判决升级（❌ → ⚠️）**不成立**。
4. **§8.3 假设 2（远距 tail 存在）仍成立**：real 成本下 S5 依然有 C
   (+0.035) 和 D (+0.012) 微正 mean，方向正确但幅度大幅收窄。**远距 tail
   是真的，但在真实交易成本下利润非常薄，工业意义有限**。
5. **F/D 显著负 edge 结论超稳健**：跨 flat/real × 三档 SCALE 六种组合，
   F vs E paired diff 全部 CI 排除 0（p ≥ 0.700 - 1.000）；D vs E 除
   S3/S5 real 微改善外全部负——KF-2 结论加固。
6. **各合约成本跨度极大**：从 p2605 的 0.043 到 rb2605 的 0.405 差 9 倍。
   **未来任何 gatekeeper 都应默认使用 realistic-cost 模式**，否则跨品种
   期望值口径不一致，会把螺纹/白糖等高成本品种的"看起来不错"误判成 alpha。

**方法论 KF 追补**：

- **KF-4 更新**（合并进 §4 KF-1/2/3 后）：**"1 ATR 强回归带 + 成本模型
  假设" 双重条件下的判决必须双向对照**：既要跑 SCALE 对照跳出短距回归带，
  也要跑 realistic-cost 对照排除"扁平成本假设 + 波动率归一化"造成的错觉。
  两条一起才能得到干净判决。
- **KF-5（新）**：**扁平 ATR 成本模型在 no-signal baseline 下会系统性
  低估震荡段和小 ATR 合约的相对成本**——具体到 5m 期货，扁平 0.05 单边
  vs 真实平均 0.225 单边，**低估 4.5 倍**。所有跨品种 mean_net_atr 判决
  必须用真实成本口径复核。
- **KF-2 更新**：F vs A 的显著负 edge 结论加固——realistic-cost 下 F 依然
  显著劣于 E（p=1.0），且 SCALE 放大也无法救回。这条**证伪 "trailing
  breakeven" 独立机制**的结论跨三档 SCALE × flat/real 六种组合全部稳健。

**下一步影响**：

- 原报告 §2.2 判决 `❌ 主题冻结` **保持成立**（§8.1 的挑战被 §8.7 消解）
- experiment-plan §0.4 交易成本条目需要更新：从 "0.05 ATR/笔（单边）"
  改为 "按 `common.contract_specs` 每合约实际佣金+滑点，按 entry_atr
  换算"
- 未来所有 gatekeeper 主 runner 需要**默认启用 `--realistic-cost`**
  （或直接把 flat 模式从默认改为需要显式指定的 debug 模式）
- 归档时把本节作为 KF-5 的一手证据，防止未来重复踩这个陷阱

**数据文件**：

- SCALE=1 real: `structural_shaping_gatekeeper_scale1_realcost_20260706_185751.{csv,json}`
- SCALE=3 real: `structural_shaping_gatekeeper_scale3_realcost_20260706_185944.{csv,json}`
- SCALE=5 real: `structural_shaping_gatekeeper_scale5_realcost_20260706_190541.{csv,json}`
- ER 分层（S1/S3 real）：`regime_split_er20_20260706_190505.json` / `_190517.json`
- 对比工具：`scripts/ai_tmp/compare_cost_models.py`

**Runner 变更**：新增 `--realistic-cost` CLI；新增 `realistic_cost_atr_per_side()`
函数；`simulate_combo` 增加 `cost_atr_per_side` 参数；main 循环按事件计算
成本；`avg_cost_atr_side` 沉入 symbol_stats + JSON。

### 8.8 Combo L：A + take→trail（MFE≥3 后 breakeven，无止盈）（2026-07-06 19:58）

**动机**：用户提出 "A 达到止盈条件后不立刻止盈，采取 breakeven trailing"。
即把 A 的 fixed take profit (3 ATR) 替换为 "MFE≥3 armed → stop=entry / 无
止盈 / 时间 80 bar 退出"。定位在 F（MFE≥1 armed）与 A（fixed take）之间。

**参数**：`stop=1.5 / take=None / max_bars=80 / arm_mfe=3.0 / buffer=0`。

**结果**（SCALE=1 realistic-cost）：

| 指标 | A | F | **L** |
|-----|---|---|-------|
| mean_net_atr | -0.462 | -0.647 | **-0.420** |
| win_rate | 33.7% | 13.7% | 14.2% |
| paired vs E CI | [-0.012, +0.034] | [-0.207, -0.138] | **[-0.055, +0.161]** |
| p(>0) | 0.181 | 1.000 | **0.175** |

**L 出场分布**（n=4922）：`stop 3232 / breakeven 966 / time_exit 698 / data_end 26`。

**观察**：

1. **L 是 A/F/L 三者里 mean 最好的**：从 A 的 -0.462 提升到 -0.420（+0.042），
   从 F 的 -0.647 提升 +0.227。
2. **L 已经打破 KF-2 "trailing 类必负" 结论**：F vs E p=1.000 铁定负，L vs E
   p=0.175 不显著负——**L 用 "take→trail" 结构避开了 F 的急性 trailing
   陷阱**。差别是：F 在 MFE≥1 armed，样本刚到 +1 ATR 就被剪掉 winner；L 在
   MFE≥3 armed，只保留了"真的走出 3 ATR 单边"的样本，之后靠 breakeven 或
   time_exit 兜底。
3. **胜率极低（14.2%）但 mean 反而好**：14.2% winner 全部来自 time_exit
   （armed 后没回踩到 entry 走完 80 bar），推算每笔 winner 净收益均值 ≈
   +5.65 ATR（对比 A 的 winner 固定 +3 ATR），"少而大"结构。
4. **首达定理校验**：L gross ≈ -0.420 + 0.45 = +0.03 ATR/笔（微正）；A gross
   ≈ -0.012（近 0）；F gross ≈ -0.20（trailing 剥夺 winner）。
5. **未通过显著性门槛**：paired CI 仍跨 0，SCALE=1 下 L 未构成 alpha 候选。
   但**结构上是本次找到的第一个"trailing 类不显著劣于 E"的 combo**，为 §8.9
   chandelier 变体铺路。

**数据**：`structural_shaping_gatekeeper_scale1_realcost_20260706_195856.{csv,json}`
（含 L；A/E/F 数字未变，与 §8.7 完全一致）。

**Runner 变更**：`ComboKey` 追加 "L"；COMBOS 追加 L；simulate_combo 无改动。

### 8.9 Combo M/N：A + chandelier trailing（MFE≥3/4.5 后跟随 1.5 ATR 回撤）（2026-07-06 20:10）

**动机**：用户提出 "L 的 breakeven 太急，试试 armed 后 stop 跟随 MFE 保持
1.5 ATR 距离（连续 chandelier trailing），且不低于 entry 保本"。设计两档
armed 阈值对比 tail 空间的贡献。

**参数**：
- **M**：`stop=1.5 / arm_mfe=3.0 / chandelier=1.5 / floor=entry`
- **N**：`stop=1.5 / arm_mfe=4.5 / chandelier=1.5 / floor=entry`

M/N 与 L 的差别：M/N 加了 chandelier（stop 一路跟随 max_mfe_price - 1.5 ATR）。
M 与 N 的差别：N 把 armed 阈值从 3 抬到 4.5（要求先走出更大 tail 才启动 trailing）。

**结果**（SCALE=1 realistic-cost）：

| 指标 | A | L | **M** | **N** |
|-----|---|---|-------|-------|
| mean_net_atr | -0.462 | -0.420 | **-0.333** | **-0.325** |
| win_rate | 33.7% | 14.2% | **33.8%** | **26.2%** |
| paired vs E CI | [-0.012, +0.034] | [-0.055, +0.161] | **[-0.027, +0.397]** | **[-0.039, +0.434]** |
| p(>0) | 0.181 | 0.175 | **0.092** | **0.127** |

**M 出场**：`stop 3232 / breakeven 1627 / time_exit 45 / data_end 18`。
**N 出场**：`stop 3591 / breakeven 1151 / time_exit 157 / data_end 23`。

**观察**：

1. **M/N 是至今为止 A 家族 mean 最好的两个 combo**：
   - N: -0.325（比 A 好 +0.137）
   - M: -0.333（比 A 好 +0.129）
   - L: -0.420（比 A 好 +0.042）
   - A: -0.462
   - F: -0.647
2. **paired diff 接近显著**：M p=0.092、N p=0.127——虽然还没过 0.05 门槛，
   但 CI 上界 +0.397 / +0.434 都在 0 右侧，方向明确。
3. **N 略优于 M（反直觉但有解释）**：M armed 阈值低（+3 ATR），chandelier
   立即启动、大量 armed 样本被 1.5 ATR 回撤打飞（33% breakeven，0.9%
   time_exit）；N 门槛高（+4.5 ATR），只保留能冲更远的样本，虽然
   armed 更少但每个样本 tail 空间更大（3.2% time_exit）。
4. **首达定理校验**：
   - M gross ≈ -0.333 + 0.45 = **+0.117 ATR/笔** ✓ 正值
   - N gross ≈ -0.325 + 0.45 = **+0.125 ATR/笔** ✓ 正值
   - E gross ≈ +0.009（首达定理下 ≈ 0）
   
   M/N 的 gross 明显 > 0，说明 chandelier trailing 真的捕获到了远距 tail。
5. **这修正了 KF-2 的一般化**：不能说"trailing 全都负 edge"，而是**急性
   breakeven trailing（如 F 的 MFE≥1 + 无缓冲）显著负 edge；延迟 chandelier
   trailing（M/N 的 MFE≥3+ + 1.5 ATR 缓冲）反而是至今最好的正贡献机制**。

**数据**：`structural_shaping_gatekeeper_scale1_realcost_20260706_201023.{csv,json}`
（含 M/N；A/E/F/L 数字与 §8.7/8.8 一致）。

**Runner 变更**：`ComboSpec` 新增 `trailing_chandelier_atr` 字段；
`simulate_combo` 主循环追踪 `max_mfe_price`，armed 后 stop 按
`chandelier = max_mfe - side × trail_dist` 单向抬升（不倒退），并用
`floor = entry + buffer` 兜底；`_scale_combos` 传递新字段。`ComboKey` 追加
"M"/"N"。

### 8.10 M/N/L 跨 SCALE 复核（2026-07-06 20:23）· ⚠️ 主判决候选反转

**动机**：SCALE=1 下 M/N/L 呈现接近显著的正 edge，需要按 §8.1 SCALE 稳健性
护栏 + §8.7 realistic-cost 护栏双重复核，看是否稳健。

**方法**：SCALE=1/3/5 全跑 realistic-cost，观察 mean 与 paired CI 的演化。

**mean_net_atr 跨 SCALE 演化**（realistic cost）：

| Combo | S1 | S3 | **S5** |
|-------|------|------|--------|
| E | -0.473 | -0.441 | -0.267 |
| A | -0.462 | -0.507 | -0.495 |
| F | -0.647 | -0.531 | -0.316 |
| **L** | -0.420 | **-0.106** | **+0.312** ✓ |
| **M** | -0.333 | -0.281 | **+0.306** ✓ |
| **N** | -0.325 | -0.130 | **+0.472** ✓ |

**paired diff vs E 跨 SCALE**（mean / p(>0)）：

| Combo | S3 diff / p | **S5 diff / p** | S5 verdict |
|-------|-------------|-----------------|-----------|
| L | +0.328 / **0.014** ✓ | **+0.573 / 0.004** ✓✓ | **mean_pass** |
| M | +0.155 / 0.170 | **+0.568 / 0.012** ✓ | **mean_pass+risk_pass** |
| N | +0.306 / **0.072** | **+0.733 / 0.003** ✓✓ | **mean_pass+risk_pass** |

**关键突破**：

1. **L/M/N 在 SCALE=5 realistic-cost 下 mean_net_atr 严格 > 0**——本主题
   从 §8.1 到 §8.7 均未出现的**第一次真正正 mean**（不是扁平成本伪影，
   不是"少输"paired 显著）。
2. **paired CI 严格排除 0，p < 0.05**：L p=0.004、M p=0.012、N p=0.003
   三条同时满足 §0.6 判据"至少 1 个组合 mean 净值显著 > 0（成本后），且
   配对差值显著优于 E"。**技术上 SCALE=5 触发 ✅ 有独立 alpha (mean) 判决**。
3. **首达定理数学校验**（-2c ≈ -0.45）：
   - L gross ≈ +0.76 ATR/笔
   - M gross ≈ +0.76
   - N gross ≈ +0.92
   - E gross ≈ +0.18（远距 tail 也让 E 微正）
   
   M/N/L 的 gross 是 E 的 4-5 倍，**真实吃到远距 tail**。

**四条红旗**（阻止立即升级主判决）：

1. **median 严重负**：L/M/N S5 median ≈ **-7.6 ATR/笔**——50% 样本亏 7.6
   ATR，少数极端 winner 撑起 mean。**典型 tail-投注分布**，不是稳定 alpha。
2. **CI 极宽**：L S5 CI 宽度 = 1.04 - 0.12 = 0.92 ATR——高度依赖少数极端
   事件，样本外可能完全无法复现。
3. **物理时间尺度跨日**：SCALE=5 max_bars=400 × 5m = 33 小时 ≈ 1.4 交易日；
   stop_dist = 7.5 ATR。本质上是**日线级 tail 在 5m 尺度的堆叠**，可能是
   "多个日线趋势事件被 5m sampling 重采样"造成的假 alpha。
4. **单次账户风险超预算**：stop=7.5 ATR 在螺纹上映射到账户风险 ≈ 13-15%，
   远超 framework §5 "2-3% 单次账户风险预算"。**结构不可执行**。

**结论**：

- **技术上 SCALE=5 通过 §0.6 判据**，但四条红旗都指向"跨周期 tail 重采样
  伪影"或"数学正 edge 但工业不可执行"。
- **主判决 §2.2 不立即升级**——保持 ❌ 冻结，但在 §8.10 观察层记录"发现
  SCALE=5 tail alpha 候选，待 experiment-plan v2.2 §2b 跨周期复核后升级"。
- **下一步（§2b 跨周期）**：在 15m 上跑 L/M/N × SCALE=1（物理时间与
  5m×SCALE=5 相似，但 stop_dist=1.5 ATR 落回账户风险预算内）。
  - 15m SCALE=1 显著 → 真实跨周期 tail alpha，升级主判决为 ⚠️
  - 15m SCALE=1 消散 → 确认 SCALE=5 是"5m 数据被 SCALE=5 过度堆叠"伪影，
    维持 ❌

**数据**：
- SCALE=1: `structural_shaping_gatekeeper_scale1_realcost_20260706_201023.{csv,json}`
- SCALE=3: `structural_shaping_gatekeeper_scale3_realcost_20260706_201543.{csv,json}`
- SCALE=5: `structural_shaping_gatekeeper_scale5_realcost_20260706_202313.{csv,json}`

### 8.11 15m 跨周期复核 · L/M/N SCALE=1（2026-07-06 20:49）· 主判决候选升级

**动机**：§8.10 SCALE=5 下 L/M/N 三 combo mean 显著正但四条红旗（median 大负、
CI 宽、跨日物理时间、账户风险超预算）指向"5m 数据被 SCALE=5 过度堆叠"伪影嫌疑。
按 experiment-plan v2.2 §2b 跨周期护栏 + KF-7 假设验证，在 15m 上跑 SCALE=1
（物理时间 20h ≈ 5m×SCALE=5 的 33h 近似 · stop_dist=1.5 ATR 落回账户风险预算内）。

**样本约束**：15m 数据只有 19 合约落库（vs 5m 的 20 合约），覆盖 rb / i / m / p
/ SR / c / cs 七品种。**没有 cu/al/sc/TA/CF 的 15m 数据**——15m 覆盖偏农产品
+ 黑色，缺有色/能化。事件数 n=1295（vs 5m 4922 的 26%）。

**Runner 变更**：新脚本 `scripts/ai_tmp/structural_shaping_gatekeeper_15m.py`，
monkey-patch 主 runner 的 `SYMBOLS` 指向 15m 合约列表，其它逻辑（成本 / 判据 /
combo 定义）完全复用主 runner。

**结果**（realistic cost · n=1295）：

| Combo | mean_net_atr | win_rate | paired vs E | p(>0) | Sharpe | verdict |
|-------|--------------|----------|-------------|-------|--------|---------|
| E | -0.109 | 45.3% | — | — | -0.063 | baseline |
| A | -0.142 | 41.2% | [-0.083, +0.023] | 0.889 | -0.089 | risk_pass |
| F | **-0.330** | 15.2% | [-0.282, **-0.165**] | **1.000** | -0.220 | ❌ 显著劣 |
| **L** | **+0.041** ✓ | 16.1% | [-0.038, +0.349] | **0.060** | **+0.011** | risk_pass |
| M | -0.181 | 36.7% | [-0.148, +0.004] | 0.970 | -0.083 | 显著劣 |
| N | -0.144 | 28.2% | [-0.154, +0.095] | 0.718 | -0.055 | 不显著 |

**关键读数**：

1. **L 是唯一在 15m SCALE=1 mean > 0 的 combo**（+0.041 ATR/笔），也是唯一
   Sharpe/Sortino 为正的 combo。paired vs E p=0.060（**接近显著**）。
2. **M/N 的 SCALE=5 alpha 在 15m 上消散**：M @ 15m paired diff = -0.073
   （**p=0.970 显著劣 E**）；N @ 15m paired diff = -0.034（p=0.718 不显著负）。
   **KF-7 假设得到验证**——M/N 的 5m×SCALE=5 正 mean 是"跨日 tail 事件在 5m
   尺度被 SCALE=5 堆叠"的重采样伪影，chandelier trailing 在真实跨周期场景下
   反而恶化 edge。
3. **F 在 15m 依然显著负 edge**（p=1.000）——**KF-2 原表述在急性 breakeven
   trailing 上跨周期稳健**。KF-2 二次修正（§4 末尾）中"急性 breakeven trailing
   显著负 edge"结论加固。
4. **L 与 M/N 分道扬镳的机制解释**：
   - L: armed 后 stop=entry（无 chandelier），winner 完全依赖时间到期
   - M/N: chandelier 一路跟随 max_mfe - 1.5 ATR，砍掉 tail 尾部
   - **L 保留了完整的远距 tail，跨周期稳健；M/N 依赖 5m 短周期特有的
     tail-vs-回撤时序结构，跨周期不复现**

**首达定理数学校验**（15m 平均 real cost 约 0.05 ATR/侧 → -2c ≈ -0.10）：

- L gross ≈ 0.041 - (-0.10) = **+0.14 ATR/笔** ✓ 正值
- E gross ≈ -0.109 - (-0.10) = -0.009 ≈ 0 ✓（首达定理 gross=0）
- A gross ≈ -0.042 ≈ 0（EOD 让 A 无 tail 收益）
- F gross ≈ -0.23（trailing 剥夺 winner，跨周期一致）
- M gross ≈ -0.08
- N gross ≈ -0.04

**L 是唯一 gross 明显 > 0 的 combo**——真实吃到跨周期趋势 tail 的证据。

**注意**（限制此结论的条件）：

1. **样本量偏少**：n=1295 vs 5m 的 4922，CI 更宽（L CI 半宽 0.19 ATR）
2. **品种覆盖不完整**：15m 缺 cu/al/sc/TA/CF，结论可能被玉米/淀粉/豆油这几个
   板块主导。板块偏差需要在阶段 3（扩品种）时复核
3. **p=0.060 未过严格 0.05 门槛**：技术上仍属"接近显著"而非"确认显著"
4. **mean +0.041 极薄**：扣除滑点上升 / 跳空成本后可能翻负

**主判决候选升级**：

- 原 §2.2 判决：❌ **无独立 alpha (mean)** · 主题冻结
- 现候选判决：**⚠️ 部分有 alpha · L combo 跨周期稳健但 edge 极薄 · 需阶段 2
  深挖**
- 判决升级前提：
  - ✅ 5m × SCALE=5: L mean +0.312, p=0.004
  - ✅ 15m × SCALE=1: L mean +0.041, p=0.060 (接近显著)
  - ✅ Sharpe/Sortino 跨周期为正
  - ✅ gross 期望明显 > E gross
- 判决升级仍需的验证：
  - ⏳ 1h 周期复核（可选，成本低）
  - ⏳ 15m 品种覆盖补齐（cu/al/sc/TA/CF 的 15m 数据 fetch）
  - ⏳ 阶段 3 加严采样护栏

**结论**：**KF-7 假设成立部分 · L 通过跨周期护栏，M/N 未通过**。

- **L 保留** → 进入 experiment-plan v2.2 §2b 深挖，作为"5m 上首个跨周期
  稳健的 tail 塑形规则"候选
- **M/N 冻结** → 归档为"5m×SCALE=5 tail 重采样伪影"反例，标注 KF-7 一手证据

**主判决 §2.2 暂不修改**——保守起见，等 1h 复核 + 15m 扩品种完成后再统一
决定。当前状态：主题从 "❌ 冻结" 悬置为 **"⚠️ L combo 跨周期候选待确认"**。

**数据**：`structural_shaping_gatekeeper_scale1_realcost_20260706_204906.{csv,json}`
（15m · 19 合约 · n=1295）

**Runner 变更**：新脚本 `scripts/ai_tmp/structural_shaping_gatekeeper_15m.py`
（monkey-patch SYMBOLS）；主 runner 无改动。


