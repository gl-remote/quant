#!/bin/bash
# ============================================================================
# 统一验证脚本（单一事实来源）
# ============================================================================
# 目的: 把散落在 pre-commit / project_rules / roadmap 里的验证命令固化成
#       一条可执行契约，避免每次人/AI/CI 各拼一套导致验证范围漂移。
#
# 与 .pre-commit-config.yaml 对齐（同范围、同工具），区别仅在:
#   - 本脚本用 `ruff check`（不自动 --fix），纯检测、不改文件，适合验证;
#   - format 用 `--check`，只报告不重写。
#
# 用法:
#   bash scripts/test.sh            # 全量: lint + format + typecheck + pytest
#   bash scripts/test.sh lint       # 仅 ruff lint
#   bash scripts/test.sh format     # 仅 ruff format 检查
#   bash scripts/test.sh type       # 仅 mypy
#   bash scripts/test.sh unit       # 仅 pytest
#
# ----------------------------------------------------------------------------
# 【演进规划 / 给 AI 的提醒】
# ----------------------------------------------------------------------------
# 当前定位（已确认，暂不改）：
#   - scripts/test.sh = 全量验证基准（低频、显式调用，慢无所谓）
#   - .pre-commit-config.yaml = commit 时的闸（现状 mypy/pytest 仍是 always_run 全量）
#
# 未来可选的「精细化」方向（pre-commit + scripts/ 组合能做到，但现在没必要做，
# 只有当「全量太慢」成为真实痛点时才值得拧这些旋钮）：
#   1. pre-commit 的 `files`/`exclude` 正则 —— 按路径精确划定 hook 触发范围
#   2. pre-commit 的 `pass_filenames: true` —— 把改动文件作为 $@ 传给脚本，实现「改哪验哪」
#   3. pre-commit 的 `stages: [pre-push]` —— 快的(ruff)走 commit，慢的(mypy/pytest)走 push
#   4. pre-commit 的 `entry: bash scripts/check.sh` —— pre-commit 算文件范围，scripts/ 管验证口径
#   分层示意：pre-commit(增量,秒级) → pre-push(相关目录) → CI/手动(全量四件套 + e2e 真实回测)
#
# ⚠️ AI 注意：将来若有人要改动 scripts/ 下脚本或 .pre-commit-config.yaml 的验证分工，
#    必须先把上面这个「全量基准 vs 增量闸」的定位和精细化方向提醒用户，确认后再动手。
#    精细度有维护代价（配置变复杂、新人/AI 要理解为什么某 hook 只在 push 跑），精细 ≠ 更好。
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
cd "$ROOT_DIR"

# mypy 范围与 pre-commit 保持一致
MYPY_TARGETS=(common/ data/ backtest/ strategies/)

run_lint() {
    echo "── [lint] ruff check ──"
    ruff check .
}

run_format() {
    echo "── [format] ruff format --check ──"
    ruff format --check .
}

run_type() {
    echo "── [type] mypy ──"
    uv run python -m mypy --config-file pyproject.toml "${MYPY_TARGETS[@]}"
}

run_unit() {
    echo "── [unit] pytest ──"
    uv run python -m pytest tests/ workspace/packages/python-contracts/tests/ -q --tb=short
}

STAGE="${1:-all}"
case "$STAGE" in
    lint)   run_lint ;;
    format) run_format ;;
    type)   run_type ;;
    unit)   run_unit ;;
    all)    run_lint; run_format; run_type; run_unit ;;
    *) echo -e "${RED}未知参数: $STAGE (可选: lint/format/type/unit/all)${NC}"; exit 1 ;;
esac

echo -e "${GREEN}✓ 验证通过${NC}"
