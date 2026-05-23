#!/bin/bash
# 项目快捷运行脚本
# 使用: ./run.sh <参数>
# 例如: ./run.sh --mode test

PYTHON_PATH="/usr/local/Caskroom/miniconda/base/envs/quant_trading/bin/python"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)/main.py"

"$PYTHON_PATH" "$SCRIPT_PATH" "$@"
