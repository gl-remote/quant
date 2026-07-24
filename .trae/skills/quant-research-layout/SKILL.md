---
name: "quant-research-layout"
description: "Rules for quant research document layout: theme directory, workbench, archive, issues, roadmap boundaries and cross-doc flows. Invoke when creating theme directories, writing non-spec research docs, migrating workbench notes, archiving, or filing issues."
---

# Quant Research Layout

本 skill 覆盖 quant 项目所有研究文档的**目录布局与跨文档流程**，包括：

- 主题目录（`docs/research/themes/<theme-name>/`）的固定布局与文件分工；
- **定理目录（`docs/research/theorems/<theme-slug>/`）的稳定数学结论存放规则**；
- **研究笔记归档目录（`docs/research/archived-notes/`）的归档流程**——与 `docs/archive/` 的工程类归档**严格分离**；
- workbench / issues / roadmap 各自的边界与写法；
- 主题目录初始化、workbench 归档、issues 处理、spec 提炼为 theorem 等跨文档流程。

**关键分离原则**（自 2026-07 起）：
- 策略研究的一切归档产物（研究笔记 md + raw-workbench + raw-scripts + raw-strategies + raw-outputs）**统一放到 `docs/research/archived-notes/`**——因为它们本质上是研究链路的一部分，不是工程资产；
- `docs/archive/` 只承载**非策略研究的工程类归档**（如 aspects、backtest、infra、deprecated 等历史技术方案）；
- 命名引用 `archive:<batch>` 前缀**保持不变**（语义扩展为"归档统称"），当前只指向 `docs/research/archived-notes/<batch>/`。

`strategy-math-spec.md`（活跃期）与 `theorems/<slug>/*.md`（稳定期）本身的写法（结构、数学记号、静态一致性检查）由 `quant-math-spec` 负责，本 skill 不重复。

## 触发时机

- 新建一个策略主题目录；
- 修改主题目录内除 `strategy-math-spec.md` 之外的任意文档；
- **判断某段稳定数学结论应放到 `themes/<slug>/strategy-math-spec.md` 还是 `theorems/<slug>/*.md`**；
- **从主题 spec 提炼稳定内核到 theorems，或反向调整**；
- 判断某段内容应放到 workbench / theme / theorems / archive / issues 中哪个位置；
- **归档主题研究成果**：以当前 git 分支相对基线（master/main）的 ALL 差异文件为归档范围，识别并归档与主题相关的 workbench / 临时脚本 / 临时策略 / 数据产出（不仅是未提交的 workbench 文件）；
- 发现底层框架问题需要开 issue；
- 修 roadmap 或 research 目录索引文件。

## 顶层目录边界

| 目录 | 用途 | 允许放什么 | 禁止放什么 |
|---|---|---|---|
| `docs/roadmap/` | 阶段规划、评价标准 | 阶段目标、候选方向、评价指标 | 具体实验方向、分支 hash、参数对照、中间结果 |
| `docs/research/` | 研究总入口与主题目录 | `strategy-current.md`（全局入口）、`README.md`、`themes/<theme-name>/`、`theorems/<theme-slug>/`、`archived-notes/` | 具体实验流水 |
| `docs/research/themes/` | **活跃**策略主题（研究中 / 待启动 / 阶段性暂停但可能恢复） | 见"主题目录布局" | 已冻结的主题、稳定数学定理集 |
| **`docs/research/theorems/`** ⭐ | **稳定数学定理集**：从主题 spec 提炼、独立成篇的定理/命题/引理 | 见"定理目录布局" | 实证结果、参数扫描、KF 演化叙事、工程实现 |
| **`docs/research/archived-notes/`** ⭐ | **研究笔记归档**：已完成阶段的压缩摘要 + 原始 workbench / 脚本 / 策略 / 数据产出 | 核心问题、实验定义、固定参数、关键结果、结论、raw-* 子目录 | 过程性计划、过期工具限制 |
| `docs/workbench/` | 当前研究中的实验流水 | 实验问题、临时参数对照、中间结果、临时结论 | 长期规格、策略契约 |
| `docs/issues/` | 底层框架问题 | 引擎 / 数据管道 / CLI / 成本口径等非策略问题 | 策略结论 |
| `docs/archive/` | **工程类**归档（非策略研究）：aspects / backtest / infra / deprecated 等历史技术方案 | 框架、基础设施、旧架构重构记录 | 策略研究归档（走 `research/archived-notes/`） |

`docs/roadmap/` 允许在 meta 顶部写"文档边界"说明。

## 主题目录布局

一个策略主题的**所有长期文档**统一放在：

```text
docs/research/themes/<theme-name>/
├── README.md                    # 目录索引 + 阅读顺序
├── research-status.md           # 主题研究现状（结论 / 边界 / 下一步）
├── strategy-math-spec.md        # 数学规格（由 quant-math-spec 约束）
├── experiment-plan.md           # 实验计划（候选矩阵 / 验证顺序 / 判定标准）
├── parameter-selection-spec.md  # 参数选择规格（分层 / 判据 / 流程）
├── implementation-notes.md      # 工程实现细节（数据结构 / 缓存 / 桥接 / 性能）
└── archive-references.md        # 与本主题相关的 archive 目录索引与关系说明
```

