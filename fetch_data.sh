#!/bin/bash
# 一键拉取近期适配数据 — tqsdk 分钟线
# 用法: ./fetch_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

# 激活 conda 环境
source activate_env.sh

echo ""
echo "开始拉取数据..."
python tools/fetch_data.py "$@"
