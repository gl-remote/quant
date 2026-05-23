#!/bin/bash
# 项目快捷运行脚本
# 使用: ./run.sh <参数>
# 例如: ./run.sh backtest --symbol DCE.m2509

CONDA_BASE="${CONDA_PREFIX:-/usr/local/Caskroom/miniconda/base}"
PYTHON_PATH="${CONDA_BASE}/envs/quant_trading/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

if [ ! -f "$PYTHON_PATH" ]; then
    PYTHON_PATH="python"
fi

"$PYTHON_PATH" "$SCRIPT_DIR/main.py" "$@"