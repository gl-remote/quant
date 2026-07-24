---
name: "quant-math-spec"
description: "Rules for writing and reviewing the strategy math spec document (strategy-math-spec.md). Invoke when creating, editing, or consistency-checking a strategy math spec."
---

# Quant Math Spec

本 skill 覆盖 quant 项目**所有数学规格类文档**的写法、记号与静态一致性检查，包括：

- **主题活跃期**：`docs/research/themes/<slug>/strategy-math-spec.md`（数学契约，跟随 KF 演化）；
- **主题稳定期**：`docs/research/theorems/<slug>/*.md`（提炼后的稳定定理集，独立成篇）。

两类文档共享同一套数学记号规则与一致性检查清单；差异仅在**结构组织**与**内容边界**（详见"文档类型分工"）。

主题目录布局、其他辅助文档（research-status / experiment-plan / parameter-selection-spec / implementation-notes / README）以及跨文档流程（含 spec ↔ theorems 迁移流程），由 `quant-research-layout` 负责，本 skill 不重复。

## 触发时机

- 创建一个新的 `strategy-math-spec.md` 或 `theorems/<slug>/*.md`；
- 修改现有 `strategy-math-spec.md` 或 `theorems/<slug>/*.md`；
- 对上述任一文档做静态一致性检查；
- 因为规格缺失需要回补，然后再继续实现或实验；
- **从 spec 提炼稳定内核到 theorems**（本 skill 提供数学侧规范，`quant-research-layout` 提供迁移流程）；
- 需要判断某段内容是否属于数学规格类文档（若不属于则应交由 `quant-research-layout` 处理）。

## 文档类型分工

| 维度 | `strategy-math-spec.md`（活跃期） | `theorems/<slug>/*.md`（稳定期） |
|------|-------------------------------|----------------------------------|
| 位置 | `themes/<slug>/` | `theorems/<slug>/` |
| 目的 | 策略行为的**唯一契约**，为实现代码所依赖 | 稳定数学结论，独立成篇、可跨主题复用 |
| 稳定性 | 中（跟随 KF / 实验演化） | 高（一旦入库不轻易改） |
| 承载 | 策略定义 + 候选矩阵 + 参数 + tie-break + 实证锚点 + 决策阈值 | 定义 + 命题 + 引理 + 定理 + 推论 + 证明 + 文献对照 |
| 禁止 | 实验流水、调参过程 | 参数最优值、决策阈值、KF 演化叙事、工程近似、数据锚点 |
| 结构骨架 | 见"strategy-math-spec.md 的推荐结构" | 见"theorem 文档的推荐结构" |

**边界判定**：若一段数学内容**不依赖于任何实证锚点或参数扫描**，且**独立成章可对外展示**，就应放到 theorems；否则留在 spec。

## 核心原则

- `strategy-math-spec.md` 是**策略行为的唯一契约**。实现代码必须以规格为准；发现规格缺失时先回补规格再写代码。
- **`theorems/<slug>/*.md` 是稳定数学结论的唯一权威**——被 spec / experiment-plan / research-status 引用时**只引用不复述**。
- 单独阅读该文档即可复现（对 spec 是策略、对 theorem 是证明），不依赖代码实现、聊天上下文或历史实验记忆。
- 变量定义遵循"必要且充分"原则：影响策略语义、执行结果或可能产生歧义的变量必须定义。
- 一眼可辨认、能轻易达成共识的常规字段不必逐项解释（例如 `O_t/H_t/L_t/C_t/V_t` 可整体说明为 OHLCV bar）。
- session、bar 索引、tick、profile、状态变量、策略参数、派生参数、tie-break 规则必须显式定义。
- 所有候选分支必须列成有限集合（例如 `poc_mode ∈ {close, range}`）。
- 所有 tie-break 规则必须显式写出，不能隐藏在 `argmax` 或代码实现里。
- 入场、出场、止损、止盈、仓位、冷却、每日交易次数、状态重置必须以数学 / 伪数学规则固定。
- 数学表达的目标是精确、简要、可实现；不为显然概念写冗长解释。
- 只固定策略定义与候选集合；实验结果、调参过程、临时观察写在 workbench 或归档中。

## strategy-math-spec.md 的推荐结构（活跃期）

按下列骨架组织；结构可按复杂度删减，但不能牺牲独立可复现性：

```text
1. 目标
2. 基础对象与变量表
3. Profile / 结构锚定义
4. 事件定义
5. 状态变量
6. 开仓条件候选
7. 入场函数
8. 执行函数：价格、止损、目标、仓位
9. 退出函数
10. 状态重置
11. 候选矩阵或首轮默认候选
```

