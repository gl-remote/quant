# -*- coding: utf-8 -*-
"""回测数据查询"""

import sqlite3
from collections import defaultdict
from typing import Any


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
