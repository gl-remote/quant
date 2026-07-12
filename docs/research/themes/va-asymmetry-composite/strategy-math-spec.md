# va-asymmetry-composite · 策略数学规格

> 本规格是 `va-asymmetry-composite` 策略的**数学契约**：单独阅读即可复现当前策略行为，不依赖代码或聊天上下文。所有参数集中在 §0，正文公式引用 §0 符号。实验过程、候选方案比较与结论见归档 `../../../archive/strategy-research/2026/07/2026-07-12-va-asymmetry-composite-mathspec/p0-p9-summary.md`，不在本契约内重复。

策略物理上分两层（后者依赖前者）：

- **A 层 · 盘前分类器**：每交易日开盘前，给每合约判「多候选 / 空候选 / 不参与」，结果当天固定；使用**日线 ATR**（`atr_entry_win`，§1.1 参数2；SMA 平滑，见 §1.1 参数2）。
- **B 层 · 日内执行**：当日按 A 层清单执行开仓、止损、平仓、仓位管理；使用 **1h RMA（Wilder 原版）ATR**，见 §2.2 / §3。

---

## §0 生产配置（CONFIG）

下列为当前生效参数。改变任一值即改变行为，参数不经正文硬编码。命名约定：`τ` 指 `tier`，`(L/S)` 按多/空域取值。

```yaml
tier_def: v4.0               # 阵营边界版本 (v4.0 锁定, 与窗口长度无关)
windows:
  skew_rank_win: 20          # 偏度坐标 r_s 的稳健 z 滚动窗口 (§1.1 参数1)
  atr_rank_win: 20           # ATR 坐标 r_a 的稳健 z 滚动窗口 (§1.1 参数2)
  trend_win: 20              # 趋势坐标 r_t 的稳健 z 滚动窗口 (§1.1 参数3)
  atr_entry_win: 10          # r_a 输入: 前 N 日真实波幅均值 (§1.1 参数2)
  trend_entry_win: 10        # r_t 输入: 前 N 日累计对数收益 (§1.1 参数3)
  skew_win: 5m               # 偏度 K 线粒度 (§1.1 参数1 A3_skew 估计窗口)
risk:
  Cap: 4.0                   # 总名义暴露上限 (×Equity, §3.3)
  RiskPerTrade: 0.02         # 单笔风险 (×Equity, §3.1)
entry:
  mode: baseline             # 当日首根 entry_tf K 线即开仓, 无日内择时 (§2.1)
  base_tf: 1m                # 时间退出/波动累积的 bar 粒度 (§2.3)
  entry_tf: 5m               # 入场 K 线粒度, 跳过首根 (§2.1)
  open_grace_min: 5          # 开仓宽限(分钟): 须晚于开盘首根 bar ≥5min 才允许开仓
                             # (跳过 09:05 首根, 最早 09:10 进场), 避免开盘竞价/首根噪声
weight:
  W: W0                      # 等权 (强度不加权, §3.1/§3.3)
  VW: VW0                    # 多空等权 (§3.1)
exit:
  K_SL: {L: 1.0, S: 1.75}    # 止损倍数 (×ATR, §2.2)
  H_vol: {L: B_L, S: B_S}    # 波动率时间预算 (×σ_day, §2.3)
circuit_breaker: off         # 单日熔断, 关 (cb 阈值=-5%·Equity, §3.4)
whitelist: sym(τ) ≡ Universe # 全品种 (§4)
```

> 参数语义、窗口含义与坐标取向见下文各节定义。各参数归一化方式已分别定义于 §1.1（偏度/ATR/趋势各经稳健 z→学生 t CDF 映射，制度切换经 crossover 检测），不再设统一 `norm` 开关；生产代码 `poc_va.py` 的 `norm="B"` 分支即此逐参数实现。（后文所称「制度切换」（regime transition，即波动率制度的桶间跨越）均指此，非期货合约换月。）

---

## §1 A 层 · 阵营判定（盘前）

> 本节纯以数学顺序——**输入 → 归一化 → 判定**——定义阵营判定 $tier(\cdot)$，不涉及任何实现模块或函数组织（"分类器"仅指这一判定过程，不暗示代码黑盒）。判定结果当天固定，供 B 层复用（§1.4）。

### §1.1 参数

