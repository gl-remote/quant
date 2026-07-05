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
└── implementation-notes.md      # 工程实现细节（数据结构 / 缓存 / 桥接 / 性能）
```

### 文件分工（严禁越界）

| 文档 | 回答 | 谁改 | 什么时候改 |
|---|---|---|---|
| README.md | 主题目录索引与阅读顺序 | 主题维护者 | 目录成员变化时 |
| research-status.md | 主题当下的一句话结论、边界、下一步 | 策略研究者 | 结论变化时 |
| strategy-math-spec.md | 策略"是什么"（数学契约） | 策略研究者 | 行为变更前 |
| experiment-plan.md | "怎么验证"（候选矩阵、验证顺序、判据） | 策略研究者 | 实验路径变化时 |
| parameter-selection-spec.md | "怎么选参数"（分层、判据、流程、回填格式） | 策略研究者 | 实验后 |
| implementation-notes.md | "怎么实现"（工程细节、优化选择、性能数据） | 实现者 | 实现开始 / 完成时 |

### 跨文档硬约束

- `strategy-math-spec.md` 是**唯一**定义策略行为的文档；其他五份文档均不得定义或改变策略行为。
- 若 `implementation-notes.md` 中的某项工程决定影响了语义，先回改 `strategy-math-spec.md`，再更新 `implementation-notes.md`。
- 若 `parameter-selection-spec.md` 需要一个 spec 未定义的参数，先在 `strategy-math-spec.md` 补声明。
- `experiment-plan.md` 与 `parameter-selection-spec.md` 都可以引用 spec，但不能复述完整策略公式。
- `research-status.md` 只承载"结论、边界、下一步"，不承载策略公式，不承载实验流水，不承载工程细节。
- 主题目录中的文档**不允许**依赖 workbench 中的临时文件；workbench 的稳定结论必须归档到 archive，主题目录再引用 archive。
- **workbench 目录只有一个，位于 `docs/workbench/`**（顶层）。**禁止**在主题目录（`docs/research/themes/<theme-name>/`）下再建 `workbench/` 子目录。所有实验流水、临时报告、driver 输出统一写到 `docs/workbench/<theme-slug>-<topic>.md` 或 `docs/workbench/<theme-slug>/<topic>.md`（大主题内多份文件时才建子目录，且该子目录必须直属 `docs/workbench/`）。

### 命名规则

- 主题目录名 = 策略主题 slug（kebab-case，如 `value-area-reacceptance`）。
- 目录内文件名固定为上表六个，作用一目了然，禁止使用过于泛化的 `spec.md / plan.md / current.md`。
- 若主题需要额外辅助文档（数据字段词表、诊断字段清单等），也放同目录并在 README 的"文档地图"中登记。

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
3. 修正该主题目录内所有文件的相对路径：
   - → `docs/archive/**`：从 `../../../archive/...` 改为 `../../../../archive/...`（多一层 `..`）；
   - → `docs/research/**`（同层）：从 `../../...` 改为 `../../../...`；
   - 主题目录内部互引：不变。
4. 主题 `README.md` 顶部标记 `Frozen <date>`，`research-status.md` 结论段落
   给出冻结原因与保留资产；
5. 更新 `docs/research/README.md` 与 `docs/research/strategy-current.md`：
   路径改为 `themes-frozen/<family>/<theme-name>/`，状态改为"已冻结"；
6. 更新反向引用的 archive 文档中的主题路径；
7. 全库 `grep` 旧路径 `themes/<theme-name>`，把仍应指向主题目录的引用改到
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
