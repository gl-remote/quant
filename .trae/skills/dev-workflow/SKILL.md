---
name: "dev-workflow"
description: "Runs the quant dev branch workflow. Invoke when starting new work, merging back to dev, or updating roadmap-linked branch metadata."
---

# Dev Workflow

用于本 quant 项目的固定开发、提交和合并流程。

## 触发条件

当用户说类似以下内容时启用：

- “开始做这个功能”
- “新开一个开发任务”
- “这个 roadmap 开始实现”
- “可以合并了”
- “合并到 dev”
- “走开发流程”
- “按固定流程提交/合并”

## 新开发任务流程

1. 确认目标 dev 分支和任务范围。
   - 目标 dev 分支通常是类似 `0.4.2` 这种版本开发分支。
   - 不在 `main` / `master` 上直接开发。
2. 从目标 dev 分支新建独立开发分支。
   - 分支名前缀按任务类型选择：`feature/`、`fix/`、`experiment/`。
   - 如果任务有关联 roadmap 文档，优先让分支名和 roadmap 文件名或任务名对应。
3. 记录开分支 hash。
   - `开分支 hash` 是创建开发分支时目标 dev 分支的 `HEAD`。
   - 这个 hash 在开分支时即可记录，不等到提交后再补。
4. 如果任务有关联 roadmap 文档，在文档顶部 meta 中维护：

   ```markdown
   > 开发分支：feature/example-task
   > 开分支 hash：xxxxxxx
   > 实现提交 hash：待提交
   ```

5. 如果没有关联 roadmap 文档，不主动创建文档；只在最终回复中说明开发分支和相关 hash。
6. 开发完成并提交后，回填 `实现提交 hash`。
   - `实现提交 hash` 是开发分支上完成该任务的提交 hash。
   - 如果一个任务包含多个实现提交，可记录最终提交 hash；必要时记录 commit range，例如 `abc1234..def5678`。
7. 不把 `合并提交 hash` 作为必填 meta。
   - 合并提交 hash 只有合回 dev 后才可能明确，且可能因为 merge、squash、fast-forward 策略不同而不存在或语义不同。
   - 如用户明确要求，可在合并后再补充。

## 合并回 dev 流程

1. 确认当前开发分支和目标 dev 分支。
   - 目标 dev 分支通常是类似 `0.4.2` 这种版本开发分支。
   - 不对 `main` / `master` 直接执行合并或推送。
2. 检查 Git 状态。
   - 运行 `git status`。
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
   - 检查 `git status`。
   - 根据改动类型运行必要验证；Python 命令必须使用 `uv run`。
6. 合并回目标 dev 分支。
   - 合并前确认关联 roadmap 文档已记录 `开发分支`、`开分支 hash`，并在提交完成后回填 `实现提交 hash`。
   - 切回目标 dev 分支。
   - 合并开发分支。
   - 合并前后都检查状态。
7. 提交与推送。
   - 只有在用户明确要求提交时才 `git commit`。
   - 只有在用户明确要求推送时才 `git push`。
   - 禁止 `force push`，除非用户明确要求，且不能 force push 到 `main` / `master`。

## 安全规则

- 每次开发新功能或修复问题，默认从目标 dev 分支新开独立开发分支，不直接在 dev 上改。
- 不运行破坏性 Git 命令，例如 `reset --hard`、`checkout .`、`restore .`、`clean -f`、`branch -D`，除非用户明确要求。
- 不自动提交或推送；提交/推送必须有用户明确授权。
- 暂存文件时优先指定具体文件，避免 `git add .` 或 `git add -A` 误加入敏感文件。
- 遇到冲突、未提交改动、远端分支落后、目标分支不明确时，先询问用户。

## 项目约束

- 本项目位于 `quant/`。
- Python 命令必须使用 `uv run`。
- 常用验证命令：
  - `ruff check workspace/ scripts/ main.py`
  - `uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report`
  - `uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short`
