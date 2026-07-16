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
#   bash scripts/test.sh                  # 全量: lint + format + type + unit + coverage fail-under
#   bash scripts/test.sh lint             # 全量仅 ruff lint
#   bash scripts/test.sh type             # 全量仅 mypy
#   bash scripts/test.sh coverage         # 全量 coverage（按业务域 fail-under，不设置全仓库总阈值）
#   bash scripts/test.sh integration      # 全量 integration 测试
#   bash scripts/test.sh <stage> <domain> # 只验某业务域（增量）
#       例: bash scripts/test.sh lint backtest   只 ruff check backtest/
#           bash scripts/test.sh unit strategies 只 pytest tests/strategies/
#   <stage>  = lint | format | type | unit | integration | slow | local-data | coverage | all（缺省 all）
#   <domain> = common|config|data|backtest|clearing|strategies|report|cli|contracts|research|report-web
#              （可选，缺省全量 Python；report-web 走前端工具链 eslint/tsc/vitest）
#
# ----------------------------------------------------------------------------
# 【设计 / 给 AI 的提醒】
# ----------------------------------------------------------------------------
# 两层职责（与 directory-roadmap 原则 8 对齐）：
#   - scripts/test.sh = 验证「内容层」：跑什么检查、什么口径、域→路径映射的单一事实来源
#   - .pre-commit-config.yaml = 验证「触发层」：何时跑、对哪些文件跑（git 集成，files 正则）
# pre-commit 已按业务域切分：改 <domain>/ 只触发该域的 lint/format/type/unit，
# 全量回归靠显式 `bash scripts/test.sh` 或 CI 兜底。自阶段 F 起，`all <domain>`
# 也会运行该业务域 coverage fail-under，commit 会按业务域覆盖率阻塞，但不设置
# 全仓库整体 coverage 阈值。
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
source "$SCRIPT_DIR/test/env.sh"
source "$SCRIPT_DIR/test/domains.sh"
source "$SCRIPT_DIR/test/python.sh"
source "$SCRIPT_DIR/test/web.sh"
source "$SCRIPT_DIR/test/precommit.sh"

STAGE="${1:-all}"
DOMAIN="${2:-}"

# ── 兜底：检测未被任何域 hook 覆盖的改动文件 ──
# 由 pre-commit 的 always_run hook 调用（pass_filenames: true），$2..$N 为改动文件列表。
# 只提示、不拦截（exit 0）：让 AI 在 commit 输出里看到盲区文件，自行决定是否通知用户。
if [ "$STAGE" = "_uncovered" ]; then
    shift || true
    run_uncovered_notice "$@"
    exit 0
fi

# 前端域单独分流到前端工具链
if [ "$DOMAIN" = "report-web" ]; then
    if [ "$STAGE" = "coverage" ]; then
        echo -e "${YELLOW}── [coverage] report-web 暂无独立 coverage 入口，跳过 ──${NC}"
        echo -e "${GREEN}✓ 验证通过${NC}"
        exit 0
    fi
    if [ "$STAGE" = "integration" ] || [ "$STAGE" = "slow" ] || [ "$STAGE" = "local-data" ]; then
        echo -e "${YELLOW}── [$STAGE] report-web 暂无对应分层测试入口，跳过 ──${NC}"
        echo -e "${GREEN}✓ 验证通过${NC}"
        exit 0
    fi
    run_web_stage "$STAGE"
    echo -e "${GREEN}✓ 验证通过${NC}"
    exit 0
fi

# 解析目标路径：传 domain 则按域，否则全量
if [ -n "$DOMAIN" ]; then
    SRC="$(resolve_src "$DOMAIN")"
    if [ -z "$SRC" ]; then
        echo -e "${RED}未知业务域: $DOMAIN${NC}"
        echo "可选: common|config|data|backtest|clearing|strategies|report|cli|contracts|research"
        exit 1
    fi
    TST="$(resolve_test "$DOMAIN")"
    COVERAGE_MIN="$(resolve_coverage_min "$DOMAIN")"
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
    TEST_PATHS=(workspace/tests/ workspace/packages/python-contracts/tests/)
fi

