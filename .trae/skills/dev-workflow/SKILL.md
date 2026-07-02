---
name: "dev-workflow"
description: "Runs the quant dev branch workflow. Invoke when starting work, committing, archiving research, merging to dev, or pushing quant changes."
---

# Dev Workflow

用于本 quant 项目的固定开发、提交、归档、合并和推送流程。

## 触发条件

当用户说类似以下内容时启用：

- “开始做这个功能”
- “新开一个开发任务”
- “这个 roadmap 开始实现”
- “清理代码，然后提交一下”
- “代码归档，然后合并到 dev/0.5”
- “可以合并了”
- “合并到 dev”
- “走开发流程”
- “按固定流程提交/合并”
- “git push”

## 新开发任务流程

1. 确认目标 dev 分支和任务范围。
   - 目标 dev 分支必须匹配 `dev/*`；通常选择最高版本的 `dev/*` 分支。
   - 不在 `main` / `master` 上直接开发。
2. 更新目标 dev 分支（仅在新建分支前）。
   - 切换到目标 dev 分支。
   - 按仓库当前策略拉取最新代码。
   - 记录更新后的目标 dev `HEAD` 作为开分支 hash。
3. 从目标 dev 分支新建独立开发分支。
   - 分支名前缀按任务类型选择：`feature/`、`fix/`、`experiment/`。
   - 如果任务有关联 roadmap 文档，优先让分支名和 roadmap 文件名或任务名对应。
4. 记录开分支 hash。
   - `开分支 hash` 是创建开发分支时目标 dev 分支的 `HEAD`。
   - 这个 hash 在开分支时即可记录，不等到提交后再补。
5. 文档元数据写入边界：
   - roadmap 默认只维护阶段目标、评价标准和候选方向。
   - 具体实验方向、开发分支、开分支 hash、参数对照和中间结果写入 `docs/workbench/`。
   - 不要把实验过程和开发分支信息直接写入 roadmap，除非用户明确要求 roadmap 记录流程约束。
6. 如果没有关联 roadmap / workbench 文档，不主动创建文档；只在最终回复中说明开发分支和相关 hash。
7. 开发完成并提交后，回填 `实现提交 hash`。
   - `实现提交 hash` 是开发分支上完成该任务的提交 hash。
   - 如果一个任务包含多个实现提交，可记录最终提交 hash；必要时记录 commit range，例如 `abc1234..def5678`。
8. 不把 `合并提交 hash` 作为必填 meta。
   - 合并提交 hash 只有合回 dev 后才可能明确，且可能因为 merge、squash、fast-forward 策略不同而不存在或语义不同。
   - 如用户明确要求，可在合并后再补充。

## 代码清理与提交流程

当用户要求“清理代码，然后提交”时：

1. 检查当前状态：
   - `git status --short --branch`
   - `git diff --stat`
   - `git log --oneline -5`
2. 分类本次文件：
   - 应保留：已验证功能代码、测试、长期有效的流程文档、已修复 issue 记录。
   - 应归档：已完成且有未来参考价值的实验摘要，从 `docs/workbench/` 移到 `docs/archive/strategy-research/`。
   - 应删除：未通过实验的临时策略代码、不可维护的一次性脚本、过期复现命令、会污染长期目录的实验产物。
3. 清理后修正文档链接：
   - workbench → archive 后，所有相对链接必须重算。
   - issue 中的“关联实验”必须指向最终 archive 路径。
   - 如果删除实验策略代码，文档中不能留下可直接执行但实际不存在的策略命令。
4. 运行必要验证。
5. 提交前只 stage 明确相关文件，避免 `git add .` / `git add -A`。
6. 使用 HEREDOC 写 commit message。
7. 提交后如需回填 hash：
   - 用一个后续 docs commit 回填 `实现提交 hash` / `修复提交 hash`。
   - 先回填功能提交 hash，而不是回填元数据提交自身。

## 研究归档流程

当用户要求“代码归档”或实验完成时：

1. 确认实验文档是否已压缩：
   - 保留核心问题、实验定义、固定参数、关键结果、结论、未来有用信息。
   - 删除过程性计划、重复判断标准、过期工具限制、不可用命令。
2. 将稳定实验摘要从：

   ```text
   docs/workbench/<name>.md
   ```

   移动到：

   ```text
   docs/archive/strategy-research/<name>.md
   ```

3. 修改文档 meta：
   - `类型：Archive / 策略实验摘要`
   - `状态：已完成 / 通过或未通过`
   - 保留 `开发分支`、`开分支 hash`、`实现提交 hash`。
4. 修正相对链接：
   - archive 到 roadmap：`../../roadmap/...`
   - archive 到 issues：`../../issues/...`
   - issue 到 archive：`../archive/strategy-research/...`
5. 提交归档变更。

## 合并回 dev 流程

1. 确认当前开发分支和目标 dev 分支。
   - 目标 dev 分支必须匹配 `dev/*`；通常选择最高版本的 `dev/*` 分支。
   - 不对 `main` / `master` 直接执行合并或推送。
2. 检查 Git 状态。
   - 运行 `git status --short --branch`。
   - 查看 staged / unstaged diff。
   - 检查未跟踪文件，避免提交 `.env`、凭据、本地数据、缓存、大文件等。
