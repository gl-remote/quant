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
#   bash scripts/test.sh                  # 全量: lint + format + type + unit
#   bash scripts/test.sh lint             # 全量仅 ruff lint
#   bash scripts/test.sh type             # 全量仅 mypy
#   bash scripts/test.sh <stage> <domain> # 只验某业务域（增量）
#       例: bash scripts/test.sh lint backtest   只 ruff check backtest/
#           bash scripts/test.sh unit strategies 只 pytest tests/strategies/
#   <stage>  = lint | format | type | unit | all（缺省 all）
#   <domain> = common|config|data|backtest|strategies|report|cli|contracts|report-web
#              （可选，缺省全量 Python；report-web 走前端工具链 eslint/tsc/vitest）
#
# ----------------------------------------------------------------------------
# 【设计 / 给 AI 的提醒】
# ----------------------------------------------------------------------------
# 两层职责（与 directory-roadmap 原则 8 对齐）：
#   - scripts/test.sh = 验证「内容层」：跑什么检查、什么口径、域→路径映射的单一事实来源
#   - .pre-commit-config.yaml = 验证「触发层」：何时跑、对哪些文件跑（git 集成，files 正则）
# pre-commit 已按业务域切分：改 <domain>/ 只触发该域的 lint/format/type/unit，
# 全量回归靠显式 `bash scripts/test.sh` 或 CI 兜底。
#
# 多工具链：report 域含 Python(workspace/report/) + 前端(workspace/report/web/) 两种形态，验证体系不同：
#   - report      → 先 ruff+mypy+pytest（Python），再追加 eslint+tsc+vitest（前端）。
#                   流程决策：改 workspace/report/ 域任何文件都前后端都验一遍（前后端强交互）。
#   - report-web  → 只跑前端工具链（eslint+tsc+vitest），供单独验证前端时使用。
#
# 按域切的依据：测试已按域与源码目录对齐（tests/<domain>/ ↔ <domain>/）。
# 「某域测试覆盖不全」是 tests 自身的完备性问题，与本验证流程正交——按域切恰好
# 能把覆盖不足暴露出来（改 A 域挂了说明 tests/A 不够），不该用全量兜底去掩盖。
#
# ⚠️ AI 注意：将来若有人要改动 scripts/ 下脚本或 .pre-commit-config.yaml 的验证分工
#    （如增量↔全量切换、stages 分 commit/push、域划分调整），必须先把上述「内容层 vs
#    触发层」「按域切 vs 全量兜底」的取舍提醒用户，确认后再动手。精细度有维护代价。
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
cd "$ROOT_DIR"

WEB_DIR="workspace/report/web"

# 全量 mypy 范围（不传 domain 时使用，与历史 pre-commit 保持一致）
MYPY_TARGETS=(common/ data/ backtest/ strategies/)

# 业务域 → 源码路径（lint/format/type 的目标）
resolve_src() {
    case "$1" in
        common|config|data|backtest|strategies|cli) echo "$1/" ;;
        report) echo "workspace/report/" ;;
        contracts) echo "workspace/packages/python-contracts/src/" ;;
        *) echo "" ;;
    esac
}

# 业务域 → 测试路径（unit 的目标）
resolve_test() {
    case "$1" in
        common|config|data|backtest|strategies|report|cli) echo "tests/$1/" ;;
        contracts) echo "workspace/packages/python-contracts/tests/" ;;
        *) echo "" ;;
    esac
}

# 已被某个 pre-commit 域 hook 覆盖的路径前缀（与 .pre-commit-config.yaml 的 files 对应）。
# 落在这些前缀外的改动 = 不会触发任何域 hook 的盲区。
# 维护规则：在 .pre-commit-config.yaml 新增/调整域 hook 时，同步更新此清单。
COVERED_PREFIXES=(
    "common/" "config/" "data/" "backtest/" "strategies/" "cli/" "workspace/report/"
    "tests/"                                  # 测试自身改动由对应域 hook（含 tests/<domain>/）覆盖
    "workspace/packages/python-contracts/"    # contracts 域
)

run_lint() {
    echo "── [lint] ruff check $* ──"
    ruff check "$@"
}

run_format() {
    echo "── [format] ruff format --check $* ──"
    ruff format --check "$@"
}

run_type() {
    echo "── [type] mypy $* ──"
    uv run python -m mypy --config-file pyproject.toml "$@"
}