## theorem 文档的推荐结构（稳定期）

```text
0. 文档头部元数据（见 quant-research-layout § 定理目录布局）
1. 记号与前提（本文档独立定义所需的所有符号）
2. 定义
3. 定理与证明（**命题/引理/定理 X.Y**：... **证明.** ... $\blacksquare$）
4. 推论与讨论
5. 文献对照（可选）
6. 与主题的关系（对应哪个 KF / 主题实证如何验证该定理）
```

**编号规范**：定理 / 命题 / 引理 / 推论使用**章节内两级编号**（如"命题 4.2"表示第 4 章第 2 个命题），跨章连续。定义与主结论用 `\boxed{...}` 高亮。

## 数学记号规则

数学表达采用**论文级 LaTeX**（KaTeX / MathJax 兼容子集），面向支持公式渲染的 Markdown 预览器。目标是"读起来像 SSRN / arXiv 论文"，而不是纯文本 pseudo-math。

### 核心格式约定

- **行内公式**使用 `$...$`，如 `令 $\tau := \text{price\_tick}$`。
- **块级公式**使用 `$$...$$`，独占段落，前后各空一行。
- 允许并鼓励使用：`\begin{aligned}` / `\begin{cases}` / `\begin{equation}` / `\begin{align}` / `\boxed{...}` / `\underbrace{...}_{...}` / `\overbrace{...}^{...}`。
- 允许使用 `\mathbb{R}, \mathbb{E}, \mathbb{P}, \mathcal{F}, \mathcal{N}` 等常用花体。
- 允许 `\text{...}` 混排中英文说明；纯变量名不要包在 `\text{}` 里，用 `\mathrm{}` 或直接下标。
- 定义式统一用 `:=`（`\coloneqq` 或字面 `:=`）；等价用 `\Leftrightarrow`；蕴含用 `\Rightarrow`。
- 逻辑连接词块级用 `\land / \lor / \neg`，行内也可用 `\wedge / \vee`。
- 集合构造用 `\{ x \in X \mid \phi(x) \}`；条件期望用 `\mathbb{E}[X \mid \mathcal{F}]`。
- 求和 / 积分 / 极限带下标：`\sum_{t \in I}`、`\int_{0}^{T}`、`\lim_{n \to \infty}`。
- 分段函数：

  $$
  P_\text{win}(\lambda; K_S, K_T) =
  \begin{cases}
    \dfrac{e^{\lambda K_T}(1 - e^{-\lambda K_S})}{e^{\lambda K_T} - e^{-\lambda K_S}} & \lambda \ne 0 \\[6pt]
    \dfrac{K_S}{K_S + K_T} & \lambda = 0
  \end{cases}
  $$

- 关键结论用 `\boxed{...}` 高亮。
- 多行推导必须对齐等号或不等号：使用 `\begin{aligned} ... \end{aligned}`。
- 每条定理 / 引理 / 命题 / 推论用 Markdown 三级或四级小标题标注编号，正文散文与公式紧接。可选使用 `**定理 2.1（Doob OST）**：` 这种粗体前缀。
- 每个证明段落用 `**证明.**` 开头，用 `\quad\square` 或 `\blacksquare` 结尾。

### KaTeX / Web 渲染兼容性硬约束

以下坑点在部分 Markdown 预览器（KaTeX / markdown-it）下会**触发解析错误**或**渲染错位**，一律按下列写法处理：

1. **表格单元内的绝对值 `|`** — 会被表格解析器当作单元格分隔符，用 KaTeX 显式宏替代：
   - ❌ `| $|s|$ 范围 |`
   - ✅ `| $\lvert s \rvert$ 范围 |`（或 `\vert s \vert`）
   - 范数用 `\lVert x \rVert`；集合/条件竖线用 `\mid`。

2. **中文间隔号 `·` (U+00B7) 禁止出现在数学环境内** — KaTeX 会解析为未定义的 `\cdotp` 并报错。散文里的 `·` 保留无碍，但**不要出现在 `$...$` / `$$...$$` 里**：
   - ❌ `$\text{【KF-1 · Doob 保守律】}$`
   - ✅ `**【KF-1 · Doob 保守律】**` （标签移出数学环境，改为 Markdown 粗体）

