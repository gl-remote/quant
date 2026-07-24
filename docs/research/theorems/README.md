# Theorems · 稳定数学定理与命题集

> **文档定位**：本目录只承载**稳定、漂亮、可长期引用**的**数学结论**——
> 定义、命题、引理、定理、推论、以及它们的证明与文献定位。
>
> 每一份文档都应当**独立成篇**、**逻辑闭合**、**记号自洽**，读者不需要
> 额外背景就能通读、复用其中的定理。

---

## 一、目录定位

| 目录 | 承载 | 稳定性 |
|------|------|--------|
| `docs/research/themes/<slug>/` | 活跃研究：math-spec + 实验计划 + KF 演化 + 参数选择 + 工程实现 | 中（随实验演化） |
| **`docs/research/theorems/<slug>/`** ⭐ | **稳定数学契约**：从主题里提炼出来的、已不再随实验流水演化的**结论集** | **高**（一旦入库不轻易改） |
| `docs/research/archived-notes/<batch>/` | 冻结历史：一次归档批次的原始过程与压缩摘要 | 高（历史证据不变） |
| `docs/roadmap/` | 阶段规划与评价标准 | 中 |

`theorems/` 与 `themes/` 的分工：

- `themes/<slug>/strategy-math-spec.md` 是**主题活跃期的数学契约**——KF 还在演化时，spec 也在演化；
- `theorems/<slug>/*.md` 是**主题成熟后从 spec 抽出的稳定内核**——不再随实验演化，只随更严格的证明或更好的记号迭代。

---

## 二、什么内容进 theorems/

**必须**满足以下四条：

1. **数学纯粹**：只承载定义 / 命题 / 引理 / 定理 / 推论 / 证明；不承载参数扫描、实证数字、KF 演化叙事、工程实现。
2. **闭合自洽**：记号在文档内自我定义，读者不需要打开 spec / KF 才能理解。
3. **可对外展示**：若删掉主题上下文，仍是一篇有独立价值的数学短文（可对同行展示、可投稿、可教学）。
4. **稳定**：结论已通过至少一次归档 / 复审，短期内不会因新实验而重写。

**明确不进**（即使已经确定）：

- 参数最优值（如 KF-27 的 `K_S^\ast = 3.0` 具体锚点）——这是**实证结果**，属于主题实证部分，theorems 只承载"求最优的方程与判据"这一层；
- 决策阈值（如 `|ν/σ| ≥ 0.10`）——同上；
- KF 演化史 / 反转记录 / 方法论纠错——属于主题历史叙事；
- 工程近似（Fourier 截断项数、数值 quadrature 网格）；
- 数据锚点（品种、时间粒度、样本量）。

---

## 三、目录内部结构

按主题 slug 分子目录，与 `themes/` 平行镜像：

```text
docs/research/theorems/
├── README.md                        # 本文件
├── <theme-slug-1>/
│   ├── README.md                   # 该主题的定理集目录索引 + 阅读顺序
│   ├── <topic-1>.md                # 稳定结论 A（如 "shaping-conservation-law.md"）
│   ├── <topic-2>.md                # 稳定结论 B（如 "channel-b-mixture-formula.md"）
│   └── ...
└── <theme-slug-2>/
    └── ...
```

**文件命名**：kebab-case，语义化，避免 `spec.md` / `theorem.md` 这类泛化名。
一份文档可以只承载一个大结论（如 `mixture-formula.md`），也可以承载
一个自洽结论簇（如 `doob-two-premises.md` = P1 失效 + P2 失效双通道）。

---

## 四、每份定理文档的结构模板

```markdown
# <文档标题>

> **来源**：theme:<slug>#strategy-math-spec 的 §X.Y
> **稳定性**：入库日期 YYYY-MM-DD · 复审 YYYY-MM-DD
> **对外可用**：是 / 否（若否说明未闭合项）

## 1. 记号与前提

（本文档独立定义所需的所有符号；不依赖其他文档）

## 2. 定义

**定义 1.1（xxx）**：...

## 3. 定理与证明

**命题 2.1**：...

**证明.** ... $\blacksquare$

## 4. 推论与讨论

**推论 3.1**：...

## 5. 文献对照

（与主流学术文献的对照，参考 theme 的附录 C）

## 6. 与主题的关系

（说明本定理对应 theme 的哪个 KF / 哪一章；说明主题实证如何验证该定理）
```

---

## 五、跨文档硬约束

- `theorems/<slug>/*.md` **不承载**策略行为的**实证结果**——那是 `themes/<slug>/*` 的职责；
- 若某个 theorem 需要引用主题的实证锚点（品种、时间粒度）作为例子，在**证明外**用命名引用（`kf:<slug>#KF-N`）或散文注解，不进入定理正文；
- `themes/<slug>/strategy-math-spec.md` 允许引用 `theorems/<slug>/*.md` 作为已证结论的复用（**只引用不复述**）；
- 一份 theorem 文档**允许**被多个主题 spec 引用（跨主题共用的数学工具，如"Doob OST 两前提对偶"这种方法论定理）。

---

## 六、命名引用协议

沿用 [quant-research-layout skill](../../../.trae/skills/quant-research-layout/SKILL.md) 的命名引用协议，扩展一个前缀：

| 前缀 | 语法 | 解析位置 |
|------|------|---------|
| `theorem:` | `theorem:<slug>#<file-stem>` | `docs/research/theorems/<slug>/<file-stem>.md` |
| `theorem:` | `theorem:<slug>#<file-stem>#定理2.1` | 定位到文档内的定理编号锚点 |

其他前缀（`archive:` / `theme:` / `kf:` / `workbench:` / `issue:` / `roadmap:`）保持不变。

---

## 七、迁移与新增流程

### 从 theme 迁移已成熟的 math-spec 到 theorems

1. 判断成熟度：主题至少经过一次归档 / 冻结，或明确进入"稳定期"（KF 不再增加）；
2. 拆分：把 `themes/<slug>/strategy-math-spec.md` 拆成
   - **稳定内核** → 迁移到 `theorems/<slug>/*.md`；
   - **实证锚点、参数扫描、决策阈值** → 留在 spec（成为"实证部分"）；
3. spec 里改为 `theorem:<slug>#<file>` 命名引用；
4. `theorems/<slug>/README.md` 里追加文档索引 + 阅读顺序；
5. `research-status.md` 的 KF 条目里把证据字段中的 spec 引用升级为 `theorem:` 引用（当适用时）。

### 新增一份 theorem 文档

- 从 workbench 直接产出的**新数学结果**：先写 workbench，通过 review 后可直接立卷进 theorems；
- 从主题 spec 提炼：见上节迁移流程；
- 跨主题的方法论定理（如 Sharpe SE、Doob OST 通用推论）：可以不属于任何 theme slug，放到 `theorems/_general/` 或以方法论 slug 命名（如 `theorems/sharpe-statistics/`）。

---

## 八、当前已收录

| 主题 slug | 文档 | 入库日期 |
|-----------|------|---------|
| [structural-shaping-alpha](structural-shaping-alpha/) | [when-barrier-shaping-yields-alpha.md](structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) | 2026-07-24 |
| [structural-shaping-alpha](structural-shaping-alpha/) | [winrate-payoff-tradeoff-under-frictions.md](structural-shaping-alpha/winrate-payoff-tradeoff-under-frictions.md) | 2026-07-24 |

