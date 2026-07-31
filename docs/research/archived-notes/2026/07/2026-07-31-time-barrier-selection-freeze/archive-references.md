# time-barrier-selection · Archive References

> 用途：登记与本主题相关的归档批次，按 `quant-research-layout` 的 pull 模式维护——引用触发登记，不引用不登记。

## 1. 上游归档

### archive:2026-07-24-structural-shaping-alpha-freeze

- **关系类型**：方法论遗产 + 数学契约上游
- **说明**：本主题的塑形容器 $(K_S, K_T, T)$ 定义、Doob 保守律、Fourier 有限时间 null、$T^\ast$ 分界、真实成本模型、cluster bootstrap 判据、DirRandom baseline 全部继承自该主题；稳定数学契约已提炼至 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`（本主题**只做命名引用，不复述**）。
- **域内使用范围（引用护栏）**：见 [README.md §4](README.md#4-引用护栏声明域内--域外)。
- **相关文件**：
  - `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`（当前活文档）
  - `theorem:structural-shaping-alpha#winrate-payoff-tradeoff-under-frictions`
  - `theorem:structural-shaping-alpha#piecewise-static-kelly-vs-fixed-risk`
  - `archive:2026-07-24-structural-shaping-alpha-freeze#freeze-summary`（KF-1..27 完整演化史）
  - `archive:2026-07-06-structural-shaping-alpha-stage1#stage-summary`（gatekeeper 实证）

## 2. 本主题自归档（冻结完成）

### archive:2026-07-31-time-barrier-selection-redirection

- **关系类型**：阶段归档 + 方向修正（Stage 1）
- **说明**：原 Stage 1（5m 周期上 $|s|(T)$ 随窗口长度 T 形态扫描）整批冻结；测量目标修正为跨周期/跨品种 $|s|$ 分布对比。保留方法论遗产（cluster bootstrap 按周 KF-2、rolling 末 bar 归属简化 KF-3）。
- **相关文件**：`archive:2026-07-31-time-barrier-selection-redirection#README`

### archive:2026-07-31-time-barrier-selection-freeze

- **关系类型**：主题最终冻结（Stage 2/3/4）
- **说明**：主题三轮实证闭环归档——Stage 2 跨周期、Stage 3 跨品种、Stage 4 KF-27 喂入；核心结论：μ_D 跨周期跨品种量级一致（0.04–0.07）、最优塑形参数"一套通吃"（K_S=4, RR=3, τ=0.1）、方向概率 p=0.60 是实盘拐点。Stage 4b p-混合闭式已沉淀到 theorem §10.5。
- **相关文件**：`archive:2026-07-31-time-barrier-selection-freeze#README`

## 3. 相关方法论归档（pull 模式）

_（首个实验完成后按需追加。当前对以下批次的"方法论片段"可能需要引用，暂不预防性登记。）_

- `archive:2026-07-17-value-area-family-consolidated` — 若 Stage 2 跨品种扩样时遇到"品种保留率"判据，可回读该家族的共同教训；
- `archive:2026-07-13-va-asymmetry-leak-chain-consolidated` — 若引入 daily 特征或事件触发时的因果性检查，需先跑截断法验证。