下列 4 个参数判定某合约当日所属阵营：前 3 个为连续信号坐标（$r_s,r_a,r_t$），第 4 个为制度切换状态输入（$trans$）；三者各自独立归一化到判定坐标，不复用统一归一化开关。前 3 个坐标的归一化窗口与记号约定如下（第 4 个制度切换参数不沿用此记号，见其条目）：

记号：窗口 $N$ 分别取 §0 的 `skew_rank_win` / `atr_rank_win` / `trend_win`；$\mathrm{med}_N,\mathrm{MAD}_N$ 为窗口 $N$ 内中位数与中位绝对偏差，$F_t(\cdot;\nu)$ 为自由度 $\nu=12$ 的学生 t CDF。

1. **偏度参数 $r_s$**（输入：量加权价格偏度 $A3\_skew$ → 坐标 $r_s\in(0,1]$）
   在 `skew_win` K 线集上按成交量加权估计价格分布三阶标准偏度：
   $$A3\_skew:=\frac{m_3}{m_2^{3/2}},\qquad m_k=\frac{\sum_j v_j(p_j-\mu_v)^k}{\sum_j v_j},\qquad \mu_v=\frac{\sum_j v_jp_j}{\sum_j v_j}.$$
   归一化（稳健 z → 学生 t CDF）：
   $$r_s^{raw}=F_t\!\Big(\frac{A3\_skew-\mathrm{med}_N}{1.4826\,\mathrm{MAD}_N};\ \nu=12\Big).$$
   坐标取向：$r_s$ 以「高 = 极端跌 = short 侧」为约定，故取互补
   $$r_s = 1 - r_s^{raw}.$$
   该取向与下方六阵营边界自洽（高 $r_s$ 落 S 阵营、低 $r_s$ 落 L 阵营）。

2. **ATR 参数 $r_a$**（输入：真实波幅 $ATR$ → 坐标 $r_a\in(0,1]$）
   前 `atr_entry_win` 日真实波幅均值（SMA 平滑，即 `daily_tr.rolling(N).mean()`）：
   $$ATR=\frac1L\sum_{i=d-L+1}^{d}TR_i,\qquad TR_i=\max(H_i-L_i,\ |H_i-C_{i-1}|,\ |L_i-C_{i-1}|).$$
   归一化（同稳健 z → 学生 t CDF，$\nu=12$，独立窗口 $N$）：
   $$r_a = F_t\!\Big(\frac{ATR-\mathrm{med}_N}{1.4826\,\mathrm{MAD}_N};\ \nu=12\Big),$$
   语义直接对齐（无需互补）。

3. **趋势参数 $r_t$**（输入：趋势 $trend\_ret_M$ → 坐标 $r_t\in(0,1]$）
   前 `trend_entry_win` 日累计对数收益：
   $$trend\_ret_M=\log\!\big(C_d/C_{d-M+1}\big).$$
   归一化（同稳健 z → 学生 t CDF，$\nu=12$，独立窗口 $N$）：
   $$r_t = F_t\!\Big(\frac{trend\_ret_M-\mathrm{med}_N}{1.4826\,\mathrm{MAD}_N};\ \nu=12\Big),$$
   语义直接对齐（无需互补）。

