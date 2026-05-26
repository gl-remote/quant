# -*- coding: utf-8 -*-
"""回测看板生成器 — 纯静态 HTML + Plotly.js

生成 output/index.html 导航页 + output/{study}/index.html 双看版。
回测完成后自动调用，不依赖任何服务端。
"""

from __future__ import annotations

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _escape(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_all(db_path: str, output_dir: str) -> None:
    """回测完成后统一入口：扫最新 study → 建看板 → 刷新导航"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT study_name FROM studies ORDER BY study_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return
    study_name = row[0]
    build_dashboard(db_path, study_name, output_dir)
    build_nav(output_dir)


def build_dashboard(db_path: str, study_name: str, output_dir: str) -> str:
    """生成双看版页面"""
    conn = sqlite3.connect(db_path)

    study_dir = Path(output_dir) / study_name
    study_dir.mkdir(parents=True, exist_ok=True)

    html = _render_page(conn, study_name)
    filepath = study_dir / "index.html"
    filepath.write_text(html, encoding="utf-8")

    conn.close()
    return str(filepath.resolve())


def build_nav(output_dir: str) -> str:
    """重建导航页"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    entries = sorted(
        [d for d in out.iterdir() if d.is_dir()],
        reverse=True,
    )

    rows_html = ""
    for d in entries:
        name = d.name
        rows_html += (
            f'<tr><td>📁 <a href="{_escape(name)}/">{_escape(name)}</a></td>'
            f"<td>{_escape(datetime.fromtimestamp(d.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'))}</td></tr>\n"
        )

    if not rows_html:
        rows_html = '<tr><td colspan="2" style="color:#999;text-align:center">暂无回测记录，运行 <code>./tools/test-ma.sh</code> 后刷新</td></tr>'

    nav_html = _NAV_TEMPLATE.format(rows=rows_html)
    (out / "index.html").write_text(nav_html, encoding="utf-8")
    return str(out / "index.html")


# ── HTML 模板 ──────────────────────────────────────────────────

