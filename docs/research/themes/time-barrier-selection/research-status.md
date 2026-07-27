# time-barrier-selection · Research Status

> 状态：活跃 · 立题（2026-07-28）· 尚未产出实验证据
> 最近更新：2026-07-28
> 归档批次：暂无

## 1. 当前一句话结论

```text
主题刚立题，尚无实证结论。
核心假设：单合约 5m 周期下，存在一个持仓周期 T*（bar 数），
使得给定 (K_S, K_T) 的双 barrier 塑形容器满足 E[E_net] > 0；
且 T* 依赖于品种 5m 的 σ_bar 与 |s| 分布，
需通过广度扫描 + FPT 分布诊断得到。

首个实验对象：玉米 DCE.c 5m（size=10, tick=1.0, commission=1.21）。
```

## 2. 核心假设

**H1（存在性）**：存在有限的持仓周期 $T \in [T_\min, T_\max]$（以 5m bar 为单位），使得

$$
\mathbb{E}[E_{\text{net}}(T)] = \mathbb{E}[X_\tau] - 2c > 0
$$

在 ATR 归一化的双 barrier 容器 $(K_S, K_T)$ 下成立。

**H2（尺度定位）**：由 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的 $T^\ast = \max(K_S, K_T)^2 / \sigma^2$（定义 4.4），$T^\ast$ 与 $\sigma_{5m}^2$ 反相关；因此在 5m 周期下 $T^\ast$ 应按 bar 数换算，判定合理的持仓 bar 数区间。

**H3（品种依赖）**：$T^\ast$ 的品种间可比性需要按 ATR 归一化后重新验证；玉米作为低波动品种，$T^\ast$ 可能显著大于豆油、螺纹等高波动品种（意味着更长的 bar 数持仓）。

## 3. 关键发现清单

_（暂无。首次实验完成后按 [quant-research-layout](../../../../.trae/skills/quant-research-layout/SKILL.md) 的 KF 格式登记。）_

## 4. 下一步

**优先级**：见 [experiment-plan.md](experiment-plan.md)。

**Stage 1**（当前）：玉米 5m 持仓周期扫描 · 目标是回答"持仓多少 5m bar 能让单笔期望净收益覆盖交易成本"。

- 数据：`project_data/market_data/csv/DCE.c*.tqsdk.5m.csv`
- 判据：$\mathbb{E}[E_{\text{net}}] > 0$ 在 combo 网格上的分布，配合随机对照（DirRandom）
- 方法论：ATR 归一化 · 期望净值 · cluster bootstrap · 真实成本模型（`workspace/common/contract_specs.py` 中 `c` 品种）

## 5. 边界与已知约束

- 本主题**不研究方向 alpha**（通道 A）——沿用 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的 DirRandom baseline；
- 本主题**不研究仓位管理**——仓位管理由 `theorem:structural-shaping-alpha#piecewise-static-kelly-vs-fixed-risk` 覆盖；
- 广度扫描完成前**不写完整 math-spec**（遵循 `quant-research-methodology` §8）。
