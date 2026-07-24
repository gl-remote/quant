"""研究侧输出 + 工程侧 run_id=18 信号对比（7 合约子集）"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import sqlite3
import pandas as pd

# ── 1. 读研究侧 trades / events ──
R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
print("=" * 80)
print("研究侧 trades.parquet / events.parquet 概览")
print("=" * 80)

r_trades = pd.read_parquet(os.path.join(R_DIR, "trades.parquet"))
r_events = pd.read_parquet(os.path.join(R_DIR, "events.parquet"))

print(f"trades.parquet: {len(r_trades)} 行, 列={list(r_trades.columns)}")
print(r_trades.dtypes.to_string())
print("\n前 3 行:")
with pd.option_context("display.width", 260, "display.max_columns", 30):
    print(r_trades.head(3).to_string())

print(f"\n研究侧 合约覆盖: {sorted(r_trades['contract'].unique().tolist()) if 'contract' in r_trades.columns else '（需要看别的列）'}")
print(f"研究侧 总 unique合约数: {r_trades['contract'].nunique() if 'contract' in r_trades.columns else r_trades.iloc[:,0].nunique()}")

print(f"\nevents.parquet: {len(r_events)} 行, 列={list(r_events.columns)}")
with pd.option_context("display.width", 260, "display.max_columns", 30):
    print(r_events.head(3).to_string())

# ── 2. 取 7 合约子集 ──
TARGET = ["SHFE.rb2501","SHFE.hc2501","DCE.m2501","DCE.y2501","DCE.i2501","INE.sc2503","CZCE.MA501","CZCE.TA501"]
print(f"\n{'='*80}\n目标 7 合约（run_id=18 实际执行了 7 个）={TARGET}\n{'='*80}")

# 找研究侧 contract 列名
c_col = None
for col in ("contract","symbol","Contract","Symbol"):
    if col in r_trades.columns:
        c_col = col; break
print(f"研究侧 contract 列 = {c_col}")

# 目标在研究侧里的合约存在性
exist = [c for c in TARGET if c in r_trades[c_col].values]
print(f"在研究侧存在的合约: {exist}  ({len(exist)}/7)")

# ── 3. 工程侧 run_id=18 的实际交易 ──
DB = "/Users/gaolei/Documents/src/quant/project_data/database/backtest/quant.db"
conn = sqlite3.connect(DB)
# 先看 backtest_trades 的列 + 每笔开平配对（实际是一条 trade 记录是开仓还是平仓？需要判断）
cur = conn.cursor()
cur.execute("PRAGMA table_info(backtest_trades)")
bt_cols = [c[1] for c in cur.fetchall()]
print(f"\n工程侧 backtest_trades 列: {bt_cols}")

# 直接读 backtest_trades 所有相关行
e_trades_raw = pd.read_sql("""
    SELECT b.symbol, t.*
    FROM backtest_trades t JOIN backtests b ON t.backtest_id = b.id
    WHERE b.run_id = 18
    ORDER BY b.symbol, t.datetime ASC
""", conn)
print(f"\n工程侧 backtest_trades 原始行数: {len(e_trades_raw)}")
with pd.option_context("display.width", 260, "display.max_columns", 30):
    print(e_trades_raw.head(10).to_string())
print(f"offset 分布:\n{e_trades_raw['offset'].value_counts().to_string() if 'offset' in e_trades_raw.columns else 'N/A'}")
conn.close()

# 保存给下一步用（后面的 join 可以直接用）
out = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_signal_compare_7contracts"
os.makedirs(out, exist_ok=True)
r_trades.to_parquet(f"{out}/R_trades_all.parquet")
r_events.to_parquet(f"{out}/R_events_all.parquet")
e_trades_raw.to_parquet(f"{out}/E_trades_run18_raw.parquet")
print(f"\n已保存到 {out}/")