3. **数字紧接 `$` + 字母** — 部分渲染器会把 `$h` 误判为新数学区起始，导致行内公式配对错乱。**带单位的量一律纳入数学环境**：
   - ❌ `$T = 1625$h`
   - ✅ `$T = 1625\,\text{h}$` 或 `$T = 1625\ \mathrm{h}$`
   - 数字与单位之间用 `\,`（3/18 em）或 `\ `（1 em）薄间隔。

4. **块级公式尾部装饰标点统一为"无"（工程风格）** — 全文一致：
   - ❌ `$$ \nu = 0 \Rightarrow E_{\text{gross}} \equiv 0. $$` （句号在 `\right]` 或右括号后视觉像乘号）
   - ✅ `$$ \nu = 0 \Rightarrow E_{\text{gross}} \equiv 0 $$`
   - `\boxed{...}` 内部同理，不保留末尾 `.` 或 `,`。
   - `aligned` 环境**中间行**的 `,`（并列子式分隔符）保留，末行不加。
   - 例外：AMS 传统式尾 `.` 在 PDF / Overleaf 环境下渲染正常；本项目为兼容 Web 预览器统一采用工程风格。

### 示例（塑形理论主题片段）

```markdown
**定义 1.1（对数空间漂移）**：设价格 $S_t$ 满足几何布朗运动 $dS_t / S_t = \mu\, dt + \sigma\, dW_t$，取对数变换 $X_t := \ln(S_t / S_0)$，由 Itô 引理得

$$
dX_t = \nu\, dt + \sigma\, dW_t, \qquad \nu := \mu - \tfrac{1}{2}\sigma^2
$$

**定义 1.2（市场强度 · Sharpe 借鉴）**：类比 Sharpe 比率 $\mathrm{SR} := (\mu - r_f)/\sigma$，定义**对数空间市场强度**

$$
\boxed{\;s := \dfrac{\nu}{\sigma} = \dfrac{\mu}{\sigma} - \dfrac{\sigma}{2}\;}
$$

即"per-unit-time 对数空间 Sharpe"。当 $\sigma$ 已归一化到单 bar 时 $s$ 直接为 per-bar Sharpe。

**命题 1.3（首达概率恒等式）**：在 $s = 0$（即 $\nu = 0$）时，双 barrier 首达止盈概率满足

$$
P_\text{win}\big|_{s=0} = \frac{K_S}{K_S + K_T} = \frac{1}{1 + R}, \quad R := K_T / K_S
$$

**证明.** 由 $\nu = 0$，$X_t$ 是鞅。取停时 $\tau := \inf\{t : X_t \notin (-K_S, K_T)\}$。Doob 可选停时定理给出 $\mathbb{E}[X_\tau] = X_0 = 0$，即

$$
K_T \cdot P_\text{win} - K_S \cdot (1 - P_\text{win}) = 0
$$

解得 $P_\text{win} = K_S / (K_S + K_T)$。$\blacksquare$
```

### 允许保留纯文本 code block 的场合

- 需要展示伪代码、状态机分支、配对矩阵的**表格结构**时，可继续使用 fenced code block（`text` 或 `python`）。
- 只有当内容以流程、伪代码或纯符号列表为主，且**不含真正的数学推导**时，才允许不套 LaTeX。
- 一旦出现 $\Rightarrow$、$\mathbb{E}$、$\int$、$\sum$、上下标混排等真正的数学表达，必须切到 LaTeX。

## 规格与实现的关系

- 规格先于实现。
- 规格中未定义的行为，代码中不要自行脑补。
- 实现需要新增参数或改变行为时，先更新 `strategy-math-spec.md`。
- 回测计划和实验记录可以引用规格，但不要把实验流水账写进 `strategy-math-spec.md`。

## 每次修改后的静态一致性检查

每次修改 `strategy-math-spec.md` 都必须**主动**执行一轮"通篇检查有没有矛盾、明显不合理、重复、约束不正交"，不等用户提醒。检查前先完整重读文档，再逐条对照下列清单，把发现的问题与修复动作写在同一次答复中。

### 检查清单

1. **符号一致性**
   - 每个符号在使用前是否已定义；同一符号是否在不同位置代表不同含义。
   - 变量的量纲是否统一：`idx(·) / time(·) / τ` 等分区，不同量纲不得在同一比较中出现。
   - 大小写、下标形式（`X_s` vs `X(s,t)`）是否全文统一。
2. **时间与索引**
   - `t_entry, t_exit, t_ref(t)` 是"bar 引用"还是"idx 数值"必须一致；用 `idx(·)` 与 `time(·)` 明确类型。
   - 窗口回溯用 bar 条数（`n_·`）还是钟表时长（`W_·`）必须与实际使用位置一致。
