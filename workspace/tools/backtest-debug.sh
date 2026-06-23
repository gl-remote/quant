#!/bin/bash
# ============================================================================
# 单次回测 DEBUG 脚本 - 一键执行
# ============================================================================
# 用途: 仅供 DEBUG / 排查问题，不做参数搜索，只跑一次回测。
#       与 backtest-ma.sh（全量并行 + 贝叶斯搜索）互补：那个跑性能/择优，
#       这个跑「单合约、单组默认参数、可观测」的调试链路。
#
# 本脚本相比生产回测额外开启的 DEBUG 能力：
#   1. --no-search        关闭参数搜索（覆盖配置 optimizer.enabled），
#                         用策略默认参数只跑一次，结果可复现、便于断点调试。
#   2. --dump-indicators  把各周期指标列回写到基础周期 DataFrame，
#                         随回测结果落地，便于离线核对指标计算是否正确
#                         （运行时默认不回写，有性能开销，仅 debug 时开）。
#   3. --profile (可选)   用 cProfile 采样写出 .prof 文件，供 snakeviz 查看热点。
#   4. report --build     回测后重建可视化 HTML 报告（K 线 + 指标叠加图 + 资金曲线），
#                         打开 output/index.html 即可肉眼检查信号/指标。
#
# 用法:
#   bash backtest-debug.sh                       # 默认合约 + 默认策略
#   SYMBOL=DCE.c2601 bash backtest-debug.sh      # 指定合约
#   STRATEGY=ma SYMBOL=DCE.m2609 bash backtest-debug.sh
#   bash backtest-debug.sh --profile             # 额外开启性能分析
#   bash backtest-debug.sh --no-report           # 跳过报告重建（只跑回测）
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."

# 默认参数（可用环境变量覆盖）
STRATEGY="${STRATEGY:-ma}"
SYMBOL="${SYMBOL:-DCE.m2609}"

# 开关
PROFILE_FLAG=""
BUILD_REPORT=1

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --profile)   PROFILE_FLAG="--profile" ;;
        --no-report) BUILD_REPORT=0 ;;
        *) echo -e "${RED}未知参数: $arg${NC}"; exit 1 ;;
    esac
done

echo "=========================================="
echo "单次回测 DEBUG"
echo "时间:   $(date)"
echo "策略:   ${STRATEGY}"
echo "合约:   ${SYMBOL}"
echo "性能分析: $([ -n "$PROFILE_FLAG" ] && echo '开' || echo '关')"
echo "重建报告: $([ "$BUILD_REPORT" -eq 1 ] && echo '开' || echo '关')"
echo "=========================================="

# ── 步骤 1: 单次回测（关搜索 + 落地指标） ──
echo ""
echo "[步骤 1/2] 单次回测（--no-search --dump-indicators ${PROFILE_FLAG})..."

if (cd "$ROOT_DIR" && uv run python main.py backtest \
    --engine vnpy \
    --strategy "$STRATEGY" \
    --symbol "$SYMBOL" \
    --no-search \
    --dump-indicators \
    $PROFILE_FLAG); then
    echo -e "${GREEN}✓ 回测执行成功${NC}"
else
    echo -e "${RED}✗ 回测执行失败 (exit=$?)${NC}"
    exit 1
fi

if [ -n "$PROFILE_FLAG" ]; then
    echo -e "${YELLOW}提示: 性能分析结果见 output/profiles/*.prof，查看: snakeviz <文件>${NC}"
fi

# ── 步骤 2: 重建可视化报告 ──
if [ "$BUILD_REPORT" -eq 1 ]; then
    echo ""
    echo "[步骤 2/2] 重建可视化报告..."
    if (cd "$ROOT_DIR" && uv run python main.py report --build); then
        echo -e "${GREEN}✓ 报告重建成功${NC}"
    else
        echo -e "${RED}✗ 报告重建失败 (exit=$?)${NC}"
        exit 1
    fi
else
    echo ""
    echo "[步骤 2/2] 已跳过报告重建（--no-report）"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}DEBUG 回测完成!${NC}"
echo "报告: output/index.html"
echo "=========================================="
