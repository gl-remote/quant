# Stage 0 · 数据与口径校验报告

> 主题：volume-spike-regime-shift
> 日期：2026-08-05
> 分支：experiment/volume-spike-regime-shift
> 脚本：`docs/workbench/volume-spike-regime-shift/scripts/stage0_data_audit.py`
> 原始数据：`project_data/research/volume-spike-regime-shift/stage0_audit.json`

---

## 1. 数据覆盖

- 扫描 `project_data/market_data/csv/*.1h.csv`：**35** 个 1h 合约；
- 解析成功 35，通过纳入条件（≥420 bar 且能取到 `CONTRACT_SPECS`）：**26** 个；
- 拒绝 9 个，全部为 `n_bars<420`（2605/2501/2505 等远月或近交割合约，样本不足）。

按品种前缀：

| prefix | 合约数 | 可用 bar | 独立 session |
|---|---:|---:|---:|
| CF | 2 | 967 | 141 |
| SR | 1 | 403 | 59 |
| TA | 2 | 967 | 141 |
| al | 2 | 1064 | 144 |
| c | 3 | 2204 | 320 |
| cs | 3 | 2198 | 319 |
| cu | 2 | 1064 | 144 |
| i | 2 | 822 | 120 |
| m | 3 | 2204 | 320 |
| p | 3 | 1246 | 182 |
| rb | 1 | 403 | 59 |
| sc | 2 | 1304 | 144 |

- 覆盖 **12 个 prefix**，满足"≥8 prefix"门槛；
- 总计可用 bar 14 846，独立 session 约 2 093（按合约×日聚合）；
- 板块覆盖农产品（m/c/cs/p/SR/CF/TA）、黑色（rb/i）、有色（cu/al）、能源（sc）。

---

## 2. Z 分布实测

trailing N=20、不含当根：

```
n=14846
mean=0.094  std=1.314
skew=2.858  excess kurtosis=16.750
```

分位数：

| 分位 | Z |
|---|---:|
| p1 | -1.482 |
| p5 | -1.183 |
| p50 | -0.248 |
| p95 | 2.504 |
| p99 | 4.942 |
| p99.9 | 9.094 |

**观察**：

1. **非正态、强右偏重尾**。skew=2.86、超额峰度=16.75，远偏离正态；
2. **中位数 -0.25 而非 0**——trailing 20 窗口内若近期出现一根放量 bar，会同时抬高 $\mu^V$ 和 $\varsigma^V$，导致其后若干 bar 的 $Z$ 被压成负值；这是"自掩蔽 + 窗口短"的预期表现；
3. **左右极端不对称**：$P(Z\ge5)\approx0.97\%$，$P(Z\le-5)=0$。缩量事实上不可能在 z-score 口径下达到 -5，因为成交量有下界 0。

---

## 3. 阈值命中率（实测 vs 正态参考）

| $z_0$ | $\hat P(Z\ge z_0)$ | $\hat P(Z\le -z_0)$ | 正态 $P^+$ | 重尾倍率 | n_events+ | n_clusters+ | 档位 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1.5 | 10.50% | 0.90% | 6.68% | 1.57× | 1 559 | 1 118 | full |
| 2.0 | **7.27%** | 0.03% | 2.28% | 3.19× | 1 079 | **855** | full |
| 2.5 | 5.02% | 0.01% | 0.62% | 8.08× | 745 | 623 | full |
| 3.0 | 3.56% | 0.00% | 0.13% | 26.4× | 528 | 464 | full |
| 4.0 | 1.81% | 0.00% | 0.003% | **572×** | 269 | 251 | full |
| 5.0 | **0.97%** | 0.00% | 2.87e-7 | **33 838×** | 144 | **137** | medium |

（cluster key = `(symbol, session_date)`；n_clusters 直接是独立观察数估计。）

**结论**：

- 所有阈值档 $n_{\text{clusters}}\ge 30$，**无需降级为描述性档**；
- $z_0=5.0$ 命中 144 事件 / 137 个独立 cluster，按 spec §2.5 属于"信度中等"档（30–200），可做 bootstrap CI 但不单独作硬证据；
- $z_0=4.0$ 有 251 cluster，意外地跨过 200 门槛，可纳入正式推断；
- 之前担心 5σ 在正态下几乎不可能，实测**命中率 0.97%**，比正态高 **3.4 万倍**——成交量的重尾性质完全验证了"必须实测，不靠正态推算"的判断。

---

## 4. 口径手验

抽样手验（DCE.m2601 前 25 行）：

- rolling mean/std 用 `Volume.rolling(20).mean().shift(1)`，`Z=(V - μ)/σ`；
- 第一根非 NaN Z 出现在第 21 行（与 `min_periods=20` 一致）；
- ATR SMA(TR,14) 口径与 structural-shaping gatekeeper 一致（未在本脚本计算，Stage 1 复用同款实现）；
- session_date 直接取 `datetime.date`：1h 周期下夜盘 bar 的 datetime 自然落到次日凌晨，不需要额外映射；
- baseline 带 $|Z|<0.5$ 覆盖（待 Stage 1 精确统计）约 40–45%，与预期 38% 相近。

---

## 5. 判决与下一步

### 5.1 Stage 0 判据复核

| 判据 | 结果 |
|------|------|
| ≥20 合约 | ✅ 26 |
| ≥8 prefix | ✅ 12 |
| 口径手验 | ✅ |
| 各阈值实测命中率 | ✅ 见 §3 |
| 预判哪些档位能正式推断 | ✅ 1.5/2.0/2.5/3.0/4.0 full；5.0 medium |

**Stage 0 通过，进入 Stage 1。**

### 5.2 对主规格的影响

- **主规格 $z_0=2.0$ 有 855 个独立 cluster**，样本充足；
- 极端档 $z_0=5.0$ 样本可用（137 cluster），但按 spec §2.5 标记为"信度中等"；
- 缩量侧由于 $P(Z\le -2)\approx 0.03\%$（全样本仅约 5 根 bar），**r1 缩量对称对照事实上不可行**。Stage 3 的缩量分析要么取消，要么换成较松的 $Z\le-1.0$（命中率 0.90%，约 133 events）；
- $Z$ 的右偏意味着直接用 $Z$ 做五分位切桶时，Q5（最高五分位）会非常宽而 Q1 非常窄；五分位图仍可画，但解读时注意 Q5 内部不均质。

### 5.3 Stage 1 待办

1. 对 26 个合约、$z_0=2.0$ 主规格、$h\in\{1,3,6,12,20\}$ 计算 6 个核心度量（$r^{(h)}$、$\sigma^{(h)}$、$|r|^{(h)}$、三组 barrier × 三方向 hit、$H^{(20)}$）；
2. spike vs baseline($|Z|<0.5$) 点估计 + cluster bootstrap CI；
3. 按 prefix 拆分，初步看跨品种 sign 一致性；
4. Stage 1 判据：≥2 度量 $|\Delta|>0.2$ baseline SD、≥5 prefix sign 一致、$n_{\text{clusters}}\ge200$。

### 5.4 未决项（来自 spec §8）更新

- **去时段化仍不做**，但 Stage 1 增加一个诊断：spike 事件按小时-of-day 的分布，检查是否集中在开盘 bar；
- **缩量对照改为 $Z\le-1.0$**（Stage 3 执行），否则无样本。

---

## 6. 复现命令

```bash
uv run python docs/workbench/volume-spike-regime-shift/scripts/stage0_data_audit.py
```

输出：

- `project_data/research/volume-spike-regime-shift/stage0_audit.json`（含每合约完整审计记录）
- 控制台简报（即本文 §1–§3 数据源）
