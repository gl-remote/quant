# -*- coding: utf-8 -*-
"""回测看板生成器 — 纯静态 HTML + Plotly.js"""

from __future__ import annotations

import json
import sqlite3
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def _escape(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_all(db_path: str, output_dir: str, run_id: int) -> None:
    """回测完成后统一入口"""
    build_dashboard(db_path, run_id, output_dir)
    _build_single_report(db_path, run_id, output_dir)
    build_nav(db_path, output_dir)


def build_dashboard(db_path: str, run_id: int, output_dir: str) -> str:
    conn = sqlite3.connect(db_path)
    study_dir = Path(output_dir) / f"r{run_id}"
    study_dir.mkdir(parents=True, exist_ok=True)
    html = _render_page(conn, run_id)
    filepath = study_dir / "index.html"
    filepath.write_text(html, encoding="utf-8")
    conn.close()
    return str(filepath.resolve())


def build_nav(db_path: str, output_dir: str) -> str:
    conn = sqlite3.connect(db_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = conn.execute("""
        SELECT id, strategy, engine, symbols, created_at FROM runs ORDER BY id DESC
    """).fetchall()

    rows_html = ""
    for r in rows:
        rid, strategy, engine, symbols, created = r
        rows_html += (
            f'<tr><td>📁 <a href="r{rid}/index.html">r{rid}</a></td>'
            f"<td>{_escape(strategy)}</td><td>{_escape(engine)}</td>"
            f"<td>{symbols}</td><td>{created[:16] if created else ''}</td></tr>\n"
        )

    if not rows_html:
        rows_html = '<tr><td colspan="5" style="color:#999;text-align:center">暂无回测记录</td></tr>'

    nav_html = _NAV_TEMPLATE.format(rows=rows_html)
    (out / "index.html").write_text(nav_html, encoding="utf-8")
    conn.close()
    return str(out / "index.html")


def _build_single_report(db_path: str, run_id: int, output_dir: str) -> None:
    try:
        from report import build_report
        from data import DataManager
        dm = DataManager()
        conn = sqlite3.connect(db_path)
        bt = conn.execute(
            "SELECT id FROM backtests WHERE run_id=? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        conn.close()
        if bt:
            study_dir = Path(output_dir) / f"r{run_id}"
            build_report(dm, bt[0], output_dir=str(study_dir))
    except Exception:
        pass


# ── HTML 模板 ──────────────────────────────────────────────────

_NAV_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化回测监控</title>
<style>
body{{font-family:-apple-system,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;color:#333}}
h1{{border-bottom:2px solid #2563eb;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin-top:20px}}
th{{text-align:left;padding:10px 8px;border-bottom:2px solid #e5e7eb;color:#666;font-weight:600}}
td{{padding:10px 8px;border-bottom:1px solid #f3f4f6}}
a{{color:#2563eb;text-decoration:none}}
a:hover{{text-decoration:underline}}
</style>
</head>
<body>
<h1>📊 量化回测监控</h1>
<table>
<thead><tr><th>回测</th><th>策略</th><th>engine</th><th>品种</th><th>时间</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>r{run_id}</title>
<script src="../assets/plotly.min.js"></script>
<style>
body{{font-family:-apple-system,sans-serif;margin:0;padding:0;color:#333}}
.tabs{{display:flex;border-bottom:2px solid #e5e7eb;background:#f9fafb;position:sticky;top:0;z-index:10}}
.tab-btn{{padding:12px 24px;border:none;background:none;cursor:pointer;font-size:15px;color:#666;border-bottom:2px solid transparent;margin-bottom:-2px}}
.tab-btn.active{{color:#2563eb;border-bottom-color:#2563eb;font-weight:600}}
.tab-content{{display:none;padding:24px;max-width:1400px;margin:0 auto}}
.tab-content.active{{display:block}}
.chart{{margin:20px 0}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}}
th{{text-align:left;padding:8px;background:#f9fafb;border-bottom:2px solid #e5e7eb}}
td{{padding:8px;border-bottom:1px solid #f3f4f6}}
.badge-green{{color:#059669}}
.badge-red{{color:#dc2626}}
h2{{font-size:20px;margin:24px 0 12px}}
</style>
</head>
<body>
<div class="tabs">
<button class="tab-btn active" onclick="showTab('backtest',this)">📈 回测结果</button>
<button class="tab-btn" onclick="showTab('optuna',this)">🔬 参数优化</button>
</div>
<div id="tab-backtest" class="tab-content active">
{backtest_tab}
</div>
<div id="tab-optuna" class="tab-content">
{optuna_tab}
</div>
<script>
function showTab(name,btn){{
 document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
 document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
 btn.classList.add('active');
 document.getElementById('tab-'+name).classList.add('active');
}}
</script>
</body>
</html>"""


# ── 渲染函数 ──────────────────────────────────────────────────

def _render_page(conn: sqlite3.Connection, run_id: int) -> str:
    return _PAGE_TEMPLATE.format(
        run_id=run_id,
        backtest_tab=_render_backtest_tab(conn, run_id),
        optuna_tab=_render_optuna_tab(conn, run_id),
    )


def _render_backtest_tab(conn: sqlite3.Connection, run_id: int) -> str:
    rows = conn.execute("""
        SELECT symbol, total_return, total_trades, win_rate, max_drawdown, sharpe_ratio,
               end_balance
        FROM backtests
        WHERE run_id=? AND status='success'
        ORDER BY symbol, total_return DESC
    """, (run_id,)).fetchall()

    if not rows:
        return "<p>无回测记录</p>"

    # 每品种取最优的一条（收益最高）
    best = {}
    for r in rows:
        sym = r[0]
        if sym not in best or r[1] > best[sym][1]:
            best[sym] = r

    parts = ['<h2>品种汇总</h2>']
    parts.append("""<table>
<thead><tr><th>品种</th><th>收益率</th><th>交易次数</th><th>胜率</th><th>最大回撤</th><th>夏普</th><th>最终权益</th></tr></thead>
<tbody>""")

    first_sym = None
    for sym in sorted(best):
        r = best[sym]
        if first_sym is None:
            first_sym = sym
        ret = float(r[1] or 0)
        wr = float(r[3] or 0) * 100
        dd = float(r[4] or 0) * 100
        sr = float(r[5] or 0)
        cls_ret = "badge-green" if ret > 0 else "badge-red"
        cls_sr = "badge-green" if sr > 0 else "badge-red"
        parts.append(
            f"<tr><td>{_escape(sym)}</td>"
            f"<td class='{cls_ret}'>{ret*100:.2f}%</td>"
            f"<td>{r[2]}</td><td>{wr:.1f}%</td><td>{dd:.2f}%</td>"
            f"<td class='{cls_sr}'>{sr:.2f}</td>"
            f"<td>{float(r[6] or 0):,.0f}</td></tr>"
        )
    parts.append("</tbody></table>")

    # 资金曲线
    if first_sym:
        daily_rows = conn.execute("""
            SELECT bd.date, bd.equity, bd.drawdown
            FROM backtest_daily bd
            JOIN backtests b ON bd.backtest_id = b.id
            WHERE b.symbol=? AND b.run_id=? AND b.status='success'
            ORDER BY bd.date
        """, (first_sym, run_id)).fetchall()

        if daily_rows:
            dates = [r[0] for r in daily_rows]
            equity = [float(r[1]) for r in daily_rows]
            dd_arr = [float(r[2]) for r in daily_rows]
            parts.append(f'<h2>资金曲线 — {_escape(first_sym)}</h2>')
            parts.append('<div id="chart-equity" class="chart"></div>')
            parts.append('<script>Plotly.newPlot("chart-equity",[{')
            parts.append(f'x:{json.dumps(dates)},y:{json.dumps(equity)},type:"scatter",name:"权益",line:{{color:"#2563eb"}}}},')
            parts.append('{')
            parts.append(f'x:{json.dumps(dates)},y:{json.dumps(dd_arr)},type:"scatter",name:"回撤%",')
            parts.append('yaxis:"y2",line:{color:"#dc2626",dash:"dot"}}],')
            parts.append('{margin:{t:10,b:50,l:60,r:60},yaxis:{title:"权益"},yaxis2:{title:"回撤%",overlaying:"y",side:"right"},legend:{x:0,y:1}});</script>')

    return "\n".join(parts)


def _render_optuna_tab(conn: sqlite3.Connection, run_id: int) -> str:
    # 通过 run_studies 找到 study_name
    study_rows = conn.execute(
        "SELECT study_name FROM run_studies WHERE run_id=?", (run_id,)
    ).fetchall()

    if not study_rows:
        return "<p>无优化记录</p>"

    # 取第一个 study
    study_name = study_rows[0][0]
    study = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=? LIMIT 1", (study_name,)
    ).fetchone()
    if not study:
        return "<p>未找到 study</p>"

    study_id = study[0]

    trials = conn.execute("""
        SELECT t.number, tv.value FROM trials t
        LEFT JOIN trial_values tv ON t.trial_id = tv.trial_id
        WHERE t.study_id=? AND t.state='COMPLETE'
        ORDER BY t.number
    """, (study_id,)).fetchall()

    params_rows = conn.execute("""
        SELECT t.number, tp.param_name, tp.param_value
        FROM trials t
        JOIN trial_params tp ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND t.state='COMPLETE'
        ORDER BY t.number, tp.param_name
    """, (study_id,)).fetchall()

    best = conn.execute("""
        SELECT tp.param_name, tp.param_value FROM trial_params tp
        JOIN trial_values tv ON tp.trial_id = tv.trial_id
        JOIN trials t ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND tv.value=(
            SELECT MIN(tv2.value) FROM trial_values tv2
            JOIN trials t2 ON tv2.trial_id=t2.trial_id WHERE t2.study_id=?)
        ORDER BY tp.param_name
    """, (study_id, study_id)).fetchall()

    parts = [f'<h2>优化概览</h2>', f'<p>Study: {_escape(study_name)} | Trials: {len(trials)}</p>']

    if best:
        parts.append('<h3>最优参数</h3><table><thead><tr><th>参数</th><th>值</th></tr></thead><tbody>')
        for p in best:
            parts.append(f"<tr><td>{_escape(p[0])}</td><td>{float(p[1]):.0f}</td></tr>")
        parts.append("</tbody></table>")

    if trials:
        nums = [t[0] for t in trials]
        values = [float(t[1] or 0) for t in trials]
        parts.append('<h3>优化收敛曲线</h3><div id="chart-converge" class="chart"></div>')
        parts.append(f'<script>Plotly.newPlot("chart-converge",[{{x:{json.dumps(nums)},y:{json.dumps(values)},type:"scatter",mode:"lines+markers",line:{{color:"#2563eb"}},marker:{{size:6}}}}],{{margin:{{t:10,b:50,l:55}},xaxis:{{title:"Trial"}},yaxis:{{title:"Score"}}}});</script>')

    if params_rows and len(set(p[1] for p in params_rows)) >= 2:
        # 参数散点图
        param_names = sorted(set(p[1] for p in params_rows))
        p1, p2 = param_names[0], param_names[1]
        p1_vals = [float(p[2]) for p in params_rows if p[1] == p1]
        p2_vals = [float(p[2]) for p in params_rows if p[1] == p2]
        scores = [float(t[1] or 0) for t in trials]
        parts.append(f'<h3>{_escape(p1)} × {_escape(p2)} → Score</h3>')
        parts.append('<div id="chart-params" class="chart"></div>')
        parts.append(f'<script>Plotly.newPlot("chart-params",[{{x:{json.dumps(p1_vals)},y:{json.dumps(p2_vals)},type:"scatter",mode:"markers",marker:{{size:10,color:{json.dumps(scores)},colorscale:"RdYlGn",showscale:true,colorbar:{{title:"Score"}}}}}}],{{margin:{{t:10,b:50,l:55}},xaxis:{{title:{json.dumps(p1)}}},yaxis:{{title:{json.dumps(p2)}}}}});</script>')

    return "\n".join(parts)
