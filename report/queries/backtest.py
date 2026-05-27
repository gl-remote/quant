# -*- coding: utf-8 -*-
"""回测数据查询"""

import sqlite3
from collections import defaultdict
from typing import Any
import pandas as pd
from pathlib import Path


def get_run_summary(db_path: str, run_id: int) -> list[dict[str, Any]]:
    """每品种最优回测记录"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT symbol, total_return, total_trades, win_rate, max_drawdown,
               sharpe_ratio, end_balance, params_json
        FROM backtests
        WHERE run_id=? AND status='success'
        ORDER BY symbol, total_return DESC
    """, (run_id,)).fetchall()

    best: dict[str, dict[str, Any]] = {}
    for r in rows:
        sym = r[0]
        if sym not in best or (r[1] or 0) > (best[sym].get('total_return') or 0):
            best[sym] = {
                'symbol': sym,
                'total_return': float(r[1] or 0),
                'total_trades': r[2],
                'win_rate': float(r[3] or 0) * 100,
                'max_drawdown': float(r[4] or 0) * 100,
                'sharpe': float(r[5] or 0),
                'end_balance': float(r[6] or 0),
                'ret_cls': 'badge-green' if (r[1] or 0) > 0 else 'badge-red',
                'sr_cls': 'badge-green' if (r[5] or 0) > 0 else 'badge-red',
            }
    conn.close()
    return [best[s] for s in sorted(best)]


def get_equity_data(db_path: str, symbol: str, run_id: int) -> dict[str, Any] | None:
    """获取资金曲线数据"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT bd.date, bd.equity, bd.drawdown
        FROM backtest_daily bd
        JOIN backtests b ON bd.backtest_id = b.id
        WHERE b.symbol=? AND b.run_id=? AND b.status='success'
        ORDER BY bd.date
    """, (symbol, run_id)).fetchall()
    conn.close()
    if not rows:
        return None
    return {
        'symbol': symbol,
        'dates': [r[0] for r in rows],
        'equity': [float(r[1]) for r in rows],
        'drawdown': [float(r[2]) for r in rows],
    }


def get_report_list(db_path: str, run_id: int, output_dir: str) -> list[dict[str, str]]:
    """获取该 run 下的所有回测报告"""
    import glob, os
    from pathlib import Path
    study_dir = Path(output_dir) / f"r{run_id}"
    reports = sorted(glob.glob(str(study_dir / "backtest_*.html")))
    result = []
    conn = sqlite3.connect(db_path)
    for rp in reports:
        fn = os.path.basename(rp)
        bid = fn.replace("backtest_", "").replace(".html", "")
        sym = conn.execute("SELECT symbol FROM backtests WHERE id=?", (bid,)).fetchone()
        result.append({'filename': fn, 'symbol': sym[0] if sym else '?'})
    conn.close()
    return result


def get_kline_data(db_path: str, symbol: str, run_id: int, export_dir: str = None) -> dict[str, Any] | None:
    """获取K线数据
    
    Args:
        db_path: 数据库路径
        symbol: 品种代码
        run_id: 运行ID
        export_dir: 导出目录（已废弃，保留用于兼容）
    """
    conn = sqlite3.connect(db_path)
    bt = conn.execute("""
        SELECT start_date, end_date, data_src FROM backtests 
        WHERE symbol=? AND run_id=? AND status='success' LIMIT 1
    """, (symbol, run_id)).fetchone()
    conn.close()
    
    if not bt:
        return None
    
    start_date, end_date, data_src = bt[0], bt[1], bt[2]
    
    if not data_src or not Path(data_src).exists():
        return None
    
    df = pd.read_csv(data_src)
    
    if 'datetime' not in df.columns:
        if 'date' in df.columns:
            df['datetime'] = df['date']
        else:
            return None
    
    df = df[(df['datetime'] >= f"{start_date} 00:00:00") & 
            (df['datetime'] <= f"{end_date} 23:59:59")]
    
    if df.empty:
        return None
    
    kline_data = []
    for _, row in df.iterrows():
        kline_data.append({
            'datetime': str(row['datetime']),
            'open': float(row.get('open', 0)),
            'high': float(row.get('high', 0)),
            'low': float(row.get('low', 0)),
            'close': float(row.get('close', 0)),
            'volume': int(row.get('volume', 0)),
        })
    
    return {'symbol': symbol, 'data': kline_data}


def get_trade_markers(db_path: str, symbol: str, run_id: int) -> dict[str, list[dict]]:
    """获取交易信号标记"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT b.id FROM backtests b 
        WHERE b.symbol=? AND b.run_id=? AND b.status='success' LIMIT 1
    """, (symbol, run_id)).fetchone()
    
    if not rows:
        return {'buy_markers': [], 'sell_markers': []}
    
    bt_id = rows[0]
    
    trades = conn.execute("""
        SELECT datetime, direction, offset, close_price, open_price 
        FROM backtest_trades 
        WHERE backtest_id=?
    """, (bt_id,)).fetchall()
    conn.close()
    
    buy_markers = []
    sell_markers = []
    
    for t in trades:
        dt = str(t[0])[:10]
        direction = str(t[1]).lower() if t[1] else ''
        offset = str(t[2]).lower() if t[2] else ''
        price = float(t[3]) if t[3] else (float(t[4]) if t[4] else 0)
        
        if direction == 'long' and offset == 'open':
            buy_markers.append({'date': dt, 'price': price})
        elif offset == 'close':
            sell_markers.append({'date': dt, 'price': price})
    
    return {'buy_markers': buy_markers, 'sell_markers': sell_markers}
