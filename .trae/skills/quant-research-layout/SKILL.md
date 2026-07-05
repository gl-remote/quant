---
name: "quant-research-layout"
description: "Rules for quant research document layout: theme directory, workbench, archive, issues, roadmap boundaries and cross-doc flows. Invoke when creating theme directories, writing non-spec research docs, migrating workbench notes, archiving, or filing issues."
---

# Quant Research Layout

本 skill 覆盖 quant 项目所有研究文档的**目录布局与跨文档流程**，包括：

- 主题目录（`docs/research/themes/<theme-name>/`）的固定布局与文件分工；
- workbench / archive / issues / roadmap 各自的边界与写法；
- 主题目录初始化、workbench 归档、issues 处理等跨文档流程。

`strategy-math-spec.md` 本身的写法（结构、数学记号、静态一致性检查）由 `quant-math-spec` 负责，本 skill 不重复。

## 触发时机

- 新建一个策略主题目录；
- 修改主题目录内除 `strategy-math-spec.md` 之外的任意文档；
- 判断某段内容应放到 workbench / theme / archive / issues 中哪个位置；
- 把 workbench 中的实验记录归档；
- 发现底层框架问题需要开 issue；
- 修 roadmap 或 research 目录索引文件。

## 顶层目录边界

| 目录 | 用途 | 允许放什么 | 禁止放什么 |
|---|---|---|---|
| `docs/roadmap/` | 阶段规划、评价标准 | 阶段目标、候选方向、评价指标 | 具体实验方向、分支 hash、参数对照、中间结果 |
| `docs/research/` | 研究总入口与主题目录 | `strategy-current.md`（全局入口）、`README.md`、`themes/<theme-name>/`、`themes-frozen/<family>/<theme-name>/` | 具体实验流水 |
| `docs/research/themes/` | **活跃**策略主题（研究中 / 待启动 / 阶段性暂停但可能恢复） | 见"主题目录布局" | 已冻结的主题 |
| `docs/research/themes-frozen/` | **已冻结**策略主题（假设证伪 / feature-only 降级 / 主策略不再作为独立候选） | 按家族聚合的冻结主题目录、家族级 README | 活跃研究、任何仍在推进的实验 |
| `docs/workbench/` | 当前研究中的实验流水 | 实验问题、临时参数对照、中间结果、临时结论 | 长期规格、策略契约 |
| `docs/issues/` | 底层框架问题 | 引擎 / 数据管道 / CLI / 成本口径等非策略问题 | 策略结论 |
| `docs/archive/strategy-research/` | 已完成阶段的压缩摘要 | 核心问题、实验定义、固定参数、关键结果、结论 | 过程性计划、过期工具限制 |

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

- **主题 slug 全局唯一**：`docs/research/themes/*` 与 `docs/research/themes-frozen/*/*` 合并后不得出现同名 slug。
- **archive 批次目录名全局唯一**（自然满足：日期前缀 + slug）。
- **workbench 文件名 / 主题内多文件时的子目录名全局唯一**：`docs/workbench/<theme-slug>-<topic>.md` 或 `docs/workbench/<theme-slug>/<topic>.md`。
- **family slug 全局唯一**：`themes-frozen/<family>/` 家族名不得与主题 slug 冲突。
- **issue 文件名全局唯一**：`docs/issues/<slug>.md`。

**立题 / 建家族 / 归档新批次前**：`grep -r "<候选 slug>" docs/research docs/archive docs/workbench` 一次，确认无重名。发现冲突时 slug 加限定后缀（如 `value-area-reacceptance-2`）而不是复用。

## 命名引用协议（Named Reference Protocol）

**跨文档引用一律用命名标签，不写路径**。这是解决路径耦合与迁移膨胀的核心规则。

### 标签前缀 → 位置的映射（权威表）

| 前缀 | 语法 | 解析位置 | 说明 |
|------|------|---------|------|
| `archive:` | `archive:<name>` | `docs/archive/strategy-research/<name>/` | `<name>` 是完整批次目录名（含日期前缀） |
| `archive:` | `archive:<name>#<file-stem>` | `docs/archive/strategy-research/<name>/<file-stem>.md` | 指向批次内某具体报告 |
| `theme:` | `theme:<slug>` | `docs/research/themes/<slug>/` **或** `docs/research/themes-frozen/<family>/<slug>/`（自动判定，活跃优先） | 主题目录本身 |
| `theme:` | `theme:<slug>#<file-stem>` | 上述目录下 `<file-stem>.md` | 主题内某文档 |
| `family:` | `family:<slug>` | `docs/research/themes-frozen/<slug>/` | 家族目录 |
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
- **themes → themes-frozen**：`theme:` / `archive:` / `kf:` 全部**不动**（解析规则自动切换活跃/冻结）；
- **家族合并/重命名**：`family:` 若变名需要 sweep，但只是一处标签串改，不涉及路径深度。