### 文件分工（严禁越界）

| 文档 | 回答 | 谁改 | 什么时候改 |
|---|---|---|---|
| README.md | 主题目录索引与阅读顺序 | 主题维护者 | 目录成员变化时 |
| research-status.md | 主题当下的一句话结论、边界、下一步、**关键发现清单** | 策略研究者 | 结论变化时 / 每次得到关键发现时 |
| strategy-math-spec.md | 策略"是什么"（数学契约） | 策略研究者 | 行为变更前 |
| experiment-plan.md | "怎么验证"（候选矩阵、验证顺序、判据） | 策略研究者 | 实验路径变化时 |
| parameter-selection-spec.md | "怎么选参数"（分层、判据、流程、回填格式） | 策略研究者 | 实验后 |
| implementation-notes.md | "怎么实现"（工程细节、优化选择、性能数据） | 实现者 | 实现开始 / 完成时 |
| archive-references.md | 与本主题相关的 archive 目录清单及关系（继承 / 反例 / 数据 / 代码复用） | 主题维护者 | 立题时 / 每次归档新增批次 / 引用/继承关系变化时 |

### 跨文档硬约束

- `strategy-math-spec.md` 是**唯一**定义策略行为的文档；其他五份文档均不得定义或改变策略行为。
- 若 `implementation-notes.md` 中的某项工程决定影响了语义，先回改 `strategy-math-spec.md`，再更新 `implementation-notes.md`。
- 若 `parameter-selection-spec.md` 需要一个 spec 未定义的参数，先在 `strategy-math-spec.md` 补声明。
- `experiment-plan.md` 与 `parameter-selection-spec.md` 都可以引用 spec，但不能复述完整策略公式。
- `research-status.md` 只承载"结论、边界、下一步、关键发现清单"，不承载策略公式，不承载实验流水，不承载工程细节。
- 主题目录中的文档**不允许**依赖 workbench 中的临时文件；workbench 的稳定结论必须归档到 archive，主题目录再引用 archive。
- **workbench 目录只有一个，位于 `docs/workbench/`**（顶层）。**禁止**在主题目录（`docs/research/themes/<theme-name>/`）下再建 `workbench/` 子目录。所有实验流水、临时报告、driver 输出统一写到 `docs/workbench/<theme-slug>-<topic>.md` 或 `docs/workbench/<theme-slug>/<topic>.md`（大主题内多份文件时才建子目录，且该子目录必须直属 `docs/workbench/`）。

### 命名规则

- 主题目录名 = 策略主题 slug（kebab-case，如 `value-area-reacceptance`）。
- 目录内文件名固定为上表六个，作用一目了然，禁止使用过于泛化的 `spec.md / plan.md / current.md`。
- 若主题需要额外辅助文档（数据字段词表、诊断字段清单等），也放同目录并在 README 的"文档地图"中登记。

### 命名唯一性硬约束（命名引用协议的基础）

- **主题 slug 全局唯一**：`docs/research/themes/*` 与 `docs/research/theorems/*` 使用**同一命名空间**（不允许 themes/foo 与 theorems/foo 同时指向不同主题），slug 共享；
- **theorem 文档文件名在主题内唯一**：`docs/research/theorems/<slug>/<file-stem>.md` 不得同名；跨主题可重名（因命名引用带 slug）；
- **archive 批次目录名全局唯一**（自然满足：日期前缀 + slug）；
- **workbench 文件名 / 主题内多文件时的子目录名全局唯一**：`docs/workbench/<theme-slug>-<topic>.md` 或 `docs/workbench/<theme-slug>/<topic>.md`；
- **issue 文件名全局唯一**：`docs/issues/<slug>.md`。

**立题 / 建家族 / 归档新批次前**：`grep -r "<候选 slug>" docs/research docs/archive docs/workbench` 一次，确认无重名。发现冲突时 slug 加限定后缀（如 `value-area-reacceptance-2`）而不是复用。

## 定理目录布局（theorems/）

**定位**：`docs/research/theorems/<theme-slug>/` 承载**稳定、独立成篇、可长期引用**的**纯数学结论**（定义 / 命题 / 引理 / 定理 / 推论 / 证明）。它与 `themes/<slug>/strategy-math-spec.md` 的分工是：

- **spec（活跃期）**：主题研究中的数学契约，跟随 KF 演化；包含实证锚点、参数扫描、决策阈值等；
- **theorem（稳定期）**：从 spec 里提炼出来的、**不再随实验演化**的数学骨架；剥离所有实证与工程近似，只保留可对外展示、可跨主题复用的定理集。

### 目录结构

