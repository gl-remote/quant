# -*- coding: utf-8 -*-
"""报告生成编排 — 查数据 + 渲染模板 → 写文件"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

_env = Environment(
    loader=PackageLoader("report", "templates"),
    autoescape=select_autoescape(["html"]),
)


def build_all(db_path: str, output_dir: str, run_id: int) -> None:
    """回测完成后统一入口"""
    _build_single_reports(db_path, run_id, output_dir)
    build_dashboard(db_path, run_id, output_dir)
    build_nav(db_path, output_dir)


def build_dashboard(db_path: str, run_id: int, output_dir: str) -> str:
    from .queries.backtest import get_run_summary, get_equity_data, get_report_list
    from .queries.optuna import get_optuna_data

    symbols = get_run_summary(db_path, run_id)
    equity = None
    if symbols:
        equity = get_equity_data(db_path, symbols[0]["symbol"], run_id)
    optuna = get_optuna_data(db_path, run_id)
    reports = get_report_list(db_path, run_id, output_dir)

    html = _env.get_template("dashboard.html").render(
        run_id=run_id,
        symbols=symbols,
        equity=equity,
        optuna=optuna,
        reports=reports,
    )
    study_dir = Path(output_dir) / f"r{run_id}"
    study_dir.mkdir(parents=True, exist_ok=True)
    (study_dir / "index.html").write_text(html, encoding="utf-8")
    return str(study_dir / "index.html")


def build_nav(db_path: str, output_dir: str) -> str:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, strategy, engine, symbols, created_at FROM runs ORDER BY id DESC"
    ).fetchall()
    conn.close()

    runs = [
        {"id": r[0], "strategy": r[1], "engine": r[2], "symbols": r[3], "created": r[4]}
        for r in rows
    ]
    html = _env.get_template("nav.html").render(runs=runs)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    return str(out / "index.html")


def _build_single_reports(db_path: str, run_id: int, output_dir: str) -> None:
    try:
        from report import build_report
        from data import DataManager
        dm = DataManager()
        conn = sqlite3.connect(db_path)
        bt_ids = [
            r[0] for r in conn.execute(
                "SELECT id FROM backtests WHERE run_id=? AND status='success'", (run_id,)
            ).fetchall()
        ]
        conn.close()
        for bid in bt_ids:
            build_report(dm, bid, output_dir=output_dir)
    except Exception:
        pass