### AI 读取协定

AI 看到命名引用时按上表映射立即调 `Read` / `LS`。不需要打开当前文档所在目录做相对路径心算。

### 命名引用与 archive 顶层索引的关系

archive 顶层索引 [`docs/archive/strategy-research/README.md`](../../archive/strategy-research/README.md) 的"家族 slug"列即 `family:` 前缀的解析源；"日期"列即 `archive:` 前缀日期段的解析源；两者共同构成命名引用的**权威索引表**。

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
| 家族 README（冻结时）| 主题冻结后，清单中**跨主题共通**的方法论 / 证伪结论必须提炼到家族级 README 的"共同教训"段（清单本身随主题一起 git mv 到 themes-frozen） |
| freeze-summary.md（冻结时）| 归档批次的 `freeze-summary.md` 必须列出"关键发现清单"的所有条目（或直接引用清单），避免归档丢失 |

### 更新时机

- **每次实验得到明确的支持 / 证伪证据**（不是每个中间数字）：追加或更新条目；
- **发现方法论必需或有伪影**：追加"方法论"类条目；
- **主题冻结时**：清单不删除；清单中的"待定/边界"条目若未收敛，需在冻结时降级为"未解决观察"（在家族 README 中登记）。

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
   - 主题目录 → `docs/archive/**`：`../../../archive/...`
   - 主题目录 → `docs/research/**`（同层）：`../../...`
   - 主题目录内部互引：直接文件名，无相对前缀。
6. 更新 `docs/research/strategy-current.md`、`docs/research/README.md`、archive 中的历史文档，把旧路径指向新的主题 README。
7. 全库 `grep` 一次旧文件名，确认无孤立引用。

## 主题冻结与家族聚合流程

### 何时冻结主题

一个主题满足以下**任意一条**后，应从 `docs/research/themes/` 迁到
`docs/research/themes-frozen/<family>/<theme-name>/`：

- **假设完全证伪**：核心假设链在多层对照下被独立证伪（例如
  `value-area-rolling-reacceptance`：POC 特殊性 / rolling 独立价值 /
  reacceptance 触发器 / 距离档 edge 均被证伪）；
- **feature-only 降级 + 主策略暂停**：主策略不再作为独立候选，只保留 feature
  语义供其他主题引用（例如 `value-area-reacceptance`）；
- **主策略退役 ≥ 一个季度且无恢复计划**。

**不冻结**的场景：仍在广度扫描 / 参数调整 / 换周期换品种验证的主题——保留在
`themes/`，通过 `research-status.md` 反映当前状态即可。

### 家族聚合规则

多个"共享核心假设 / 前后置继承关系 / 命名共前缀"的冻结主题应聚合到一个家族目录：

```text
docs/research/themes-frozen/<family>/
├── README.md                        # 家族级总结：关系图、共同教训、方法论遗产
├── <theme-name-1>/                  # 家族成员（保持原主题目录布局）
│   └── ...
└── <theme-name-2>/
    └── ...
```

**家族命名**：kebab-case，取共同 slug 前缀（例如 `value-area`、`breakout`、
`trend-pullback`）。单主题冻结时，若可预见未来同家族其他主题也会冻结，也可
直接建家族目录，只放一个成员。

**家族级 README 必须包含**：

- 成员主题列表 + 各自冻结原因；
- 成员之间的继承关系或差异；
- 共同教训与方法论遗产（每个主题不重复写，家族层统一登记）；
- 引用规则（是否允许后续主题引用某成员的 feature / 方法 / 数据）。

### 冻结迁移流程

**冻结单个主题**（首次进入 themes-frozen）：

1. 决定家族：若已有家族目录则复用；否则新建 `themes-frozen/<family>/`；
2. `git mv docs/research/themes/<theme-name> docs/research/themes-frozen/<family>/<theme-name>`；
3. 修正该主题目录内所有文件的**历史 markdown 相对路径链接**：
   - → `docs/archive/**`：从 `../../../archive/...` 改为 `../../../../archive/...`（多一层 `..`）；
   - → `docs/research/**`（同层）：从 `../../...` 改为 `../../../...`；
   - 主题目录内部互引：不变。
   - **命名引用（`archive:` / `theme:` / `kf:` / `family:` / `issue:` / `roadmap:` / `workbench:`）零改动**——迁移后解析规则自动切换活跃/冻结。