3. 合并前防误判门禁。
   - 在执行 checkout / merge / cherry-pick 前，先向用户展示并确认：当前分支、目标 dev 分支、双方 HEAD、待合入 commit 列表。
   - 不根据当前所在分支、最近使用分支、branch list 顺序或版本号习惯推断目标 dev 分支。
   - 检查 `git log --oneline <target-dev>..<feature-branch>` 和 `git log --oneline <feature-branch>..<target-dev>`。
   - 若待合入列表含明显非本任务提交，不直接 merge；改为让用户确认 cherry-pick 哪些提交。
4. 更新目标 dev 分支。
   - 切换到目标 dev 分支。
   - 按仓库当前策略拉取最新代码。
5. 不自动 rebase 开发分支。
   - 合并阶段不要求、也不主动执行 `git rebase <dev-branch>`。
   - “在哪就是哪”：保留当前分支关系，先观察一段时间。
   - 如果出现分支落后、提交范围混乱或冲突风险，只提示用户并等待确认，不自动改写开发分支历史。
6. 验证合并前状态。
   - 检查 `git status --short --branch`。
   - 根据改动类型运行必要验证；Python 命令必须使用 `uv run`。
7. 合并回目标 dev 分支。
   - 切回目标 dev 分支。
   - 使用 `git merge --no-ff <feature-branch> -m "merge: ..."` 保留任务边界。
   - 合并前后都检查状态。
8. 合并后再次验证核心改动。
9. 不 push，除非用户明确要求。

## Push 流程

当用户明确说 `git push` 或“push”时：

1. 检查状态：
   - `git status --short --branch`
   - `git log --oneline -5`
   - `git branch -vv`
2. 如果当前分支是 `main` / `master`，不要直接 push，先警告并询问。
3. 如果有未提交改动，先询问是否提交，不自动提交。
4. 如果分支无 upstream：
   - 使用 `git push -u origin <branch>`。
5. 如果分支已有 upstream：
   - 使用 `git push`。
6. push 后再次运行 `git status --short --branch` 确认远端同步。

## 安全规则

- 每次开发新功能或修复问题，默认从目标 dev 分支新开独立开发分支，不直接在 dev 上改。
- 不运行破坏性 Git 命令，例如 `reset --hard`、`checkout .`、`restore .`、`clean -f`、`branch -D`，除非用户明确要求。
- 不自动提交或推送；提交/推送必须有用户明确授权。
- 暂存文件时优先指定具体文件，避免 `git add .` 或 `git add -A` 误加入敏感文件。
- 遇到冲突、未提交改动、远端分支落后、目标分支不明确、待合入 commit 范围包含非本任务提交时，先询问用户。
- 合并流程中不要自动 rebase 开发分支；需要改写历史时必须由用户明确要求。
- 文档文件通常不在 pre-commit 域 hook 覆盖范围内；提交时若 hook 提醒 docs 未覆盖，需人工确认链接和内容边界即可，不要为了 docs 强行补测试。

## 源文件创建规则

创建任何新的源文件时，必须在尽可能靠近文件头的位置添加文件级别注释块，作为源代码级别的元信息。

要求：

- 适用范围：`.py`、`.ts`、`.tsx`、`.js`、`.sh`、`.sql` 等源代码/脚本文件；普通研究文档和 README 不适用。
- 位置：放在 shebang、encoding 声明、future import 等语言强制头部内容之后，常规 import / 业务代码之前。
- 内容必须说明：
  - 创建背景：为什么需要新增这个文件；
  - 用途：这个文件在项目中的职责；
  - 关键注意事项：运行口径、依赖假设、实验性质、是否长期保留、不要误用的边界。
- 注释块是文件级元信息，不替代函数/类文档，也不要写成变更日志。
- 内容要简洁，避免过程性流水账；如果文件是临时实验脚本，必须明确临时性和清理/归档边界。

Python 示例：

```python
"""
文件级元信息：
- 创建背景：用于补充 R30 VA 回归分支验证，避免复用 CLI 报告链路造成批量实验过慢。
- 用途：执行轻量回测并输出结构诊断指标。
- 注意事项：仅用于同一 runner 下的相对比较，不直接替代清算口径结果。
"""
```

TypeScript 示例：

```ts
/**
 * 文件级元信息：
 * - 创建背景：为回测报告新增结构诊断展示入口。
 * - 用途：渲染结构诊断指标表格。
 * - 注意事项：只消费已生成的 report JSON，不在前端重新计算交易指标。
 */
```

## 项目约束

- 本项目位于 `quant/`。
- Python 命令必须使用 `uv run`。
- 常用验证命令：
  - `ruff check workspace/ scripts/ main.py`
  - `ruff format --check workspace/ scripts/ main.py`
  - `uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report`
  - `uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short`
- 针对局部 CLI 改动，可用：
  - `ruff check workspace/cli/commands/backtest.py workspace/cli/workflows/backtests_run.py workspace/tests/cli/test_commands_backtest_routing.py`
  - `ruff format --check workspace/cli/commands/backtest.py workspace/cli/workflows/backtests_run.py workspace/tests/cli/test_commands_backtest_routing.py`
  - `uv run pytest workspace/tests/cli/test_commands_backtest_routing.py --tb=short`
  - `uv run mypy workspace/cli`
