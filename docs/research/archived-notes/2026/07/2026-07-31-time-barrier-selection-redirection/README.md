# time-barrier-selection · 方向修正归档（2026-07-31）

> **关系类型**：阶段归档 + 方向修正
>
> **归档原因**：原 Stage 1（5m 周期上 $|s|(T)$ 随 $T$ 形态扫描）已完成扫描，但用户复盘时发现**测量目标不对**——应关注"不同周期的 $|s|$ 强度"，而非"5m 内不同窗口长度的 $|s|$ 估计"。前者是市场结构信号（KF-14 跨周期不变性），后者是纯统计收敛现象（i.i.d. 下 $\alpha = 0.5$）。
>
> **归档动作**：把 Stage 1 全部产物（脚本、报告、输出 CSV/JSON）原样搬到本批次；workbench 目录清空以承载新方向。

## 1. 原 Stage 1 的一句话结论（已冻结）

玉米 5m 9 主力合约的 $\widehat{|s|}(T) = |\mu_T|/\sigma_T$ 随滚动窗口 $T$ 呈**严格幂律单调衰减**，9/9 合约归类为形态 A，衰减指数 $\alpha = 0.638 \pm 0.10$，$R^2 \ge 0.83$。短期存在 microstructure mean reversion（$\rho_1 \in [-0.04, -0.15]$），但强度弱于 AR(1) phi=0.3。

## 2. 方向修正（用户发现的问题）

> **用户的反思**：原计划测的是"5m 数据 + 不同滚动窗口长度 $T$"——这是**窗口长度的统计效应**（$\alpha = 0.5$ 是 i.i.d. 必然），不是市场结构信号。
>
> **真正应该测的**：每个**自然周期**（5m / 15m / 1h / 1d）单独看 $|s|$ 的真实水平与分布——直接验证 KF-14（structural-shaping-alpha 的跨周期不变性）。
>
> **新方向**：在 5m / 15m / 1h / 1d 四个周期上分别计算 $|s|$（用 20h / 80h 窗口，与 `corn_1h_strength_three_views.py` 口径一致），拟合 FoldedNormal 分布，对比 $\mu_D$ / $\sigma_D$ 在四个周期上的差异。

## 3. 归档文件清单

### 3.1 raw-docs/

- `experiment-plan.md` —— Stage 1 旧实验计划（5m $|s|(T)$ 形态扫描的设计、判据、验证顺序）；已冻结，新方向计划见 `docs/research/workbench/time-barrier-selection/cross-period-plan.md`

### 3.2 raw-workbench/

- `stage1-report.md` —— Stage 1 主报告，含一句话结论、$\alpha=0.638$ 等数据、单笔解读、方法论遗产

### 3.3 raw-scripts/

- `market_strength_scan.py` —— 5m 数据上扫描 $\widehat{|s|}(T) = |\mu_T|/\sigma_T$ 随滚动 $T$ 网格的曲线；cluster bootstrap 按周重抽样
- `classify_morphology.py` —— 把扫描结果按形态 A/B/C/D 归类（log-log 拟合 R^2 / 平台检测 / 局部极大值检测）

### 3.4 raw-outputs/

- `stage1_scan.csv` —— 91 行扫描数据（9 合约 + 4 合成 sanity check，每合约 6 个 T + 1 个 ∞）
- `stage1_scan.json` —— 同上，JSON 格式
- `stage1_morphology.csv` —— 13 行形态归类表（9 合约 + 4 sanity check，全部归类为形态 A）

## 4. Stage 1 的方法论遗产（保留价值）

即使方向打乱，Stage 1 仍有两条可复用的方法论结论：

1. **cluster bootstrap 粒度修正**（KF-2）：5m 期货每日 69 bar，5m 尺度扫描必须用"周 cluster"而非"日 cluster"——可推广到所有 5m/1m 主题
2. **rolling 窗口归属简化**（KF-3）：跨多周的大 T 窗口，"末 bar 所在周"作为 cluster 标签足够稳健（28x 加速）

这两条已登记到主题 `research-status.md` 的 KF 清单，不随归档消失。

## 5. 新方向定位

新方向（待启动）的文件将放在 workbench 下，**新文件名前缀 `cross-period-`**，避免与本批次混淆：

- `docs/research/workbench/time-barrier-selection/cross-period-plan.md`
- `docs/research/workbench/time-barrier-selection/scripts/cross_period_strength.py`
- `docs/research/workbench/time-barrier-selection/cross-period-report.md`
- `docs/research/workbench/time-barrier-selection/outputs/cross_period_*.{csv,json}`

## 6. 命名引用

`archive:2026-07-31-time-barrier-selection-redirection` — 本批次
`archive:2026-07-31-time-barrier-selection-redirection#stage1-report` — 旧 Stage 1 报告
`theme:time-barrier-selection#research-status` — 主题研究状态（KF 1/2/3 仍登记）
`archive:2026-07-24-structural-shaping-alpha-freeze` — 上游塑形理论（KF-14 跨周期不变性）
