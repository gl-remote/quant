#!/bin/bash
# ============================================================================
# VA 非对称复合策略启动脚本
# ============================================================================
# 用途:
#   默认 — 全量 145 合约 5m K线 × 默认参数的并行单次回测
#          （用于「工程侧 vs 研究侧收益 gap 对比」基线）
#   可选 — 通过 MODE=search 切换到全量贝叶斯参数搜索
#
# 环境变量覆盖（优先级最高）:
#   PATTERN     合约文件名正则（默认全量 5m CSV: "\.tqsdk\.5m\."）
#   MODE        single=单次回测(默认) | search=贝叶斯参数搜索
#   WORKERS     并行进程数（默认: 本机 CPU 核数）
#   CAPITAL     初始资金（默认: 1,000,000，与研究侧对齐）
#   TRIALS      search 模式下: 最大试验次数（默认: 30）
#   EARLY_STOP_PATIENCE  search 模式下: 连续 N 次无改善早停（默认: 5）
#
# 命令行额外开关:
#   --no-report     跳过报告重建
#   --no-parallel   强制串行（仅 single 模式 debug 用）
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/../.."

# ── 参数与默认值 ────────────────────────────────────────
PATTERN="${PATTERN:-\.tqsdk\.5m\.}"
MODE="${MODE:-single}"

NCPU="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 8)"
WORKERS="${WORKERS:-$NCPU}"
CAPITAL="${CAPITAL:-1000000}"

TRIALS="${TRIALS:-30}"
EARLY_STOP_PATIENCE="${EARLY_STOP_PATIENCE:-5}"

BUILD_REPORT=1
FORCE_SERIAL=0

# ── 解析命令行开关 ────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --no-report)   BUILD_REPORT=0 ;;
        --no-parallel) FORCE_SERIAL=1 ;;
        *) echo -e "${RED}未知参数: $arg${NC}";
           echo "可用: --no-report, --no-parallel (仅 single)"; exit 1 ;;
    esac
done

if [ "$MODE" = "single" ] && [ "$FORCE_SERIAL" -eq 1 ]; then
    PARALLEL_ARGS=""
    MODE_DESC="单次回测(串行)"
else
    PARALLEL_ARGS="--parallel --workers $WORKERS"
    if [ "$MODE" = "single" ]; then
        MODE_DESC="单次回测(并行 workers=${WORKERS})"
    else
        MODE_DESC="参数搜索(并行 workers=${WORKERS})"
    fi
fi

echo "=========================================="
echo "VA 非对称复合策略"
echo "时间:   $(date)"
echo "模式:   ${MODE_DESC}"
echo "合约:   ${PATTERN}"
echo "资金:   ${CAPITAL}"
echo "环境:   backtest (5m bar)"
if [ "$MODE" = "search" ]; then
echo "试验数: ${TRIALS}  早停: ${EARLY_STOP_PATIENCE}"
fi
echo "报告:   $([ "$BUILD_REPORT" -eq 1 ] && echo '重建' || echo '跳过')"
echo "=========================================="

# ── 步骤 1: 启动 vnpy 回测 ──────────────────────────
echo ""
echo "[步骤 1/2] 执行回测..."

if [ "$MODE" = "search" ]; then
    BACKTEST_ARGS=(
        --pattern "$PATTERN"
        --strategy va_asymmetry_composite
        --mode search
        --optimizer bayesian
        --parallel
        --workers "$WORKERS"
        --trials "$TRIALS"
        --early-stop-patience "$EARLY_STOP_PATIENCE"
        --capital "$CAPITAL"
        --env backtest
    )
else
    BACKTEST_ARGS=(
        --pattern "$PATTERN"
        --strategy va_asymmetry_composite
        --mode single
        --env backtest
        --capital "$CAPITAL"
        $PARALLEL_ARGS
    )
fi

if "$ROOT_DIR/run.sh" backtest "${BACKTEST_ARGS[@]}"; then
    echo -e "${GREEN}✓ 回测执行成功${NC}"
else
    echo -e "${RED}✗ 回测执行失败 (exit=$?)${NC}"
    exit 1
fi

# ── 步骤 2: 重建可视化报告 ────────────────────────────
if [ "$BUILD_REPORT" -eq 1 ]; then
    echo ""
    echo "[步骤 2/2] 重建可视化报告..."
    if "$ROOT_DIR/run.sh" report --build; then
        echo -e "${GREEN}✓ 报告重建成功${NC}"
    else
        echo -e "${RED}✗ 报告重建失败 (exit=$?)${NC}"
        exit 1
    fi
else
    echo ""
    echo -e "${YELLOW}[步骤 2/2] 已跳过报告重建（--no-report）${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}VA 回测完成!${NC}"
if [ "$BUILD_REPORT" -eq 1 ]; then
echo "报告: ${ROOT_DIR}/project_data/reports/index.html"
fi
echo "=========================================="