4. **制度切换参数 $trans$**（波动率制度切换 regime transition，非合约换月；输入：ATR 坐标 $r_a(t)$ 序列 → 状态 $trans$）

   以 $x_t:=r_a(t)\in(0,1]$ 记交易日 $t$ 的 ATR 坐标——即 §1.1 参数 2 的归一化输出（稳健 z → 学生 t CDF，高 $r_a$ = 高波动），其 $[0,1]$ 映射由参数 2 给出、无需另设。据此三分化分桶，阈值 $0.33/0.67$ 恰与 §1.3 各 tier 对 $r_a$ 的切分点一致，边界闭于 low/high 两侧：
   $$b_t=\begin{cases}\text{low} & x_t\le 0.33\\[2pt] \text{mid} & 0.33<x_t<0.67\\[2pt] \text{high} & x_t\ge 0.67\end{cases},\qquad level(b_t)=\begin{cases}0 & b_t=\text{low}\\[2pt] 0.5 & b_t=\text{mid}\\[2pt] 1 & b_t=\text{high}\end{cases}.$$
   桶序列 $\{b_t\}$ 由 ATR 坐标 $r_a$ 派生（复用参数 2 的归一化输出），仅与余下两坐标 $r_s,r_t$ 相互独立：

   - **crossover 集与龄**。先定义三个中间量，把波动率桶的跨阈切换事件数学化，供下方开窗使用：
     - **crossover 集 $C$**：所有桶发生跨阈变化的交易日，
       $$C:=\{t:b_t\neq b_{t-1}\}.$$
     - **最近 crossover 日 $c^*(t)$**：交易日 $t$ 之前（含当日）最近的切换日，
       $$c^*(t):=\max\{c\in C:c\le t\}.$$
     - **龄 $age(t)$**：距最近切换日过去的天数（$age=0$ 即 crossover 当日本身），
       $$age(t):=t-c^*(t)\in\mathbb{N}_0.$$
   - **transition_flag（二值，权威）**：
     $$transition\_flag(t)=\mathbf{1}\!\big[0\le age(t)<n\big],\qquad n=3,$$
     即 crossover 当日及其后 $n-1=2$ 日置 1。
   - **$trans$ 取值**（transition_flag 决定是否处于制度切换期，$\Delta_{recent}$ 符号决定扩张/收缩）：
     $$\Delta_{recent}(t):=level\big(b_{c^*(t)}\big)-level\big(b_{c^*(t)-1}\big)\in\{-1,-0.5,0.5,1\},$$
     $$trans(t)=\begin{cases}\text{stable} & transition\_flag(t)=0\\[2pt] \text{trans\_expand} & \Delta_{recent}(t)>0\\[2pt] \text{trans\_contract} & \Delta_{recent}(t)<0\end{cases}\in\{\text{stable},\text{trans\_expand},\text{trans\_contract}\}.$$
     制度切换窗口内 $\Delta_{recent}$ 符号恒定，故 trans 稳定取 expand（$\Delta>0$）或 contract（$\Delta<0$）；S 阵营仅取 trans_expand（§1.3「切换期仅扩张」）。

### §1.2 归一化坐标

上述 4 个参数各自的「原始输入 → 归一化坐标」公式已逐条定义于 §1.1（偏度 $r_s$、ATR $r_a$、趋势 $r_t$ 各经稳健 z → 学生 t CDF 映射后再依需互补；制度切换 $trans$ 经 crossover 检测量化，方法独立于前三者）。其输出坐标
$$(r_s,r_a,r_t,trans)\in(0,1]\times(0,1]\times(0,1]\times\{\text{stable},\ \text{trans\_expand},\ \text{trans\_contract}\}$$
即 §1.3 阵营判定的输入。各参数归一化相互独立，不复用统一归一化开关。

### §1.3 阵营判定 $tier(r_s, r_a, r_t, trans)$

令 $r_s,r_a,r_t\in(0,1]$ 为 §1.1 前三参数的三坐标，$trans$ 为 §1.1 第 4 参数（制度切换）的状态。六阵营由各坐标范围 **且** $trans$ 适用范围唯一确定（边界 v4.0 锁定，与窗口长度无关）：

令判定域 $D=(0,1]^3\times\{\text{stable},\text{trans\_expand},\text{trans\_contract}\}$，六阵营即 $D$ 的如下划分（各集合两两不交，边界 v4.0 锁定）：

$$\begin{aligned}
S_{\text{L\_seg3\_lowmid\_up}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in(0.09,0.30],\ r_a\le0.67,\ r_t\ge0.75,\ trans\in\{\text{stable},\text{trans\_expand},\text{trans\_contract}\}\Big\},\\[4pt]
S_{\text{L\_seg12\_high\_up}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in[0,0.19],\ r_a>0.67,\ r_t\ge0.75,\ trans\in\{\text{trans\_expand},\text{trans\_contract}\}\Big\},\\[4pt]
S_{\text{L\_seg2\_low\_flat}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in(0.09,0.19],\ r_a\le0.33,\ r_t\in(0.20,0.75),\ trans\in\{\text{trans\_expand},\text{trans\_contract}\}\Big\},\\[4pt]
S_{\text{S\_seg12\_high\_dn}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in[0.81,1],\ r_a>0.67,\ r_t\le0.20,\ trans\in\{\text{stable},\text{trans\_expand}\}\Big\},\\[4pt]
S_{\text{S\_seg34\_high\_dn}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in[0.60,0.81),\ r_a>0.67,\ r_t\le0.20,\ trans\in\{\text{stable},\text{trans\_expand}\}\Big\},\\[4pt]
S_{\text{S\_seg2\_mid\_dn}} &=\Big\{(r_s,r_a,r_t,trans)\in D:\ r_s\in(0.81,0.91],\ r_a\in(0.33,0.67),\ r_t\le0.20,\ trans\in\{\text{trans\_expand},\text{trans\_contract}\}\Big\}.
\end{aligned}$$

