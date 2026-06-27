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
   - 目标 dev 分支通常是类似 `dev/0.5`、`0.4.2` 这种版本开发分支。
   - 不在 `main` / `master` 上直接开发。
2. 从目标 dev 分支新建独立开发分支。
   - 分支名前缀按任务类型选择：`feature/`、`fix/`、`experiment/`。
   - 如果任务有关联 roadmap 文档，优先让分支名和 roadmap 文件名或任务名对应。
3. 记录开分支 hash。
   - `开分支 hash` 是创建开发分支时目标 dev 分支的 `HEAD`。
   - 这个 hash 在开分支时即可记录，不等到提交后再补。
4. 文档元数据写入边界：
   - roadmap 默认只维护阶段目标、评价标准和候选方向。
   - 具体实验方向、开发分支、开分支 hash、参数对照和中间结果写入 `docs/workbench/`。
   - 不要把实验过程和开发分支信息直接写入 roadmap，除非用户明确要求 roadmap 记录流程约束。
5. 如果没有关联 roadmap / workbench 文档，不主动创建文档；只在最终回复中说明开发分支和相关 hash。
6. 开发完成并提交后，回填 `实现提交 hash`。
   - `实现提交 hash` 是开发分支上完成该任务的提交 hash。
   - 如果一个任务包含多个实现提交，可记录最终提交 hash；必要时记录 commit range，例如 `abc1234..def5678`。
7. 不把 `合并提交 hash` 作为必填 meta。
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
   - 目标 dev 分支通常是类似 `dev/0.5`、`0.4.2` 这种版本开发分支。
   - 不对 `main` / `master` 直接执行合并或推送。
2. 检查 Git 状态。
   - 运行 `git status --short --branch`。
   - 查看 staged / unstaged diff。
   - 检查未跟踪文件，避免提交 `.env`、凭据、本地数据、缓存、大文件等。
3. 拉取最新目标 dev 分支。
   - 切换到目标 dev 分支。
   - `git pull --rebase` 或按仓库当前策略拉取最新代码。
4. 将当前开发分支 rebase 到最新 dev 分支。
   - 切回开发分支。
   - 执行 `git rebase <dev-branch>`。
   - 如有冲突，停止并让用户确认冲突解决方式；不要强行覆盖用户改动。
5. 验证 rebase 后状态。
   - 检查 `git status --short --branch`。
   - 根据改动类型运行必要验证；Python 命令必须使用 `uv run`。
6. 合并回目标 dev 分支。
   - 切回目标 dev 分支。
   - 使用 `git merge --no-ff <feature-branch> -m "merge: ..."` 保留任务边界。
   - 合并前后都检查状态。
7. 合并后再次验证核心改动。
8. 不 push，除非用户明确要求。

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
- 遇到冲突、未提交改动、远端分支落后、目标分支不明确时，先询问用户。
- 文档文件通常不在 pre-commit 域 hook 覆盖范围内；提交时若 hook 提醒 docs 未覆盖，需人工确认链接和内容边界即可，不要为了 docs 强行补测试。

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
