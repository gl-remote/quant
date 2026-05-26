#!/bin/bash
# 清理回测/optuna 数据 — 保留 CSV / metadata / db 结构
# 用法:
#   ./clean_data.sh            清理回测 + optuna
#   ./clean_data.sh --csv      同时清理 CSV 文件
#   ./clean_data.sh --all      清理全部含 metadata + CSV

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
DB="$SCRIPT_DIR/.quant_shared_data/quant_shared.db"
CSV_DIR="$SCRIPT_DIR/.quant_shared_data/csv"

CLEAN_CSV=false
CLEAN_ALL=false
for a in "$@"; do
    case "$a" in
        --csv) CLEAN_CSV=true ;;
        --all) CLEAN_CSV=true; CLEAN_ALL=true ;;
    esac
done

echo "=========================================="
echo "  清理回测 / Optuna 数据"
echo "  CSV: $([ "$CLEAN_CSV" = true ] && echo '一并清理' || echo '跳过')"
echo "  metadata: $([ "$CLEAN_ALL" = true ] && echo '一并清理' || echo '保留')"
echo "=========================================="

# ── 1. 清理数据库 ──
if [ -f "$DB" ]; then
    echo ""
    echo "[1/3] 清理数据库..."
    
    CLEAN_ALL=$CLEAN_ALL python3 -c "
import sqlite3, os
db = '$DB'
if not os.path.exists(db):
    print('  无数据库文件')
    exit()

conn = sqlite3.connect(db)
cur = conn.cursor()

tables = {
    'backtests':       '回测记录',
    'backtest_trades': '交易明细',
    'backtest_daily':  '每日资金',
    'operation_logs':  '操作日志',
}
if os.environ.get('CLEAN_ALL') == 'true':
    tables['export_metadata'] = '导出元数据'

tables.update({
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
})

for tbl, desc in tables.items():
    try:
        cur.execute(f'SELECT count(*) FROM \"{tbl}\"')
        n = cur.fetchone()[0]
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
print('  数据库已清理 (保留表结构)')
"
fi

# ── 2. 清理 CSV ──
if [ "$CLEAN_CSV" = true ] && [ -d "$CSV_DIR" ]; then
    echo ""
    echo "[2/3] 清理 CSV 文件..."
    count=$(find "$CSV_DIR" -name '*.csv' | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        rm -f "$CSV_DIR"/*.csv
        echo "  删除 $count 个 CSV 文件"
    else
        echo "  无 CSV 文件"
    fi
fi

# ── 3. 清理 output ──
echo ""
echo "[3/3] 清理 output..."
if [ -d "$SCRIPT_DIR/output" ]; then
    count=$(ls "$SCRIPT_DIR/output"/*.html 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        rm -f "$SCRIPT_DIR/output"/*.html
        echo "  删除 $count 个 HTML 报告"
    else
        echo "  无 HTML 报告"
    fi
fi

echo ""
echo "=========================================="
echo "  清理完成"
echo "=========================================="