4. 主题 `README.md` 顶部标记 `Frozen <date>`，`research-status.md` 结论段落
   给出冻结原因与保留资产；
5. **搬运"关键发现清单"**：
   - `research-status.md` 中的关键发现清单**原样保留**（历史不删）；
   - 归档批次 `freeze-summary.md` 必须列出全部条目（或引用清单）；
   - 清单中**跨主题共通**的方法论 / 证伪结论提炼到家族 README 的"共同教训"段；
   - 清单中未收敛的"边界待定"条目降级为家族 README 的"未解决观察"。
6. 更新 `docs/research/README.md` 与 `docs/research/strategy-current.md`：
   路径改为 `themes-frozen/<family>/<theme-name>/`，状态改为"已冻结"；
7. 更新反向引用的 archive 文档中的主题路径；
8. 全库 `grep` 旧路径 `themes/<theme-name>`，把仍应指向主题目录的引用改到
   新路径（archive 内部指向已归档 workbench 的除外）。

**新增家族成员**（家族目录已存在）：

- 复用上面 2-7 步；
- 更新家族 README 的成员列表 + 关系图 + 共同教训段。

### 冻结主题的写作纪律

- 冻结主题目录**只读**：不再修改 `strategy-math-spec.md` /
  `experiment-plan.md` / `parameter-selection-spec.md` /
  `implementation-notes.md`；仅允许更新 `research-status.md` 的"下一步"段落
  以反映家族层决策变化。
- 冻结主题**不建 workbench**：若发现新观察需要验证，属于**立新主题**的
  范畴，不能污染已冻结主题的目录。
- 冻结主题被引用的**唯一入口**是主题 `README.md`（顶部标 Frozen）或家族
  `README.md`；后续主题不得直接跳过 README 引用某内部文件。
- 冻结主题的**代码资产已在归档时随 archive 保存副本**（`raw-scripts/` 等）；
  themes-frozen 目录只保留文档，不再放代码。

## Workbench 写法

实验过程默认先写入 `docs/workbench/`：

- 实验问题；
- 结构塑形定义；
- 固定参数组；
- 参数对照与初步结果；
- 受框架 issue 影响的部分；
- 临时结论。

工作原则：

- workbench 内容**允许粗糙**，但结论稳定后必须提炼进主题目录或 archive；主题目录**禁止**长期引用 workbench 文件。
- 完整策略公式由 `strategy-math-spec.md` 承载，workbench 中不重复完整公式。

## Archive 写法

归档前必须压缩，只保留未来有用的信息：

- 核心问题；
- 实验定义；
- 固定参数；
- 关键结果；
- 结论；
- 对后续研究有用的信息；
- 必要复现备注。

删除：

- 过程性计划；
- 重复判断标准；
- 过期工具限制；
- 不存在策略的可执行命令；
- 不再有长期价值的中间描述。

归档路径：

```text
docs/workbench/<name>.md
-> docs/archive/strategy-research/<archive-batch>/<name>.md
```

移动后修正相对链接：

- archive → roadmap：`../../roadmap/...`
- archive → issues：`../../issues/...`
- archive → 主题目录 README：`../../research/themes/<theme-name>/README.md`
- issue → archive：`../archive/strategy-research/<archive-batch>/...`

若主题目录里的某份文件（例如 `research-status.md`）引用 archive，档路径用 `../../../archive/...`。

### 归档动作的原子步骤（必须一次完成）

一次归档批次到 `docs/archive/strategy-research/<archive-batch>/` **不是**单纯的移动动作，它包含以下**原子步骤，缺一不可**：

1. **压缩 workbench 内容**到 archive 目录（按上面"归档写法"的保留/删除清单）；
2. **移动 workbench 文件** `git mv docs/workbench/<name>.md docs/archive/strategy-research/<archive-batch>/<name>.md`；
3. **修正 archive 内部相对链接**（roadmap / issues / 主题 README）；
4. **只更新归档主题自己的 `archive-references.md`**（O(1) 动作）：
   - 归档批次天然属于某个"归档主题"（workbench 文件本来就是该主题的产物）；
   - 归档者只在**该主题**的 `archive-references.md` 里追加一条自登记条目，
     关系类型通常是"继承 / 阶段归档"；
   - **不扫描其他主题**——跨主题反向登记走 pull 模式（见下节）。