case "$STAGE" in
    lint)   run_lint "${SRC_PATHS[@]}" ;;
    format) run_format "${SRC_PATHS[@]}" ;;
    type)   run_type "${TYPE_PATHS[@]}" ;;
    coverage)
        if [ -z "$DOMAIN" ]; then
            run_coverage workspace/common "$(resolve_coverage_min common)" workspace/tests/common/
            run_coverage workspace/config "$(resolve_coverage_min config)" workspace/tests/config/
            run_coverage workspace/data "$(resolve_coverage_min data)" workspace/tests/data/
            run_coverage workspace/backtest "$(resolve_coverage_min backtest)" workspace/tests/backtest/
            run_coverage workspace/clearing "$(resolve_coverage_min clearing)" workspace/tests/clearing/
            run_coverage workspace/strategies "$(resolve_coverage_min strategies)" workspace/tests/strategies/
            run_coverage workspace/report "$(resolve_coverage_min report)" workspace/tests/report/
            run_coverage workspace/cli "$(resolve_coverage_min cli)" workspace/tests/cli/
            run_coverage workspace/research "$(resolve_coverage_min research)" workspace/tests/research/
            run_coverage src "$(resolve_coverage_min contracts)" workspace/packages/python-contracts/tests/
        else
            run_coverage "$SRC" "$COVERAGE_MIN" "${TEST_PATHS[@]}"
        fi
        ;;
    integration)
        if [ -z "$DOMAIN" ]; then
            run_integration workspace/tests/
            run_integration workspace/packages/python-contracts/tests/
        else
            run_integration "${TEST_PATHS[@]}"
        fi
        ;;
    slow)
        if [ -z "$DOMAIN" ]; then
            run_slow workspace/tests/
            run_slow workspace/packages/python-contracts/tests/
        else
            run_slow "${TEST_PATHS[@]}"
        fi
        ;;
    local-data)
        if [ -z "$DOMAIN" ]; then
            run_local_data workspace/tests/
            run_local_data workspace/packages/python-contracts/tests/
        else
            run_local_data "${TEST_PATHS[@]}"
        fi
        ;;
    unit)
        if [ -z "$DOMAIN" ]; then
            run_unit workspace/tests/
            run_unit workspace/packages/python-contracts/tests/
        else
            run_unit "${TEST_PATHS[@]}"
        fi
        ;;
    all)
        run_lint "${SRC_PATHS[@]}"
        run_format "${SRC_PATHS[@]}"
        run_type "${TYPE_PATHS[@]}"
        if [ -z "$DOMAIN" ]; then
            run_unit workspace/tests/
            run_unit workspace/packages/python-contracts/tests/
            run_coverage workspace/common "$(resolve_coverage_min common)" workspace/tests/common/
            run_coverage workspace/config "$(resolve_coverage_min config)" workspace/tests/config/
            run_coverage workspace/data "$(resolve_coverage_min data)" workspace/tests/data/
            run_coverage workspace/backtest "$(resolve_coverage_min backtest)" workspace/tests/backtest/
            run_coverage workspace/clearing "$(resolve_coverage_min clearing)" workspace/tests/clearing/
            run_coverage workspace/strategies "$(resolve_coverage_min strategies)" workspace/tests/strategies/
            run_coverage workspace/report "$(resolve_coverage_min report)" workspace/tests/report/
            run_coverage workspace/cli "$(resolve_coverage_min cli)" workspace/tests/cli/
            run_coverage workspace/research "$(resolve_coverage_min research)" workspace/tests/research/
            run_coverage src "$(resolve_coverage_min contracts)" workspace/packages/python-contracts/tests/
        else
            run_unit "${TEST_PATHS[@]}"
            run_coverage "$SRC" "$COVERAGE_MIN" "${TEST_PATHS[@]}"
        fi
        ;;
    *) echo -e "${RED}未知 stage: $STAGE (可选: lint/format/type/unit/integration/slow/local-data/coverage/all)${NC}"; exit 1 ;;
esac

# report 域含前后端：Python 跑完后追加前端工具链（流程决策——改 report 前后端都验）
# coverage 和分层测试属于 Python 专用入口，report web 后续独立治理，不复用前端验证 stage。
if [ "$DOMAIN" = "report" ] && [ "$STAGE" != "coverage" ] && [ "$STAGE" != "integration" ] && [ "$STAGE" != "slow" ] && [ "$STAGE" != "local-data" ]; then
    echo "── report 前端 ──"
    run_web_stage "$STAGE"
fi

echo -e "${GREEN}✓ 验证通过${NC}"
