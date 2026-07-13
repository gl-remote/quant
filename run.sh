#!/bin/bash
# ============================================================================
# 策略工具箱 - 快捷运行脚本
# ============================================================================
# 使用方式:
#   ./run.sh <command> [options]
#
# 命令列表:
#   export        导出Qlib格式CSV数据
#   test          本地策略逻辑测试（不联网）
#   backtest      统一回测（自动选择引擎）
#   report        从数据库生成回测报告
#   live          实盘/模拟交易
#
# 示例:
#   ./run.sh export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31
#   ./run.sh backtest --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31 --gui
#   ./run.sh backtest --pattern "DCE\.m"
#   ./run.sh report --id 42
# ============================================================================

# 设置 Python 路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

# 检查命令是否有效
VALID_COMMANDS="export test backtest report live"

# 显示帮助信息
show_help() {
    echo "策略工具箱 - 快捷运行脚本"
    echo ""
    echo "使用方式:"
    echo "  ./run.sh <command> [options]"
    echo ""
    echo "命令列表:"
    echo "  export        导出Qlib格式CSV数据"
    echo "  test          本地策略逻辑测试（不联网）"
    echo "  backtest      统一回测（自动选择引擎）"
    echo "  report        从数据库生成回测报告"
    echo "  live          实盘/模拟交易"
    echo ""
    echo "详细帮助:"
    echo "  ./run.sh export --help"
    echo "  ./run.sh test --help"
    echo "  ./run.sh backtest --help"
    echo "  ./run.sh report --help"
    echo "  ./run.sh live --help"
    echo ""
    echo "使用示例:"
    echo "  # 导出数据"
    echo "  ./run.sh export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31"
    echo ""
    echo "  # 单标的回测（TqSdk，支持GUI）"
    echo "  ./run.sh backtest --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31 --gui"
    echo ""
    echo "  # 批量回测（vn.py）"
    echo "  ./run.sh backtest --pattern \"DCE\\.m\""
    echo "  ./run.sh backtest  # 扫描全部品种"
    echo ""
    echo "  # 查看回测报告"
    echo "  ./run.sh report --id 42"
    echo "  ./run.sh report --compare 1,2,3"
}

# 如果没有参数，显示帮助
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

# 检查命令是否有效
COMMAND="$1"
case "$COMMAND" in
    export|test|backtest|report|live)
        ;;
    -h|--help|help)
        show_help
        exit 0
        ;;
    *)
        echo "错误: 未知命令 '$COMMAND'"
        echo "有效命令: $VALID_COMMANDS"
        exit 1
        ;;
esac

# 执行命令
#
# sandbox 环境兼容：沙箱注入的 PYTHONHOME(3.13)/PYTHONPATH 会与
# 项目的 Python 3.12 venv 冲突，导致 import 失败或版本不匹配。
# 这里在执行 uv run 之前先 unset，不影响其他系统命令。
(cd "$SCRIPT_DIR" &&
    unset PYTHONHOME &&
    unset PYTHONPATH &&
    PYTHONPATH="$SCRIPT_DIR/workspace${PYTHONPATH:+:$PYTHONPATH}" uv run python main.py "$@")