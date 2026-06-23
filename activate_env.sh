#!/bin/bash
# 策略工具箱：加载本地密钥并显示 uv 工作流提示
# 使用方法: source activate_env.sh

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "错误：请用 source 执行本脚本，而非直接运行"
    echo "  source activate_env.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

# 加载本地密钥（不提交 Git）
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "已加载 .env"
fi

# 检查 uv 与 .venv
if ! command -v uv >/dev/null 2>&1; then
    echo "错误: 未找到 uv，请先安装: https://docs.astral.sh/uv/"
    return 1 2>/dev/null || exit 1
fi

if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "提示: 尚未创建 .venv，请先执行: uv sync --all-groups"
fi

echo ""
echo "本仓库通过 uv 管理 Python 环境，所有 Python 命令请用 uv run 前缀。"
echo "示例:"
echo "  uv run python main.py test"
echo "  uv run python main.py backtest --symbol DCE.m2509"
echo "  uv run pytest workspace/tests/ --tb=short"
echo "  ruff check workspace/strategies/ workspace/tests/"
