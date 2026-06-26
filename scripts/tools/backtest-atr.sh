#!/bin/bash
# ============================================================================
# ATR策略全链路测试脚本 - 一键执行
# ============================================================================
# 功能: 测试ATR策略全链路是否正常工作（并行回测）
# 步骤: 1. 全量回测 + 贝叶斯搜索  2. 生成报告
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/../.."

# 合约筛选正则（可用环境变量覆盖，其余参数有意写死）
PATTERN="${PATTERN:-DCE\\.m.*}"
TRIALS="${TRIALS:-100}"
EARLY_STOP_PATIENCE="${EARLY_STOP_PATIENCE:-5}"

echo "=========================================="
echo "ATR 策略全链路测试（并行回测）"
echo "时间:   $(date)"
echo "合约:   ${PATTERN}"
echo "试验数: ${TRIALS}"
echo "早停:   ${EARLY_STOP_PATIENCE} (0=关闭)"
echo "=========================================="

# ── 步骤 1: 全量回测 + 贝叶斯搜索 ──
echo ""
echo "[步骤 1/2] 执行全量回测 + 贝叶斯搜索..."

if "$ROOT_DIR/run.sh" backtest \
    --pattern "$PATTERN" \
    --strategy atr \
    --mode search \
    --optimizer bayesian \
    --parallel \
    --trials "$TRIALS" \
    --early-stop-patience "$EARLY_STOP_PATIENCE" \
    --capital 100000 \
    --contract-size 10 "$@"; then
    echo -e "${GREEN}✓ 回测执行成功${NC}"
else
    echo -e "${RED}✗ 回测执行失败 (exit=$?)${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}测试完成!${NC}"
echo "报告: output/index.html"
echo "=========================================="
