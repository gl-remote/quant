#!/bin/bash
# 一键拉取近期适配数据 — tqsdk 1m / 5m / 15m
# 用法: ./fetch_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

source activate_env.sh

for interval in 1m 5m 15m; do
    echo ""
    echo ">>> 拉取 ${interval} 数据..."
    python tools/fetch_data.py --source tqsdk --interval "$interval"
done