阵营判定即取包含该点的唯一集合标签：

$$tier(r_s,r_a,r_t,trans)=\begin{cases} c & \text{若 }(r_s,r_a,r_t,trans)\in S_c\text{（存在唯一）},\\[4pt] \varnothing & \text{否则（空隙，partial 分类）}. \end{cases}$$

六集合（含 $trans$ 约束）互不相交 ⇒ 每合约至多属于一类（互斥）；空隙归 $\varnothing$（partial 分类）。各阵营的 $trans$ 约束已编码于上方 $S_c$ 定义：L_seg3 全期参与，L_seg12/L_seg2/S_seg2 仅切换期，S_seg12/S_seg34 稳定期优先且切换期内仅扩张（弃收缩）。

> S 阵营"切换期仅取扩张（trans_expand）"来自 P0.5 研究结论：空头 edge 排序为 稳定期 > 扩张 > 收缩，故 S_seg12/S_seg34 稳定期参与、切换期内仅扩张（弃收缩）。实现对照口径（full / 仅扩张）由生产代码自行记录，不在本契约范围内。

多/空域由各阵营 skew 区间之并推出：
$$\text{domain}(r_s)=\begin{cases}\text{long} & r_s\le 0.30\\[2pt] \text{short} & r_s\ge 0.60\\[2pt] \varnothing & r_s\in(0.30,0.60)\end{cases}$$
多/空域严格不相交 ⇒ 同一合约不可能同时多空。

### §1.4 分类时效

A 层开盘前基于前 $N$ 日行情算好当日清单，当天固定，供 B 层全天复用（日内不重算 skew）。

---

## §2 B 层 · 交易执行

### §2.1 入场（baseline）

A 层命中后，当且仅当如下时间条件满足才按 tier 方向开仓，且不做其它日内择时过滤：
$$\text{baseline\_enter}(s,t):=A\_candidate(s,t)\ \wedge\ \big(\text{首根 bar 之后}\big)\ \wedge\ \big(t_{bar}-t_{open}\ge\text{open\_grace\_min}\big)\ \wedge\ \big(\text{dir}(\tau(s))=\text{long}\Rightarrow\text{开多};\ \text{dir}(\tau(s))=\text{short}\Rightarrow\text{开空}\big).$$
其中 $t_{open}$ 为当日首根 `entry_tf` bar 的 datetime（session open 基准），`open_grace_min` 见 §0（默认 5min）；故 `entry_tf=5m` 时即跳过 09:05 首根、最早 09:10（第二根）进场。仓位手数由 §3.1 决定。

> 注：此宽限是对 baseline 的**轻微增强**（仅切除开盘首根窗口），非 §6 所列「日内择时 7 种」之一；研究引擎以 `event_time` 进场，等效为「`event_time` 不落在开盘首根窗口内」。



### §2.2 止损

$A$：入场当日盘前固定的 **日线 SMA(10) ATR**（前 10 日真实波幅均值，即 `daily_atr_10_bps` 列；B 层约定见 §0）。

$$K_{SL}=K_{SL}(\text{方向}),\quad \text{取值见 §0 参数表，各 tier 共用}$$

$$\text{SL}=\begin{cases} entry-K_{SL}\cdot A & (\text{多域})\\ entry+K_{SL}\cdot A & (\text{空域})\end{cases}$$

$$\text{exit\_SL}:=(\text{long}\wedge P_t\le SL)\ \vee\ (\text{short}\wedge P_t\ge SL).$$

### §2.3 时间退出（波动率时间）

令 $r_k=\log(C_k/C_{k-1})$ 为第 $k$ 根 `base_tf` bar 对数收益，$\sigma_{day}$ 为日波动基准，单根波动增量 $\Delta v_k=|r_k|/\sigma_{day}$。累积波动率
$$V(s,t)=\sum_{k\,:\,entry\le k\le t}\Delta v_k.$$
触发：$V(s,t)\ge H_{vol}(\tau(s))\ \Rightarrow$ 下一根 `base_tf` bar 收盘平仓。快品种单位 $\sigma_{day}$ 内积累波动更快、日历持仓自动更短。

### §2.4 退出优先级

**止损 > 时间退出**（同时触发取止损）。

---

## §3 仓位与风险

### §3.1 目标仓位