run_unit() {
    if [ "$#" -eq 0 ]; then
        echo -e "${YELLOW}── [unit] 该域无测试目录，跳过 ──${NC}"
        return 0
    fi
    echo "── [unit] pytest $* ──"
    # 覆盖 pyproject 的 addopts（含 --cov=. 全量覆盖率），按域验证时不需要全量 coverage
    uv run python -m pytest "$@" -o addopts="" -p no:cacheprovider -q --tb=short
}

# ── 前端（report-web）工具链：stage 语义对齐 Python 侧 ──
web_lint()   { echo "── [lint] eslint ──";  (cd "$WEB_DIR" && npm run --silent lint); }
web_type()   { echo "── [type] tsc --noEmit ──"; (cd "$WEB_DIR" && npx --no-install tsc --noEmit); }
web_unit()   { echo "── [unit] vitest run ──"; (cd "$WEB_DIR" && npx --no-install vitest run); }
web_format() { echo -e "${YELLOW}── [format] 前端无独立 prettier 脚本，eslint 已含风格，跳过 ──${NC}"; }

run_web_stage() {
    case "$1" in
        lint)   web_lint ;;
        format) web_format ;;
        type)   web_type ;;
        unit)   web_unit ;;
        all)    web_lint; web_type; web_unit ;;
        *) echo -e "${RED}未知 stage: $1${NC}"; exit 1 ;;
    esac
}

STAGE="${1:-all}"
DOMAIN="${2:-}"

# ── 兜底：检测未被任何域 hook 覆盖的改动文件 ──
# 由 pre-commit 的 always_run hook 调用（pass_filenames: true），$2..$N 为改动文件列表。
# 只提示、不拦截（exit 0）：让 AI 在 commit 输出里看到盲区文件，自行决定是否通知用户。
if [ "$STAGE" = "_uncovered" ]; then
    shift || true
    uncovered=()
    for f in "$@"; do
        covered=0
        for p in "${COVERED_PREFIXES[@]}"; do
            case "$f" in "$p"*) covered=1; break ;; esac
        done
        [ "$covered" -eq 0 ] && uncovered+=("$f")
    done
    if [ "${#uncovered[@]}" -gt 0 ]; then
        echo -e "${YELLOW}⚠ 以下改动文件不在任何 pre-commit 域 hook 覆盖范围内（未被验证）：${NC}"
        for f in "${uncovered[@]}"; do echo "    $f"; done
        echo -e "${YELLOW}  （AI：请判断是否需要提醒用户为这些文件补充测试覆盖或纳入某业务域。）${NC}"
    fi
    exit 0
fi

# 前端域单独分流到前端工具链
if [ "$DOMAIN" = "report-web" ]; then
    run_web_stage "$STAGE"
    echo -e "${GREEN}✓ 验证通过${NC}"
    exit 0
fi

# 解析目标路径：传 domain 则按域，否则全量
if [ -n "$DOMAIN" ]; then
    SRC="$(resolve_src "$DOMAIN")"
    if [ -z "$SRC" ]; then
        echo -e "${RED}未知业务域: $DOMAIN${NC}"
        echo "可选: common|config|data|backtest|strategies|report|cli|contracts"
        exit 1
    fi
    TST="$(resolve_test "$DOMAIN")"
    SRC_PATHS=("$SRC")
    TYPE_PATHS=("$SRC")
    # 测试目录可能尚未建立，不存在则 unit 跳过
    if [ -d "$TST" ]; then
        TEST_PATHS=("$TST")
    else
        TEST_PATHS=()
    fi
else
    SRC_PATHS=(.)
    TYPE_PATHS=("${MYPY_TARGETS[@]}")
    TEST_PATHS=(tests/ workspace/packages/python-contracts/tests/)
fi

case "$STAGE" in
    lint)   run_lint "${SRC_PATHS[@]}" ;;
    format) run_format "${SRC_PATHS[@]}" ;;
    type)   run_type "${TYPE_PATHS[@]}" ;;
    unit)   run_unit "${TEST_PATHS[@]}" ;;
    all)
        run_lint "${SRC_PATHS[@]}"
        run_format "${SRC_PATHS[@]}"
        run_type "${TYPE_PATHS[@]}"
        run_unit "${TEST_PATHS[@]}"
        ;;
    *) echo -e "${RED}未知 stage: $STAGE (可选: lint/format/type/unit/all)${NC}"; exit 1 ;;
esac

# report 域含前后端：Python 跑完后追加前端工具链（流程决策——改 report 前后端都验）
if [ "$DOMAIN" = "report" ]; then
    echo "── report 前端 ──"
    run_web_stage "$STAGE"
fi

echo -e "${GREEN}✓ 验证通过${NC}"
