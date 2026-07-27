# time-barrier-selection · Strategy Math Spec（占位）

> 状态：**占位** · Stage 1 广度扫描通过后再补完整规格
> 依据：`quant-research-methodology` §8 · 少数品种阶段不写完整 math spec，只写核心假设

## 核心假设

在 5m 周期上，存在有限持仓上限 $T^\ast_{\text{PL}}$（bar 数），使得双 barrier 塑形容器 $(K_S, K_T, T^\ast_{\text{PL}})$ 下

$$
\mathbb{E}[E_{\text{net}}] = \mathbb{E}[X_{\tau \wedge T^\ast_\text{PL}}] - 2c > 0
$$

其中 $\tau$ 为首达停时、$c$ 为按真实成本模型换算的单边 ATR 成本。

## 数学骨架（引用不复述）

所有底层数学定义（$X_t$、$\tau$、$P_\text{win}^{\infty}$、$P_\text{win}^\text{finiteT}$、Doob 保守律、$T^\ast$、$x_\min$、$s = \nu/\sigma$、混合期望公式）严格引用 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`——本 spec 只在广度扫描证实假设后补 **5m 尺度专属**的：

- 5m 品种 $|s|$ 分布 $D_{5m}$ 的经验拟合
- 5m 真实成本 $c_{5m}$（`workspace/common/contract_specs.py`）
- $T^\ast_{\text{PL}}$ 与 $T^\ast$ 定义 4.4 的经验比例
- time-exit 事件的期望贡献（若落入过渡区）

## 待补章节（Stage 1 通过后）

1. 5m 周期下的记号与前提（时间量纲改为 5m bar）
2. 玉米 5m 的实证 $D_{5m}$（FoldedNormal 或经验分布）
3. Stage 1 通过后每个 combo 的 $\bar{E}_\text{net}$ / $\mathbb{E}[\tau]$ / time-exit% 汇总
4. $T^\ast_{\text{PL}}$ 的存在性命题与其证明（若通过）
5. 与上游 theorem 的 KF 对应表
