#!/bin/bash
# 清理回测/Optuna数据 — 不动 CSV / metadata
# 用法: ./clean_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
DB="$SCRIPT_DIR/.quant_shared_data/quant_shared.db"
OUT_DIR="$SCRIPT_DIR/output"

echo "=========================================="
echo "  清理回测 / Optuna 数据"
echo "  CSV / metadata → 保留"
echo "=========================================="

# ── 1. 数据库 ──
if [ -f "$DB" ]; then
    echo ""
    echo "[1/2] 清理数据库..."

    python3 -c "
import sqlite3, os
db = '$DB'
if not os.path.exists(db):
    exit()
conn = sqlite3.connect(db)
cur = conn.cursor()

tables = {
    'backtests':       '回测记录',
    'backtest_trades': '交易明细',
    'backtest_daily':  '每日资金',
    'operation_logs':  '操作日志',
    'studies':         'Optuna studies',
    'trials':          'Optuna trials',
    'trial_params':    'Optuna trial参数',
    'trial_values':    'Optuna trial值',
    'trial_intermediate_values': 'Optuna 中间值',
    'trial_heartbeats':          'Optuna 心跳',
    'trial_system_attributes':   'Optuna 系统属性',
    'trial_user_attributes':     'Optuna 用户属性',
    'study_directions':          'Optuna 方向',
    'study_system_attributes':   'Optuna 系统属性',
    'study_user_attributes':     'Optuna 用户属性',
    'version_info':              'Optuna 版本',
    'alembic_version':           'Optuna alembic',
}

for tbl, desc in tables.items():
    try:
        cur.execute(f'SELECT count(*) FROM \"{tbl}\"')
        n = cur.fetchone()[0]
        if n > 0:
            cur.execute(f'DELETE FROM \"{tbl}\"')
            print(f'  {desc:<20} 删除 {n} 条')
    except Exception:
        pass

try:
    cur.execute('DELETE FROM sqlite_sequence')
except Exception:
    pass

conn.commit()
conn.close()
print('  数据库已清理')
"
fi

# ── 2. output ──
echo ""
echo "[2/2] 清理 output..."
if [ -d "$OUT_DIR" ]; then
    count=$(find "$OUT_DIR" -type f | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        rm -rf "$OUT_DIR"/*
        echo "  删除 $count 个文件"
    else
        echo "  无文件"
    fi
fi

echo ""
echo "=========================================="
echo "  清理完成 (CSV / metadata 已保留)"
echo "=========================================="
