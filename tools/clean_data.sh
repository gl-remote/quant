#!/bin/bash
# 清理回测/Optuna数据 — 不动 CSV / metadata
# 用法: ./clean_data.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
DB="$ROOT_DIR/.quant_shared_data/quant_shared.db"
OUT_DIR="$ROOT_DIR/output"

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

# 固定业务表（不动 export_metadata）
biz_tables = ['runs', 'run_studies', 'backtests', 'backtest_params', 'backtest_trades', 'backtest_daily', 'operation_logs']
for tbl in biz_tables:
    try:
        cur.execute(f'SELECT count(*) FROM \"{tbl}\"')
        n = cur.fetchone()[0]
        if n > 0:
            cur.execute(f'DELETE FROM \"{tbl}\"')
            print(f'  {tbl:<24} 删除 {n} 条')
    except Exception:
        pass

# Optuna 相关表
optuna_tables = [
    'studies', 'study_directions', 'study_system_attributes', 'study_user_attributes',
    'trials', 'trial_heartbeats', 'trial_intermediate_values', 'trial_params',
    'trial_system_attributes', 'trial_user_attributes', 'trial_values',
    'version_info', 'alembic_version',
]
for tbl in optuna_tables:
    try:
        cur.execute(f'SELECT count(*) FROM \"{tbl}\"')
        n = cur.fetchone()[0]
        if n > 0:
            cur.execute(f'DELETE FROM \"{tbl}\"')
            print(f'  {tbl:<24} 删除 {n} 条')
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
    # 完全内联版本：所有资源（JS/CSS/JSON）都已打包到 index.html
    # assets/ 目录仅在构建时需要，生成 index.html 后可安全删除
    find "$OUT_DIR" -mindepth 1 -not -name index.html -not -path "$OUT_DIR/assets" -not -path "$OUT_DIR/assets/*" -exec rm -rf {} + 2>/dev/null || true
    # 删除子目录中的 index.html (但保留 assets 内的)
    find "$OUT_DIR" -mindepth 2 -not -path "$OUT_DIR/assets/*" -name 'index.html' -exec rm -f {} + 2>/dev/null || true
    # 清理 assets/ 目录（index.html 已包含所有资源，无需外部引用）
    rm -rf "$OUT_DIR/assets" 2>/dev/null || true
    echo "  已清理 (仅保留 output/index.html)"
fi

echo ""
echo "=========================================="
echo "  清理完成 (CSV / metadata 已保留)"
echo "=========================================="
