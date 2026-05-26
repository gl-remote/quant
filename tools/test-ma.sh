#!/bin/bash
# ============================================================================
# MA策略全链路测试脚本 - 一键执行
# ============================================================================
# 功能: 测试MA策略全链路是否正常工作
# 步骤: 1. 全量回测 + 网格搜索  2. 生成报告
#
# 用法: bash test-ma.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
PYTHON_PATH="${CONDA_PREFIX:-/usr/local/Caskroom/miniconda/base}/envs/quant_trading/bin/python"

echo "=========================================="
echo "MA 策略全链路测试"
echo "时间: $(date)"
echo "=========================================="

# ── 步骤 1: 全量回测 + 网格搜索 ──
echo ""
echo "[步骤 1/2] 执行全量回测 + 网格搜索..."
if "$PYTHON_PATH" "$ROOT_DIR/main.py" backtest \
    --pattern "DCE.*" \
    --strategy ma \
    --mode search \
    --optimizer grid \
    --trials 20 \
    --capital 100000 \
    --contract-size 10; then
    echo -e "${GREEN}✓ 回测执行成功${NC}"
else
    echo -e "${RED}✗ 回测执行失败 (exit=$?)${NC}"
    exit 1
fi

# ── 获取最新回测 ID ──
LATEST_ID=$(sqlite3 "$ROOT_DIR/.quant_shared_data/quant_shared.db" \
    "SELECT id FROM backtests ORDER BY created_at DESC LIMIT 1;")
if [ -z "$LATEST_ID" ] || ! [[ "$LATEST_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}✗ 未找到有效的回测记录 (LATEST_ID='$LATEST_ID')${NC}"
    exit 1
fi

# ── 步骤 2: 生成报告 ──
echo ""
echo "[步骤 2/2] 生成回测报告 (id=$LATEST_ID)..."
if "$PYTHON_PATH" "$ROOT_DIR/main.py" report --id "$LATEST_ID"; then
    echo -e "${GREEN}✓ 报告生成成功${NC}"
else
    echo -e "${RED}✗ 报告生成失败 (exit=$?)${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}测试完成!${NC}"
echo "回测 ID: $LATEST_ID"
echo "=========================================="