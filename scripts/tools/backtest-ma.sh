#!/bin/bash
# ============================================================================
# MA策略全链路测试脚本 - 一键执行
# ============================================================================
# 功能: 测试MA策略全链路是否正常工作（并行回测）
# 步骤: 1. 全量回测 + 贝叶斯搜索  2. 生成报告
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/../.."

echo "=========================================="
echo "MA 策略全链路测试（并行回测）"
echo "时间: $(date)"
echo "=========================================="

# ── 步骤 1: 全量回测 + 贝叶斯搜索 ──
echo ""
echo "[步骤 1/2] 执行全量回测 + 贝叶斯搜索..."

if (cd "$ROOT_DIR" && uv run python main.py backtest \
    --pattern "DCE\\.m.*" \
    --strategy ma \
    --mode search \
    --optimizer bayesian \
    --parallel \
    --trials 3 \
    --capital 100000 \
    --contract-size 10); then
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