3. **状态变量正交性**
   - `X_s`、`A_s / B_s^- / Z_s^-`、`P_t / D_t / U_t`、`T_refresh / T_adopt`、`T_last_exit / TradeCount_d` 各自的更新触发源是否不重叠。
   - 重置事件（session reset、breakout reset、profile refresh）是否显式声明"影响哪些状态、不影响哪些状态"。
4. **候选集合与配对矩阵**
   - 每组候选（形态 / 风控 / 方向 / 止盈 / ...）内部是否析取（∨），组间是否合取（∧）。
   - 配对矩阵维度是否与所有候选集合数量一致；退化情形（`Ω = {全集}`）是否等价于"不启用该组过滤"。
5. **触发条件冗余与蕴含**
   - `Enter / Exit` 判定式中是否有被其它子式蕴含的项（可降级为注解）。
   - `RiskOK / SpaceOK / DirOK` 之间是否有互相蕴含的严格不等式。
6. **退出优先级与成交模型**
   - `first_true` 顺序是否与优先级声明一致。
   - 每种退出触发的成交价（engine fill vs strategy-level C_t）是否明确到每个候选。
7. **默认候选与参数**
   - 首轮默认（`§11` 或等价小节）是否覆盖 `θ_profile / θ_signal / θ_exec / θ_size` 中所有会影响回测的参数。
   - 有条件参数（例如 `rr_raw_min` 只在 `R1 ∈ Ω_risk` 时有效）是否声明在无关配置下归并为单点。
8. **散文与公式一致性**
   - 每段散文说明是否与紧邻的公式定义完全等价；散文若添加公式未覆盖的约束，应升级为公式。
   - 冗余的"重复解释同一件事"的段落应合并或删除。
9. **量纲汇总表**
   - 若文档含"量纲约定"表，新增变量必须归入其中之一。
10. **孤立符号**
    - 用文本搜索方法检查是否存在只被定义未被使用（死变量），或只被使用未被定义（悬空引用）。
11. **KaTeX / Web 渲染兼容性**（见"数学记号规则 § KaTeX 兼容性硬约束"）
    - 表格单元内 `|` 是否已用 `\lvert / \rvert / \vert / \mid` 替代；
    - `$...$` / `$$...$$` 内是否含中文间隔号 `·`；
    - 带单位量是否用 `\,\text{...}` 纳入数学环境；
    - 块级公式尾部装饰标点（`.` `,` 在 `$$` 或 `\boxed{...}` 末尾）是否已清除。

### theorem 文档额外检查项（仅对 `theorems/<slug>/*.md` 适用）

12. **闭合自洽性**
    - 记号是否在文档内**自我定义**——不允许"参见 spec §X"这类外部依赖；
    - 若确需引用 spec 的定义，必须**内联复述**该定义。
13. **禁区检测**
    - 是否混入了参数最优值、决策阈值、KF 演化叙事、工程近似、数据锚点等 spec 专属内容；
    - 品种 / 时间粒度 / 样本量作为例子出现时，是否严格限制在**证明外**的散文注解或"与主题的关系"章节。
14. **可对外展示性**
    - 删掉主题上下文后，是否仍是有独立价值的数学短文；
    - 是否包含足够的文献对照（可选）与"与主题关系"说明（必需）。
15. **头部元数据完备性**
    - blockquote 是否包含 5 项：文档定位 / 稳定性 / 对外可用 / 与本主题关系 / 命名引用；
    - 命名引用格式是否符合 `theorem:<slug>#<file-stem>` 规范。

### 产出格式

- 用短表格列出「问题 → 位置 → 修复」；
- 对每处修复实际调用 SearchReplace 工具改动文档；
- 最后附一段"验证正交性"总结，说明本轮修改后各正交维度间的相互作用是否仍然清晰。
- 若清单项均未发现问题，也必须显式说明"本轮无需修复"，不省略该步。

### 触发条件（除主动触发外）

- 用户显式要求"检查一致性 / 冗余 / 正交"时；
- 用户在同一轮修改中新增 / 删除 / 合并了任何状态、参数、候选、退出条件时；
- 用户提出概念性问题后规格随之调整时。

## 与其他 skill 的边界

- 主题目录布局、其他辅助文档写法、跨文档流程、workbench / archive / issues / roadmap 边界：全部见 `quant-research-layout`。
- 本 skill 不涉及回测运行、数据管道、CLI；相关问题分别由 `quant-cli`、`quant-project` 等 skill 负责。
