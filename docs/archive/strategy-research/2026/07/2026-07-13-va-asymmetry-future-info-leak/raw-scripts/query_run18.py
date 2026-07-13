"""查询 run_id=18"""
import sqlite3
import pandas as pd
DB = "/Users/gaolei/Documents/src/quant/project_data/database/backtest/quant.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("PRAGMA table_info(backtests)")
cols = [c[1] for c in cur.fetchall()]
print("backtests 列:", cols)

sel_cols = [c for c in ['id','symbol','total_trades','total_net_pnl','annual_return','sharpe_ratio','max_drawdown','turnover','pnl_gross_ccy','pnl_fee_ccy','pnl_slippage_ccy','commission'] if c in cols]
print("selecting:", sel_cols)

bts = pd.read_sql(f"SELECT {','.join(sel_cols)} FROM backtests WHERE run_id = 18 ORDER BY total_net_pnl DESC", conn)
with pd.option_context("display.float_format", "{:,.2f}".format, "display.width", 240):
    print(bts.to_string(index=False))
print("\n=== 汇总 ===")
sum_cols = [c for c in ['total_trades','total_net_pnl','pnl_gross_ccy','pnl_fee_ccy','pnl_slippage_ccy','turnover'] if c in bts.columns]
with pd.option_context("display.float_format", "{:,.2f}".format):
    print(bts[sum_cols].sum().to_string())

# backtest_trades
cur.execute("PRAGMA table_info(backtest_trades)")
tcols = [c[1] for c in cur.fetchall()]
print("\nbacktest_trades 列:", tcols)
sel_tcols = [c for c in ['direction','entry_price','exit_price','qty','pnl_net_ccy','entry_time','exit_time','exit_reason','symbol'] if c in tcols]
# 实际列要加 b.symbol，我们先直接拿所有关联列
trades = pd.read_sql("""
    SELECT b.symbol, t.*
    FROM backtest_trades t JOIN backtests b ON t.backtest_id=b.id
    WHERE b.run_id = 18 ORDER BY t.entry_time ASC
""", conn)
if len(trades):
    print(f"\n总笔数: {len(trades)}")
    show_cols = [c for c in ['symbol','direction','entry_price','exit_price','qty','pnl_net_ccy','entry_time','exit_time','exit_reason'] if c in trades.columns]
    with pd.option_context("display.float_format", "{:,.2f}".format, "display.width", 260):
        print(trades[show_cols].to_string(index=False))
    print("\n方向分布:")
    print(trades['direction'].value_counts().to_string())
    print("\n退出原因:")
    if 'exit_reason' in trades.columns:
        print(trades['exit_reason'].value_counts().to_string())
    print("\n单笔 pnl_net_ccy 描述:")
    with pd.option_context("display.float_format", "{:,.2f}".format):
        print(trades['pnl_net_ccy'].describe().to_string())
conn.close()
