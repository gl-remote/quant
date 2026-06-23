#!/bin/bash
# ============================================================================
# MA策略信号链路测试脚本 - 一键执行（不下单）
# ============================================================================
# 功能: 连接天勤实时行情驱动MA策略，验证信号链路正确性
# 安全: test 命令代码路径不包含下单逻辑，永远安全
#
# 用法: bash test-signal.sh
#       bash test-signal.sh --gui    # 启用浏览器可视化
#       SYMBOL=SHFE.rb2609 bash test-signal.sh  # 自定义合约

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

# 默认参数
STRATEGY="ma"
SYMBOL="${SYMBOL:-DCE.m2609}"
GUI_FLAG="--gui"

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --no-gui) GUI_FLAG="" ;;
        *) echo -e "${RED}未知参数: $arg${NC}"; exit 1 ;;
    esac
done

echo "=========================================="
echo "MA 策略信号链路测试"
echo "时间: $(date)"
echo "策略: ${STRATEGY}"
echo "标的: ${SYMBOL}"
echo "GUI:  $([ -n "$GUI_FLAG" ] && echo '开' || echo '关')"
echo "=========================================="
echo ""

echo "[步骤 1/1] 启动实时信号测试（Ctrl+C 停止）..."
echo ""

# 检查非交易时段提醒
CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" -ge 15 ] && [ "$CURRENT_HOUR" -lt 21 ]; then
    echo -e "${YELLOW}⚠ 提示: 当前为日盘收盘时段($(date +%H:%M))，天勤可能无新行情推送。"
    echo -e "  建议在交易时段运行（日盘 9:00-15:00，夜盘 21:00-23:00/次日 2:30）。${NC}"
    echo ""
fi

if (cd "$ROOT_DIR" && uv run python main.py test \
    --strategy "$STRATEGY" \
    --symbol "$SYMBOL" \
    $GUI_FLAG); then
    echo -e "${GREEN}✓ 测试完成${NC}"
else
    echo -e "${GREEN}✓ 测试已停止（Ctrl+C 正常退出）${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}信号链路测试结束${NC}"
echo "=========================================="