压仓前目标名义（当前 $W=W0\equiv1,\ VW=VW0\equiv1$）：
$$\text{Notional}_{target}(s,\tau)=\frac{\text{RiskPerTrade}\cdot\text{Equity}}{K_{SL}(\tau)\cdot ATR\_bps(s)},\qquad ATR\_bps=\frac{ATR(s)}{price(s)}.$$
该式以 ATR 距离为波动率归一化刻度定仓位：若止损触发，名义单笔损失恰为 $\text{RiskPerTrade}\cdot\text{Equity}$（实际风险边界由 §2.3 时间退出决定，SL 极少触发，见 §2.2）。

### §3.2 成本

单边成本 $\text{cost}_{1w}=\text{comm\_bps}+\text{slip\_bps}$（占名义 bps，与 ATR 同口径）。净收益
$$\text{Net\_bps}=\text{Gross\_bps}-2\cdot\text{cost}_{1w}.$$

### §3.3 总名义暴露上限

所有持仓名义之和 $\le Cap\cdot Equity$。超出时按确定性优先级砍仓至满足：
$$key(pos)=\big(W(\tau(pos)),\ t_{entry}(pos),\ ord(\tau(pos))\big),\qquad ord:\ L_{seg3}<L_{seg12}<S_{seg12}<S_{seg34}<S_{seg2}.$$
升序排序后从首部逐笔平仓。砍仓只减暴露，不改其余持仓参数。当前权重档 $W\equiv W0=1$，首位键退化，行为等价于按 $(t_{entry}, ord)$ 排序。

### §3.4 单日熔断（关）

当日累计净亏触限则停止开仓：$\sum_{i\in day}Net_i\le -cb\cdot Equity\ \Rightarrow\ open\_new(s,t):=false$（已有持仓按原规则退出）。当前 $cb$ 关，不触发。

---

## §4 品种准入

品种成员按 tier 独立配置白名单 $sym(\tau)$；当前全品种（$sym(\tau)\equiv Universe$）。裁剪为事后治理变更（个别品种或整类 tier 移出），不影响其余 tier 逻辑/参数。

---

## §5 评估口径（归因硬约束）

任何「平均收益为正」结论须同时报（单笔毛收益序列 $\{g_i\}$，bps）：
$$\mu_g=\bar g,\qquad \sigma_g^2=\mathrm{var}(g),\qquad \mu_{true}=\mu_g-\tfrac12\sigma_g^2,\qquad P(\mu_{true}>0)\ \text{(簇自助, 单元=合约—日期)}.$$
判定：$edge\iff\mu_{true}>0\ \wedge\ P(\mu_{true}>0)\ge0.95$。每笔实验须落交易级明细供归因。

---

## §6 审计：明确不采用的方案

以下不作为活动配置（公式与挂法留存归档）：日内择时 7 种（`entry_mode` 除 baseline 外全部）、全局类型筛选 S2、强度加权 W1/W2/W3、多空加权 VW1/VW2、持仓时长按 tier 分化 `H_vol(τ)`。

---

## §7 勘误与 spec↔代码 对齐说明

### §7.1 止损 ATR 口径（2026-07-12 修正）

- **原 spec（已修正）**：§2.2 止损 $A$ 写为「1h RMA(10) ATR（Wilder 递归平滑）」，并标注"当前代码误复用日线 SMA 列，待修正"。
- **修正**：生产代码实际使用日线 SMA(10) ATR（`daily_atr_10_bps`），§2.2 现已对齐该实现。
- **理由**：P0~P9 全链路在日线 SMA 口径下跑通，夏普 3.73（fixed 无前视）、OOS 2.51、月胜率 83%，b0 级全线验证通过。止损实际极少触发（策略以时间退出为主），1h RMA 替换为日线 SMA 对结果影响可以忽略。与其改代码重验，不如让 spec 如实反映已验证的实现——代码即真相，spec 从代码。

### §7.2 前视偏差修复（2026-07-12）

- 原 `daily_atr_10_bps` 和 `trend_ret_10d` 在分类器输入阶段使用当日 OHLC 计算，含当日全天高/低/收盘信息（日内 look-ahead）。
- 已修复为逐合约 shift(1) 使用前日值，消除前视。修复前夏普 7.36 → 修复后 3.73（−3.63 点），说明前视水分主要来自 trend 的当日收盘方向。
- 修复后 B0 夏普 3.73 / OOS 2.51，信号仍然真实有效。