_NAV_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化回测监控</title>
<style>
body{{font-family:-apple-system,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#333}}
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
<thead><tr><th>回测目录</th><th>时间</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{study_name}</title>
<script src="https://cdn.plot.ly/plotly-3.0.1.min.js"></script>
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

def _render_page(conn: sqlite3.Connection, study_name: str) -> str:
    backtest_html = _render_backtest_tab(conn, study_name)
    optuna_html = _render_optuna_tab(conn, study_name)
    return _PAGE_TEMPLATE.format(
        study_name=study_name,
        backtest_tab=backtest_html,
        optuna_tab=optuna_html,
    )


def _render_backtest_tab(conn: sqlite3.Connection, study_name: str) -> str:
    """回测结果 Tab：品种汇总表 + 资金曲线"""
    # 找到 study 对应的时间窗口，取该时段所有 backtest
    study_row = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=? LIMIT 1", (study_name,)
    ).fetchone()
    if not study_row:
        return "<p>未找到研究记录</p>"

    study_id = study_row[0]
    # 取 study 时间窗口：起始 → 最后 trial 完成 + 30s（回测持久化在 trial 后）
    t0 = conn.execute(
        "SELECT datetime_start FROM trials WHERE study_id=? ORDER BY trial_id LIMIT 1",
        (study_id,),
    ).fetchone()
    t1 = conn.execute(
        "SELECT datetime_complete FROM trials WHERE study_id=? ORDER BY trial_id DESC LIMIT 1",
        (study_id,),
    ).fetchone()
    if not t0 or not t1:
        return "<p>无 trial 数据</p>"

    # 找最优 trial 参数，只展示该 trial 的回测结果
    best_params = conn.execute("""
        SELECT tp.param_name, tp.param_value
        FROM trial_params tp
        JOIN trial_values tv ON tp.trial_id = tv.trial_id
        JOIN trials t ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND tv.value=(SELECT MIN(tv2.value)
            FROM trial_values tv2 JOIN trials t2 ON tv2.trial_id=t2.trial_id WHERE t2.study_id=?)
    """, (study_id, study_id)).fetchall()
    best_params_dict = {p[0]: str(int(float(p[1]))) for p in best_params}

    # 取所有回测记录，按品种 + 最优参数匹配
    all_rows = conn.execute("""
        SELECT symbol, total_return, total_trades, win_rate, max_drawdown, sharpe_ratio,
               end_balance, initial_capital, id, params_json
        FROM backtests
        WHERE status='success'
          AND created_at BETWEEN ? AND datetime(?, '+30 seconds')
        ORDER BY symbol
    """, (t0[0], t1[0])).fetchall()

    # 按品种分组，找最接近最优参数的那条
    from collections import defaultdict
    by_sym = defaultdict(list)
    for r in all_rows:
        sym = r[0]
        pj = r[9] or "{}"
        try:
            p = json.loads(pj)
            # 计算参数匹配度
            match_score = sum(1 for k, v in best_params_dict.items() if str(p.get(k, "")) == v)
            by_sym[sym].append((match_score, r))
        except Exception:
            by_sym[sym].append((-1, r))

    rows = []
    for sym in sorted(by_sym):
        best = max(by_sym[sym], key=lambda x: x[0])
        rows.append(best[1])

    if not rows:
        return "<p>无回测记录</p>"

    parts = []
    parts.append('<h2>品种汇总</h2>')
    parts.append("""<table>
<thead><tr>
<th>品种</th><th>收益率</th><th>交易次数</th><th>胜率</th><th>最大回撤</th><th>夏普</th><th>最终权益</th>
</tr></thead><tbody>""")

    for r in rows:
        ret = float(r[1] or 0)
        wr = float(r[3] or 0) * 100
        dd = float(r[4] or 0) * 100
        sr = float(r[5] or 0)
        cls_ret = "badge-green" if ret > 0 else "badge-red"
        cls_sr = "badge-green" if sr > 0 else "badge-red"
        parts.append(
            f"<tr><td>{_escape(r[0])}</td>"
            f"<td class='{cls_ret}'>{ret*100:.2f}%</td>"
            f"<td>{r[2]}</td>"
            f"<td>{wr:.1f}%</td>"
            f"<td>{dd:.2f}%</td>"
            f"<td class='{cls_sr}'>{sr:.2f}</td>"
            f"<td>{float(r[6] or 0):,.0f}</td></tr>"
        )
    parts.append("</tbody></table>")

    # 资金曲线：取第一个品种的 daily
    first_sym = rows[0][0]
    daily_rows = conn.execute("""
        SELECT bd.date, bd.equity, bd.daily_return, bd.drawdown, b.id
        FROM backtest_daily bd
        JOIN backtests b ON bd.backtest_id = b.id
        WHERE b.symbol=? AND b.status='success'
          AND b.created_at BETWEEN ? AND datetime(?, '+30 seconds')
        ORDER BY bd.date
    """, (first_sym, t0[0], t1[0])).fetchall()

    if daily_rows:
        dates = [r[0] for r in daily_rows]
        equity = [float(r[1]) for r in daily_rows]
        dd_arr = [float(r[3]) for r in daily_rows]

        parts.append(f'<h2>资金曲线 — {_escape(first_sym)}</h2>')
        parts.append('<div id="chart-equity" class="chart"></div>')
        parts.append('<script>Plotly.newPlot("chart-equity",[{')
        parts.append(f'x:{json.dumps(dates)},y:{json.dumps(equity)},type:"scatter",name:"权益",')
        parts.append('line:{color:"#2563eb"}},')

        parts.append('{')
        parts.append(f'x:{json.dumps(dates)},y:{json.dumps(dd_arr)},type:"scatter",name:"回撤%",')
        parts.append('yaxis:"y2",line:{color:"#dc2626",dash:"dot"}}],')
        parts.append('{margin:{t:10},yaxis:{title:"权益"},yaxis2:{title:"回撤%",overlaying:"y",side:"right"},')
        parts.append('legend:{x:0,y:1}});</script>')

    return "\n".join(parts)


def _render_optuna_tab(conn: sqlite3.Connection, study_name: str) -> str:
    """参数优化 Tab：收敛曲线 + 参数分布"""
    study_row = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=? LIMIT 1", (study_name,)
    ).fetchone()
    if not study_row:
        return "<p>未找到优化记录</p>"

    study_id = study_row[0]
    trials = conn.execute("""
        SELECT t.number, tv.value
        FROM trials t
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

    # 最优参数
    best = conn.execute("""
        SELECT tp.param_name, tp.param_value
        FROM trial_params tp
        JOIN trial_values tv ON tp.trial_id = tv.trial_id
        JOIN trials t ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND tv.value=(SELECT MIN(tv2.value) FROM trial_values tv2 JOIN trials t2 ON tv2.trial_id=t2.trial_id WHERE t2.study_id=?)
        ORDER BY tp.param_name
    """, (study_id, study_id)).fetchall()

    parts = []
    parts.append(f'<h2>优化概览</h2>')
    parts.append(f'<p>Study: {_escape(study_name)} | Trials: {len(trials)}</p>')

    # 最优参数表
    if best:
        parts.append('<h3>最优参数</h3><table><thead><tr><th>参数</th><th>值</th></tr></thead><tbody>')
        for p in best:
            val = float(p[1])
            parts.append(f"<tr><td>{_escape(p[0])}</td><td>{val:.0f}</td></tr>")
        parts.append("</tbody></table>")

    # 收敛曲线
    if trials:
        nums = [t[0] for t in trials]
        values = [float(t[1] or 0) for t in trials]
        parts.append('<h3>优化收敛曲线</h3>')
        parts.append('<div id="chart-converge" class="chart"></div>')
        parts.append('<script>Plotly.newPlot("chart-converge",[{')
        parts.append(f'x:{json.dumps(nums)},y:{json.dumps(values)},type:"scatter",mode:"lines+markers",')
        parts.append('line:{color:"#2563eb"},marker:{size:6}}],')
        parts.append('{margin:{t:10},xaxis:{title:"Trial"},yaxis:{title:"Score"}});</script>')

    # 参数空间散点图
    if params_rows:
        import itertools
        from collections import defaultdict
        param_data = defaultdict(list)
        trial_scores = {}
        for t in trials:
            trial_scores[t[0]] = float(t[1] or 0)
        for r in params_rows:
            param_data[r[1]].append((r[0], float(r[2])))

        param_names = sorted(param_data.keys())
        if len(param_names) >= 2:
            p1, p2 = param_names[0], param_names[1]
            x_vals = [float(trial_scores[n]) for n, _ in param_data[p1] if n in trial_scores]
            y_vals = [float(v) for _, v in param_data[p1]]
            z_vals = [trial_scores.get(n, 0) for n, _ in param_data[p1]]

            p2_dict = dict(param_data[p2])
            x2 = [v for _, v in param_data[p1]]
            y2 = [p2_dict.get(n, 0.0) for n, _ in param_data[p1]]

            parts.append(f'<h3>{_escape(p1)} × {_escape(p2)} → Score</h3>')
            parts.append('<div id="chart-params" class="chart"></div>')
            parts.append('<script>Plotly.newPlot("chart-params",[{')
            parts.append(f'x:{json.dumps(y_vals)},y:{json.dumps(y2)},type:"scatter",mode:"markers",')
            parts.append('marker:{size:10,color:')
            parts.append(json.dumps(z_vals))
            parts.append(',colorscale:"RdYlGn",showscale:true,colorbar:{title:"Score"}},')
            parts.append(f'hovertemplate:"{_escape(p1)}: %{{x}}<br>{_escape(p2)}: %{{y}}<br>Score: %{{marker.color:.2f}}<extra></extra>"}}]')
            parts.append(',{margin:{t:10},xaxis:{title:')
            parts.append(json.dumps(p1))
            parts.append('},yaxis:{title:')
            parts.append(json.dumps(p2))
            parts.append('}});</script>')

    return "\n".join(parts)