```text
docs/research/theorems/
├── README.md                        # 顶层总入口 + 收录表
├── <theme-slug-1>/
│   ├── README.md                    # 该主题的定理集索引 + 阅读顺序
│   ├── <topic-1>.md                 # 一份文档 = 一个大结论 或 一个自洽结论簇
│   ├── <topic-2>.md
│   └── ...
└── <theme-slug-2>/
    └── ...
```

### 什么进 theorems/（四条硬约束）

1. **数学纯粹**：只承载定义 / 命题 / 引理 / 定理 / 推论 / 证明；不承载参数扫描、实证数字、KF 演化叙事、工程实现。
2. **闭合自洽**：记号在文档内自我定义，读者不需要打开 spec / KF 才能理解。
3. **可对外展示**：若删掉主题上下文，仍是一篇有独立价值的数学短文（可对同行展示、可投稿、可教学）。
4. **稳定**：结论已通过至少一次归档 / 复审，短期内不会因新实验而重写。

**明确不进 theorems/**（即使已经确定）：
- 参数最优值、决策阈值等**实证结果**——留在 spec 或 parameter-selection-spec；
- KF 演化史、反转记录、方法论纠错——留在 research-status；
- 工程近似（Fourier 截断项数、数值 quadrature 网格）——留在 implementation-notes；
- 数据锚点（品种、时间粒度、样本量）——留在 spec 或 parameter-selection-spec。

### 文档命名（AI 友好）

**文件名 = "AI 检索关键词 + 回答的问题"**，遵循三层语义：
1. **问题类型词**：`when-...`（存在性 / 充分条件）、`how-...`（构造 / 算法）、`why-...`（机制解释）、`<topic>-tradeoff`（权衡分析）；
2. **研究对象**：如 `barrier-shaping`、`winrate-payoff`、`sharpe-statistics`；
3. **修饰词**：如 `-under-frictions`、`-with-noise`、`-in-log-space`。

**好命名示例**：
- `when-barrier-shaping-yields-alpha.md` — 存在性问题
- `winrate-payoff-tradeoff-under-frictions.md` — 权衡分析
- `doob-two-premises-duality.md` — 数学对偶结构
- `sharpe-standard-error-bounds.md` — 界定命题

**坏命名（禁止）**：
- `theorem.md` / `spec.md` / `math.md` — 过于泛化，无法 grep 命中意图
- `chapter-1.md` — 顺序命名，无法反映内容
- `notes.md` — 语义不明

### 文档头部元数据

每份 theorem 文档头部必须包含元数据 blockquote：

```markdown
# <文档标题>

> **文档定位**：本文回答一个数学问题——**<核心问题一句话>**。<方法论 / 结论 / 贡献一句话>。
>
> **稳定性**：入库日期 YYYY-MM-DD · <是否来自 spec 提炼 / 一致性检查状态>。
>
> **对外可用**：是 / 否（若否说明未闭合项）。
>
> **与本主题的关系**：<与主题内其他文档、其他 theorem 的分工关系>。
>
> **命名引用**：`theorem:<slug>#<file-stem>`
```

### 每份 theorem 文档的推荐结构

```text
1. 记号与前提（本文档独立定义所需的所有符号）
2. 定义
3. 定理与证明（每条 **命题/引理/定理 X.Y**：... **证明.** ... $\blacksquare$）
4. 推论与讨论
5. 文献对照（可选，见 quant-math-spec）
6. 与主题的关系（对应哪个 KF / 哪一章；主题实证如何验证该定理）
```

数学记号、证明格式、静态一致性检查规则由 `quant-math-spec` 提供，本 skill 不重复。

### 迁移与新增流程

**从 spec 提炼稳定内核到 theorems**：
1. 判断成熟度：主题至少经过一次归档 / 冻结，或明确进入"稳定期"（KF 不再增加）；
2. 拆分：
   - **稳定内核**（定义 / 命题 / 引理 / 定理 / 证明 / 附录级方法论） → 迁移到 `theorems/<slug>/<file>.md`；
   - **实证锚点、参数扫描、决策阈值** → 留在 spec；
3. spec 里改为 `theorem:<slug>#<file>` 命名引用（禁止复述定理内容）；
4. 更新 `theorems/<slug>/README.md` 文档地图；
5. 更新 `theorems/README.md` 顶层收录表；
6. 主题 `research-status.md` 的 KF 条目里，把证据字段中的 spec 引用升级为 `theorem:` 引用（当适用时）。

**新增一份 theorem 文档**：
- 从 workbench 直接产出的**新数学结果**：先写 workbench，通过 review 后可直接立卷进 theorems；
- 从主题 spec 提炼：见上；
- 跨主题的方法论定理（如 Sharpe SE、Doob OST 通用推论）：可以不属于任何 theme slug，放到 `theorems/_general/` 或以方法论 slug 命名（如 `theorems/sharpe-statistics/`）。

### 跨文档硬约束

- `theorems/<slug>/*.md` **不承载**策略行为的**实证结果**——那是 `themes/<slug>/*` 的职责；
- 若定理需要引用主题实证锚点作为例子，在**证明外**用命名引用（`kf:<slug>#KF-N`）或散文注解，不进入定理正文；
- `themes/<slug>/strategy-math-spec.md` 允许引用 `theorems/<slug>/*.md` 作为已证结论的复用（**只引用不复述**）；
- 一份 theorem 文档**允许**被多个主题 spec 引用（跨主题共用的数学工具）；
- **theorem 文档一旦入库不轻易改**——重要修改需在文档头部元数据"稳定性"字段追加"复审 YYYY-MM-DD"记录，说明为什么改。

## 命名引用协议（Named Reference Protocol）

**跨文档引用一律用命名标签，不写路径**。这是解决路径耦合与迁移膨胀的核心规则。

### 标签前缀 → 位置的映射（权威表）

| 前缀 | 语法 | 解析位置 | 说明 |
|------|------|---------|------|
| `archive:` | `archive:<name>` | `docs/research/archived-notes/<name>/` | `<name>` 是完整批次目录名（含日期前缀） |
| `archive:` | `archive:<name>#<file-stem>` | `docs/research/archived-notes/<name>/<file-stem>.md` | 指向批次内某具体报告 |
| `theme:` | `theme:<slug>` | `docs/research/themes/<slug>/` | 主题目录本身 |
| `theme:` | `theme:<slug>#<file-stem>` | 上述目录下 `<file-stem>.md` | 主题内某文档 |
| `theorem:` ⭐ | `theorem:<slug>#<file-stem>` | `docs/research/theorems/<slug>/<file-stem>.md` | 稳定数学定理文档 |
| `theorem:` ⭐ | `theorem:<slug>#<file-stem>#命题X.Y` | 文档内定理/命题的章节锚点 | 定位到具体命题 |
| `workbench:` | `workbench:<name>` | `docs/workbench/<name>.md` **或** `docs/workbench/<theme-slug>/<name>.md`（后者若首段等于某 theme-slug） | workbench 报告 |
| `kf:` | `kf:<theme-slug>#KF-<N>` | 主题 `research-status.md` 中 KF-N 条目 | 关键发现锚点 |
| `issue:` | `issue:<slug>` | `docs/issues/<slug>.md` | 底层框架 issue |
| `roadmap:` | `roadmap:<slug>` | `docs/roadmap/<slug>.md` | 路线图文档 |

### 引用格式（不用 markdown 链接语法）

```markdown
- 证据：archive:2026-07-05-value-area-rolling-reacceptance-freeze
- 反例：theme:value-area-rolling-reacceptance
- 方法论继承：archive:2026-07-05-value-area-rolling-reacceptance-freeze#freeze-summary
- 相关 KF：kf:structural-shaping-alpha#KF-1
```

**禁止**：
- `[label](../../../archive/...)` 相对路径链接；
- `[label](file:///Users/.../docs/...)` 绝对路径链接；
- 裸文件名如 `见 gatekeeper.md`；
- 除本 skill 权威表以外的自造前缀。

**例外（允许保留 markdown 链接）**：
- 外部 URL（学术论文、工具官网等）；
- 主题目录**内部**的六份长期文档互引（如 [research-status.md](research-status.md)——同目录相对路径极短且永久稳定，用不用命名引用无实质差别）；
- 已存在的历史 markdown 链接**不做被动 sweep**——新增引用按新规则即可，旧引用等自然演化替换。

### 迁移零成本

- **workbench → archive**：`kf:` 里的 `archive:` 引用不变；只需 `workbench:` 引用改为 `archive:`；

### AI 读取协定

AI 看到命名引用时按上表映射立即调 `Read` / `LS`。不需要打开当前文档所在目录做相对路径心算。

### 命名引用与 archive 顶层索引的关系

archive 顶层索引 [`docs/research/archived-notes/README.md`](../../docs/research/archived-notes/README.md) 的"家族 slug"列用于分类归档批次；"日期"列即 `archive:` 前缀日期段的解析源；两者共同构成命名引用的**权威索引表**。

## 关键发现清单（research-status.md 内节）

主题活跃期产生的**每一条重要结论**都必须登记到 `research-status.md`
的"关键发现清单"节，作为**主题内唯一入口**。规则如下。

### 什么算"关键发现"

必须登记的三类：

1. **策略行为级**：某维度 / 参数 / 结构变体被确认**有 alpha** 或**无 alpha**
   （无论证实还是证伪都要记）；
2. **方法论级**：某判据 / 采样 / 统计方法被确认**必需 / 无效 / 有伪影**
   （例如"cluster bootstrap 不可省"、"PrevClose 价格锚点会引入 DirRandom 偏置"）；
3. **假设证伪级**：主题原假设或子假设被独立证据链证伪（进入冻结候选）。

不登记：
- workbench 中一次性的临时观察（应留在 workbench）；
- 单一实验的中间数字（应留在 workbench / archive 的实验报告）；
- 参数微调结果（应写入 `parameter-selection-spec.md`）。

### 条目格式（每条 ≤ 5 行）

```markdown
### KF-<序号> · <一句话结论>
- 类型：策略行为 / 方法论 / 假设证伪（选一或多）
- 状态：已证实 / 已证伪 / 边界待定
- 证据：archive:<batch-name> 或 workbench:<name>（必需，走命名引用协议）
- 影响：对 strategy-math-spec / experiment-plan / 后续主题的具体影响
- 日期：YYYY-MM-DD
```

序号跨阶段单调递增，冻结时保留完整历史（不重编号）。**证据字段必须用命名引用**（`archive:` / `workbench:` / `theme:` / `issue:`），禁止用相对路径或绝对路径链接——这样归档 / 冻结 / 家族迁移时 KF 条目**零改动**。

### 与其他文档的关系

| 目标文档 | 关系 |
|---------|------|
| workbench | 关键发现的**证据源**——workbench 是原始报告，清单只做提炼与索引 |
| archive | 归档后清单条目的"证据"链接从 workbench 路径改指 archive 路径 |
| strategy-math-spec | 若发现修改策略行为，先由发现驱动改 spec，再在清单"影响"段登记 spec 版本变化 |
| freeze-summary.md（归档时）| 归档批次的 `freeze-summary.md` 必须列出"关键发现清单"的所有条目（或直接引用清单），避免归档丢失；清单中**跨主题共通**的方法论 / 证伪结论提炼到 freeze-summary.md 的"共同教训"段 |

### 更新时机

- **每次实验得到明确的支持 / 证伪证据**（不是每个中间数字）：追加或更新条目；
- **发现方法论必需或有伪影**：追加"方法论"类条目；
- **主题归档时**：清单不删除；清单中的"待定/边界"条目若未收敛，需在归档时降级为"未解决观察"（在 freeze-summary.md 中登记）。

### 禁忌

- 关键发现清单**不承载完整策略公式**（那是 spec 的职责）；
- **不承载参数分层规则**（那是 parameter-selection-spec 的职责）；
- **不承载实验流水与原始数字**（那是 workbench / archive 的职责）；
- **禁止孤儿条目**（无证据引用）——任何未指向 archive / workbench / issue 的条目视为无效；
- **禁止在证据字段用相对/绝对路径**——必须用命名引用（`archive:` / `workbench:` / `issue:` / `kf:`），否则归档/冻结时会级联更新。

## 主题目录初始化流程

新增一个策略主题时按下列顺序操作（尽量用 `git mv` 保留 diff 历史）：

1. `mkdir docs/research/themes/<theme-name>/`
2. 从 workbench 迁移已有的数学规格与实验计划：
   - `git mv docs/workbench/<...spec>.md docs/research/themes/<theme-name>/strategy-math-spec.md`
   - `git mv docs/workbench/<...plan>.md docs/research/themes/<theme-name>/experiment-plan.md`
3. 若旧主题现状文件（例如 `docs/research/themes/<theme-name>.md`）存在，`git mv` 到 `research-status.md`。
4. 新建 `README.md, parameter-selection-spec.md, implementation-notes.md`（后两者可先建占位版）。
5. 修正六份文档的相对路径：
   - 主题目录 → `docs/research/archived-notes/**`：`../../archived-notes/...`（共同祖先 `docs/research/`）
   - 主题目录 → `docs/research/**`（同层）：`../...`
   - 主题目录 → `docs/archive/**`（工程类归档 aspects/backtest/infra/deprecated）：`../../../archive/...`
   - 主题目录内部互引：直接文件名，无相对前缀。
6. 更新 `docs/research/strategy-current.md`、`docs/research/README.md`、archive 中的历史文档，把旧路径指向新的主题 README。
7. 全库 `grep` 一次旧文件名，确认无孤立引用。

## Workbench 写法

实验过程默认先写入 `docs/workbench/`：

- 实验问题；
- 结构塑形定义；
- 固定参数组；
- 参数对照与初步结果；
- 受框架 issue 影响的部分；
- 临时结论。

**AI 生成的临时研究资产也全部写入 `docs/workbench/`**，取代旧的 `scripts/ai_tmp/` 与 `project_data/ai_tmp/`：

- 临时分析 / debug / 探查脚本：`docs/workbench/<theme-slug>/scripts/*.py`（或大主题下 `docs/workbench/<theme-slug>-<topic>/scripts/`）；
- 临时策略代码（未进入 `workspace/strategies/` 长期目录的实验策略）：`docs/workbench/<theme-slug>/strategies/*.py`；
- 临时中间数据 / 图表 / parquet / csv 产出：`docs/workbench/<theme-slug>/outputs/`；
- 单文件主题可放在 `docs/workbench/<theme-slug>-<topic>.md` 同级或改用子目录形式；大主题多组件时建议直接使用子目录布局 `docs/workbench/<theme-slug>/`。

工作原则：

- workbench 内容**允许粗糙**，但结论稳定后必须提炼进主题目录或 archive；主题目录**禁止**长期引用 workbench 文件。
- 完整策略公式由 `strategy-math-spec.md` 承载，workbench 中不重复完整公式。
- workbench 下的临时脚本 / 策略 / 数据在归档时一起搬运进 archive 批次（详见 `## Archive 写法`）。

## Archive 写法

**归档范围定义（核心原则 ⭐⭐⭐）**：

一次归档批次的范围是**当前 git 分支中，与本次归档主题 slug 相关的 ALL 文件**，而不仅是 workbench 文件。归档前必须先做"分支差异枚举"，识别以下几类文件：

| 类别 | 路径模式（按主题 slug / 关键词匹配） | 归档后位置 |
|:---|:---|:---|
| workbench 实验流水 | `docs/workbench/<theme-slug>-*.md` 或 `docs/workbench/<theme-slug>/*.md` | `<batch>/` 根目录（压缩版）+ `<batch>/raw-workbench/`（原始版，若需保留多份） |
| 临时分析脚本 | `docs/workbench/<theme-slug>/scripts/` · 或分支中新增/修改且仅服务于该主题的脚本 | `<batch>/raw-scripts/` |
| 临时策略代码 | `docs/workbench/<theme-slug>/strategies/` · 分支中新增且未进入 `workspace/strategies/` 长期目录的临时策略；或 `workspace/strategies/*<theme-slug>*` 中未通过验证的临时策略 | `<batch>/raw-strategies/` |
| 临时中间数据 | `docs/workbench/<theme-slug>/outputs/` 下由本次实验产生的 parquet / csv / 图像（大文件不移动，只在 README 登记路径） | **不移动文件本身**，只在 `<batch>/README.md` 登记绝对路径和文件 hash / 行数 |
| 主题目录长期文档（experiment-plan / research-status 等） | 不归档，保留在 `docs/research/themes/<theme-slug>/` | — |
| 框架 issue | `docs/issues/` 不移动，archive 只做命名引用 | — |

**识别方法**：
- `git diff --name-only <base-branch>...HEAD` 枚举本分支相对基线（通常 master / main）的所有差异文件
- 按主题 slug / 关键词（如 `poc-va` / `value-area` / `<experiment-plan 中定义的主题标签>`）过滤
- 对边界模糊的文件（共用脚本）· 判断"没有该主题就不会存在/修改该文件" → 归档；否则保留
- 数据文件（>10MB）一律不搬运，只登记路径

**压缩原则**：删废话、删弯路、删无价值信息。**不做"必须压缩多少"的硬性要求**——如果内容已经足够精炼、无冗余、每一段都有长期价值，可以整段搬运不改动。压缩是手段，不是目的。

**保留**（若存在且有长期价值）：

- 核心问题；
- 实验定义；
- 固定参数；
- 关键结果；
- 结论；
- 对后续研究有用的信息；
- 必要复现备注。

**删除**（若存在）：

- 过程性计划、被推翻的中间假设；
- 重复的判断标准（skill / spec 已写清一次即可）；
- 过期工具限制、已修复的框架 issue 复述；
- 不存在策略的可执行命令；
- 走过又放弃的弯路描述（若不构成 KF 或方法论证据，删）；
- 不再有长期价值的中间描述。

**判据**：**"未来读者需要它做出决策吗？"** 需要则保留，不需要则删。判断困难时倾向保留，宁可稍冗余不要丢失证据链。

归档路径：

```text
（分支相关文件）
  docs/workbench/<name>.md
    -> <archive-batch>/<compressed-name>.md （压缩版，根目录）
    -> <archive-batch>/raw-workbench/<name>.md （原始版，多文件时）
  docs/workbench/<theme>/scripts/*     -> <archive-batch>/raw-scripts/
  docs/workbench/<theme>/strategies/*  -> <archive-batch>/raw-strategies/
  workspace/strategies/*<theme>*       -> <archive-batch>/raw-strategies/（仅未通过验证的临时策略）
  （数据文件不搬运，只登记）
```

`<archive-batch>` = `docs/research/archived-notes/<YYYY-MM-DD>-<slug>/`

移动后修正相对链接：

- archive → roadmap：`../../roadmap/...`
- archive → issues：`../../issues/...`
- archive → 主题目录 README：`../../research/themes/<theme-name>/README.md`
- issue → archive：`../research/archived-notes/<archive-batch>/...`

若主题目录里的某份文件（例如 `research-status.md`）引用 archive，**优先使用命名引用 `archive:<batch>#<file>`**；确需相对路径时用 `../../archived-notes/...`（源在 `docs/research/themes/<slug>/`，目标在 `docs/research/archived-notes/`，共同祖先是 `docs/research/`，故 `../../` 层足够）。

### 归档动作的原子步骤（必须一次完成）

一次归档批次到 `docs/research/archived-notes/<archive-batch>/` **不是**单纯的移动 workbench 动作，它包含以下**原子步骤，缺一不可**：

1. **Step 0 · 枚举归档范围（分支差异扫描）**：
   - `git diff --name-only <base-branch>...HEAD` 得到本分支相对基线的 ALL 改动文件；
   - 按主题 slug / 关键词过滤，建立候选清单（workbench + 脚本 + 策略 + 数据产出）；
   - 对每个文件做"是否专属于本主题"判断，确定最终归档文件清单；
   - 对数据文件（>10MB 或 parquet/npy 二进制）· 决定"只登记不搬运"并记录路径 + md5/行数。
2. **Step 1 · 审阅 ALL 归档范围文件内容**：
   - workbench 按"删除清单"清理废话/弯路/无价值信息；已足够精炼可跳过压缩直接搬运；
   - 临时脚本和策略 · 检查是否有外部依赖需要记录在 README 的复现备注。
3. **Step 2 · 移动/拷贝文件到批次子目录**：
   - `git mv docs/workbench/<name>.md <archive-batch>/<compressed-name>.md`（压缩版放根目录）；
   - 若归档文件数 ≥ 3（多 workbench / 多脚本）· 建 `raw-workbench/` `raw-scripts/` `raw-strategies/` 三个子目录存放原始版；
   - 共用脚本（非专属）不移动，在 README 注明引用路径。
4. **Step 3 · 修正 archive 内部相对链接**（roadmap / issues / 主题 README）· 将 markdown 相对路径链接升级为命名引用。
5. **Step 4 · 只更新归档主题自己的 `archive-references.md`**（O(1) 动作）：
   - 归档批次天然属于某个"归档主题"（枚举文件时已识别）；
   - 归档者只在**该主题**的 `archive-references.md` 里追加一条自登记条目，
     关系类型通常是"继承 / 阶段归档 / 主题冻结"；
   - **不扫描其他主题**——跨主题反向登记走 pull 模式（见下节）。
6. **Step 5 · 修正原主题目录内引用了被归档路径的文档**：
   - **命名引用**（`workbench:<name>`）改为 `archive:<batch>#<file-stem>`——一次全库替换即可，无 KF 数级联；
   - **历史 markdown 相对路径链接**（若存在）仍需更新——建议一并升级为命名引用以避免下次归档再改；
   - 检查脚本/策略被删后：文档中不能留下直接可执行但实际不存在的 `--strategy <name>` 或脚本路径。
7. **Step 6 · 提交前 `grep` 一次旧路径 + 旧 `workbench:` 标签 + 已删除脚本/策略名**，确认无孤立引用。
8. **Step 7 · 若顶层索引 `docs/research/archived-notes/README.md` 已存在**：追加一行本批次记录（日期 / 家族 / topic / 结论标签，O(1)）；不存在但批次数达到 ≥10 阈值时，本次归档一并创建索引。

**任一步骤缺失都视为"归档未完成"**，不允许合并到长期分支。

**注意：步骤 4 是 O(1) 而非 O(N)**——归档者不承担枚举全库主题、判断相关性的责任。跨主题反向引用由**下游主题维护者按需拉取**（见下节）。

### 跨主题反向登记（Pull 模式，非归档者的责任）

archive 的反向索引由**下游主题维护者主动拉取**，而不是归档者广播推送。触发时机：

- **主题立题时**：主题维护者在创建 `archive-references.md` 时，扫描已存在的 archive；**采用截断策略**避免随 archive 目录规模线性增长（见下节）；
- **主题实际引用某 archive 时**：无论是在 KF 清单的证据链接、experiment-plan 的方法论继承、还是 spec 的公式参考中，**只要主题内文档实际引用某 archive**，就在同一次 commit 中把该 archive 登记到 `archive-references.md`；

**判定原则**：**引用触发登记，不引用不登记**。这样 archive-references.md 只包含"真正被本主题读取过的 archive"，避免预防性登记膨胀。

**归档时的最小提示（可选）**：归档者可以在归档 commit message 里加一行"可能相关的主题：X/Y/Z"作为提示，但**不强制**下游主题维护者立即登记——他们在下一次实际引用时登记即可。

### 立题扫描 archive 的截断策略

`docs/research/archived-notes/` 是**时间前缀 + 家族 slug** 的自然索引
（`YYYY-MM-DD-<slug>/`），立题时**不需要**逐个打开旧批次的 summary，
按下列三重截断阅读即可：

1. **家族截断（首要）**：先按 slug 前缀匹配同家族（如新主题属于
   `structural-*`，先看所有 `*structural*` 批次），家族内的 archive
   必读；
2. **时间截断（次要）**：跨家族批次只看**近 2 周**（按目录名日期前缀
   排序倒序，超出窗口的跳过）；更早的跨家族 archive **不主动登记**，
   走 pull 模式（真被引用时再登记）；
3. **索引先读**：优先阅读顶层索引 `docs/research/archived-notes/README.md`
   （批次 → 家族 → topic → 一句话结论）而不是逐个打开 summary；
   索引不存在时使用 `ls docs/research/archived-notes/ | tail -20`
   查看最近 20 个批次名，按名字判断相关性再决定是否深读。

**渐进登记原则**：立题扫描后 archive-references 只包含"高相关性 + 家族
内的 + 近期的"批次；主题推进过程中若发现远期或跨家族的 archive 与本
主题相关，pull 模式即时登记即可。**不追求立题时 archive-references
的"完备性"**——它是动态索引，不是静态目录快照。

### 顶层索引 README.md（archive 目录）

**当 `docs/research/archived-notes/` 批次数 ≥ 10 时必须建立**，减少后续
立题扫描成本：

- 路径：`docs/research/archived-notes/README.md`；
- 内容：**每行一个批次**，含 `日期 | 家族 slug | topic 一句话 | 结论标签
  (✅ 通过 / ❌ 证伪 / 🧪 方法论 / ⚠️ 分流 / 🔁 转主线，可组合)`；
- 归档原子步骤新增：**批次数达到阈值后**，每次归档必须同步在顶层索引
  追加一行（O(1)），保持索引与目录同步。

批次数 < 10 时可省略该索引，立题者直接 `ls` 一遍即可。

## archive-references.md 写法

每个活跃主题目录**必须**有一份 `archive-references.md`，用于回答：
"`docs/research/archived-notes/` 中哪些目录与本主题相关，各自是什么关系？"

### 何时创建 / 更新

采用 **pull 模式**——引用触发登记，不引用不登记。具体时机：

- **主题立题时**：创建 `archive-references.md`，扫描已存在的 archive，登记与本主题相关的批次（一次性动作）；
- **归档主题自己产生新 archive 批次时**：归档原子步骤 4 追加一条自登记条目（O(1)，见 `## Archive 写法 § 归档动作的原子步骤`）；
- **主题内任何文档实际引用某 archive 时**（KF 清单证据 / experiment-plan 方法论继承 / spec 公式参考）：在同一次 commit 中登记该 archive 到 `archive-references.md`；
- **关系类型变化**（如原本作为"反例"引用，后续升级为"数据复用"）：更新条目。

**不做**的：
- 归档者**不广播**给其他主题（跨主题反向登记走 pull 模式）；
- 不做**预防性登记**（可能被引用但暂未引用的 archive 不登记）。

### 必备内容

- **archive 目录清单**：每条记录包含 (1) `archive:<batch-name>` 命名引用（**唯一定位方式**，禁止用路径），(2) 关系类型（继承 / 反例 / 数据复用 / 代码复用 / 方法论遗产），(3) 一句话说明"这个 archive 对本主题意味着什么"；
- **关系说明**：为什么这个 archive 值得被本主题引用？它证伪 / 支撑 / 铺垫了本主题的哪个假设？
- **禁忌**：archive-references.md 不承载策略公式、不承载实验流水、不承载归档内容的完整复述——它只是**索引 + 关系标签**。

### 示例条目

```markdown
### archive:2026-07-05-value-area-rolling-reacceptance-freeze
- 关系类型：反例 + 方法论遗产
- 说明：value-area 家族最终证伪批次；本主题继承其 ATR 归一化、期望净值、
  cluster bootstrap、多层对照四大方法论约束，但假设正交（结构塑形独立 alpha
  vs 触发器均值回归），不复用其结论。
- 相关文件：archive:2026-07-05-value-area-rolling-reacceptance-freeze#freeze-summary
```

### 与 archive 反向索引的关系

- archive 本身不维护"哪些主题引用我"的反向清单；由每个主题的
  `archive-references.md` 单向登记；

## Issues 工作流

当实验中发现问题不再属于策略逻辑，而可能来自底层框架时，先写 `docs/issues/` 并**暂停受影响实验**：

- 回测引擎统计口径异常；
- DataFeed / 缓存 / 周期加载不一致；
- vnpy 桥接、开平仓、成交配对异常；
- CLI / runner 与策略 `data_requirements` 不一致；
- 指标、成本、滑点、手续费、PnL 等基础口径存在疑问。

issue 修复后：

- 状态改为"已验证"；
- 回填 `修复提交 hash`；
- 若关联实验已归档，issue 链接应指向 archive 路径。

## Roadmap 边界

- roadmap 只维护阶段目标、评价标准、候选方向。
- 不把具体实验方向、开发分支、分支 hash、参数对照、中间结果直接写入 roadmap。
- 若需要说明与研究文档的关系，可在 roadmap 顶部 meta 中写"文档边界"。

## 策略代码保留 / 删除规则

- 已通过或仍在活跃研究的策略，保留在 `workspace/strategies/`。
- 未通过实验的临时策略代码，默认不污染长期策略目录。
- 删除失败实验策略代码时，文档中不能留下直接可执行但实际不存在的 `--strategy <name>` 命令。
- 若未来需要复现失败实验，在 archive 文档中保留结构定义与参数，让后续按定义重新实现最小策略。

## 与其他 skill 的边界

- `strategy-math-spec.md` 本身的写法、记号、静态一致性检查：`quant-math-spec`。
- 回测运行、CLI 命令、样本切换：`quant-cli`。
- 项目基础设施与代码分区：`quant-project`。