5. **修正原主题目录内引用了这些 workbench 路径的文档**：
   - **命名引用**（`workbench:<name>`）改为 `archive:<batch>/<name>` 或 `archive:<batch>#<file-stem>`——一次全库替换即可，无 KF 数级联；
   - **历史 markdown 相对路径链接**（若存在）仍需 sed 更新——建议一并升级为命名引用以避免下次归档再改；
6. **提交前 `grep` 一次旧 workbench 路径 + 旧 `workbench:` 标签**，确认无孤立引用；
7. **若顶层索引 `docs/archive/strategy-research/README.md` 已存在**：追加一行本批次记录（日期 / 家族 / topic / 结论标签，O(1)）；不存在但批次数达到 ≥10 阈值时，本次归档一并创建索引。

**任一步骤缺失都视为"归档未完成"**，不允许合并到长期分支。

**注意：步骤 4 是 O(1) 而非 O(N)**——归档者不承担枚举全库主题、判断相关性的责任。跨主题反向引用由**下游主题维护者按需拉取**（见下节）。

### 跨主题反向登记（Pull 模式，非归档者的责任）

archive 的反向索引由**下游主题维护者主动拉取**，而不是归档者广播推送。触发时机：

- **主题立题时**：主题维护者在创建 `archive-references.md` 时，扫描已存在的 archive；**采用截断策略**避免随 archive 目录规模线性增长（见下节）；
- **主题实际引用某 archive 时**：无论是在 KF 清单的证据链接、experiment-plan 的方法论继承、还是 spec 的公式参考中，**只要主题内文档实际引用某 archive**，就在同一次 commit 中把该 archive 登记到 `archive-references.md`；
- **家族聚合时**：主题冻结进入 `themes-frozen/<family>/` 时，家族维护者把该主题的 archive-references 中的方法论 / 反例条目提炼到家族 README。

**判定原则**：**引用触发登记，不引用不登记**。这样 archive-references.md 只包含"真正被本主题读取过的 archive"，避免预防性登记膨胀。

**归档时的最小提示（可选）**：归档者可以在归档 commit message 里加一行"可能相关的主题：X/Y/Z"作为提示，但**不强制**下游主题维护者立即登记——他们在下一次实际引用时登记即可。

### 立题扫描 archive 的截断策略

`docs/archive/strategy-research/` 是**时间前缀 + 家族 slug** 的自然索引
（`YYYY-MM-DD-<slug>/`），立题时**不需要**逐个打开旧批次的 summary，
按下列三重截断阅读即可：

1. **家族截断（首要）**：先按 slug 前缀匹配同家族（如新主题属于
   `structural-*`，先看所有 `*structural*` 批次），家族内的 archive
   必读；
2. **时间截断（次要）**：跨家族批次只看**近 2 周**（按目录名日期前缀
   排序倒序，超出窗口的跳过）；更早的跨家族 archive **不主动登记**，
   走 pull 模式（真被引用时再登记）；
3. **索引先读**：优先阅读顶层索引 `docs/archive/strategy-research/README.md`
   （批次 → 家族 → topic → 一句话结论）而不是逐个打开 summary；
   索引不存在时使用 `ls docs/archive/strategy-research/ | tail -20`
   查看最近 20 个批次名，按名字判断相关性再决定是否深读。

**渐进登记原则**：立题扫描后 archive-references 只包含"高相关性 + 家族
内的 + 近期的"批次；主题推进过程中若发现远期或跨家族的 archive 与本
主题相关，pull 模式即时登记即可。**不追求立题时 archive-references
的"完备性"**——它是动态索引，不是静态目录快照。

### 顶层索引 README.md（archive 目录）

**当 `docs/archive/strategy-research/` 批次数 ≥ 10 时必须建立**，减少后续
立题扫描成本：

- 路径：`docs/archive/strategy-research/README.md`；
- 内容：**每行一个批次**，含 `日期 | 家族 slug | topic 一句话 | 结论标签
  (✅ 通过 / ❌ 证伪 / 🧪 方法论 / ⚠️ 分流 / 🔁 转主线，可组合)`；
- 归档原子步骤新增：**批次数达到阈值后**，每次归档必须同步在顶层索引
  追加一行（O(1)），保持索引与目录同步。

批次数 < 10 时可省略该索引，立题者直接 `ls` 一遍即可。

## archive-references.md 写法

每个活跃主题目录**必须**有一份 `archive-references.md`，用于回答：
"`docs/archive/strategy-research/` 中哪些目录与本主题相关，各自是什么关系？"

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
- 家族级 README（`themes-frozen/<family>/README.md`）也可以在"方法论遗产"
  段引用 archive，但**主题级 archive-references.md 仍是主索引**。

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
