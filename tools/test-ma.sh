#!/bin/bash
# ============================================================================
# MA策略全链路测试脚本 - 一键执行
# ============================================================================
# 功能: 测试MA策略全链路是否正常工作
# 步骤: 1. 全量回测 + 贝叶斯搜索  2. 生成报告
#
# 用法: bash test-ma.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
if [[ "${CONDA_PREFIX:-}" == *quant_trading* ]]; then
    PYTHON_PATH="${CONDA_PREFIX}/bin/python"
else
    PYTHON_PATH="/usr/local/Caskroom/miniconda/base/envs/quant_trading/bin/python"
fi

echo "=========================================="
echo "MA 策略全链路测试"
echo "时间: $(date)"
echo "=========================================="

# ── 步骤 1: 全量回测 + 网格搜索 ──
echo ""
echo "[步骤 1/2] 执行全量回测 + 网格搜索..."
if "$PYTHON_PATH" "$ROOT_DIR/main.py" backtest \
    --pattern "\.1m\." \
    --strategy ma \
    --mode search \
    --optimizer bayesian \
    --trials 20 \
    --capital 100000 \
    --contract-size 10; then
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
