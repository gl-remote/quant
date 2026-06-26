#!/bin/bash
# 分层清理 project_data — 默认保留行情 CSV / 数据库 metadata
# 用法: ./clean_data.sh [backtests|reports|cache|logs|runtime]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$SCRIPT_DIR/../.."
PROJECT_DATA="$ROOT_DIR/project_data"
DB="$PROJECT_DATA/database/quant_shared.db"
TARGET="${1:-backtests}"

clean_backtests() {
    echo ""
    echo "[clean-backtests] 清理数据库回测 / Optuna 数据..."
    if [ ! -f "$DB" ]; then
        echo "  数据库不存在: $DB"
        return
    fi

    uv run python -c "
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
}

clean_dir() {
    local label="$1"
    local dir="$2"
    echo ""
    echo "[$label] 清理 $dir"
    if [ -d "$dir" ]; then
        rm -rf "$dir"
        echo "  已删除"
    else
        echo "  不存在，跳过"
    fi
}

case "$TARGET" in
    backtests)
        clean_backtests
        ;;
    reports)
        clean_dir "clean-reports" "$PROJECT_DATA/reports"
        ;;
    cache)
        clean_dir "clean-cache" "$PROJECT_DATA/cache"
        ;;
    logs)
        clean_dir "clean-logs" "$PROJECT_DATA/logs"
        ;;
    runtime)
        clean_dir "clean-reports" "$PROJECT_DATA/reports"
        clean_dir "clean-cache" "$PROJECT_DATA/cache"
        clean_dir "clean-profiles" "$PROJECT_DATA/profiles"
        clean_dir "clean-coverage" "$PROJECT_DATA/coverage"
        ;;
    *)
        echo "未知清理目标: $TARGET" >&2
        echo "可选: backtests | reports | cache | logs | runtime" >&2
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  清理完成: $TARGET"
echo "  已保留: project_data/market_data 与 project_data/database/export_metadata"
echo "=========================================="
