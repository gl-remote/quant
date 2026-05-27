# -*- coding: utf-8 -*-
"""报告生成编排 — export JSON → 数据写入 → 前端构建

将 Jinja2 模板渲染替换为 JSON 数据导出 + React 前端构建。
一次 build_all() = 全部 JSON 导出 + 增量前端构建 + 入口 HTML 写入。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sqlite3
from pathlib import Path

import pandas as pd

from .kline_cache import KlineCache

logger = logging.getLogger(__name__)

KLINE_DOWNSAMPLE_THRESHOLD = 5000


# ── Public API ──────────────────────────────────────────────────


def build_all(db_path: str, output_dir: str, run_id: int) -> None:
    """回测完成后统一入口

    1. 导出全部 JSON 数据文件
    2. 增量构建 React 前端
    3. 写入入口 HTML

    Args:
        db_path: SQLite 数据库路径
        output_dir: 输出根目录 (e.g. "output")
        run_id: run_id
    """
    export_run_json(db_path, output_dir, run_id)
    export_summary_json(db_path, output_dir, run_id)
    export_backtests_json(db_path, output_dir, run_id)
    export_equity_json(db_path, output_dir, run_id)
    export_kline_json(db_path, output_dir, run_id)
    export_optuna_json(db_path, output_dir, run_id)
    write_nav_json(db_path, output_dir)
    build_frontend(output_dir)
    write_entry_html(output_dir)
    logger.info("报告构建完成: output/r%d/", run_id)


# ── JSON 导出函数 ────────────────────────────────────────────────


def export_run_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出单次 run 的元信息"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs WHERE id=?",
        (run_id,),
    ).fetchone()
    conn.close()

    if not row:
        logger.warning("run_id=%d 不存在", run_id)
        return

    data = {
        "id": row[0],
        "strategy": row[1],
        "engine": row[2],
        "symbols": row[3],
        "status": row[4],
        "created_at": row[5],
    }
    _write_json(output_dir, f"r{run_id}/data/run.json", data)


def export_summary_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出品种汇总表（每品种最优回测记录）"""
    from .queries.backtest import get_run_summary
    data = get_run_summary(db_path, run_id)
    _write_json(output_dir, f"r{run_id}/data/summary.json", data)


def export_backtests_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出所有回测记录完整信息（含指标、参数、日线数据）"""
    conn = sqlite3.connect(db_path)
    backtests = conn.execute(
        "SELECT id, symbol, strategy, status, start_date, end_date, "
        "initial_capital, end_balance, total_return, sharpe_ratio, "
        "max_drawdown, win_rate, total_trades, data_src, kline_interval, "
        "strategy_version, git_hash "
        "FROM backtests WHERE run_id=? AND status='success'",
        (run_id,),
    ).fetchall()

    result = []
    for bt in backtests:
        bt_id = bt[0]
        params = conn.execute(
            "SELECT param_name, param_value FROM backtest_params "
            "WHERE backtest_id=? ORDER BY param_name",
            (bt_id,),
        ).fetchall()

        daily = conn.execute(
            "SELECT date, equity, daily_return, drawdown "
            "FROM backtest_daily WHERE backtest_id=? ORDER BY date",
            (bt_id,),
        ).fetchall()

        daily_data = [
            {"date": d[0], "equity": d[1], "daily_return": d[2], "drawdown": d[3]}
            for d in daily
        ]

        result.append({
            "id": bt_id,
            "symbol": bt[1],
            "strategy": bt[2],
            "status": bt[3],
            "start_date": bt[4],
            "end_date": bt[5],
            "initial_capital": bt[6],
            "end_balance": bt[7],
            "total_return": bt[8],
            "sharpe_ratio": bt[9],
            "max_drawdown": bt[10],
            "win_rate": bt[11],
            "total_trades": bt[12],
            "data_src": bt[13],
            "kline_interval": bt[14],
            "strategy_version": bt[15],
            "git_hash": bt[16],
            "params": [{"name": p[0], "value": p[1]} for p in params],
            "daily": daily_data,
        })
    conn.close()

    _write_json(output_dir, f"r{run_id}/data/backtests.json", result)


def export_equity_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出资金曲线数据（每品种最优回测的日线权益/回撤）"""
    from .queries.backtest import get_equity_data, get_run_summary

    summary = get_run_summary(db_path, run_id)
    result = {}
    for s in summary:
        equity = get_equity_data(db_path, s["symbol"], run_id)
        if equity:
            result[s["symbol"]] = equity
    _write_json(output_dir, f"r{run_id}/data/equity.json", result)


def export_kline_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出 K 线数据 JSON（使用 KlineCache 避免重复转换）

    从 backtests 表获取各品种的 CSV 路径和日期范围，
    按品种独立生成 kline_{symbol}.json。
    """
    cache = KlineCache(output_dir)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT DISTINCT symbol,
               FIRST_VALUE(data_src) OVER w AS data_src,
               FIRST_VALUE(start_date) OVER w AS start_date,
               FIRST_VALUE(end_date) OVER w AS end_date,
               FIRST_VALUE(kline_interval) OVER w AS kline_interval
        FROM backtests
        WHERE run_id=? AND status='success' AND data_src IS NOT NULL
        WINDOW w AS (PARTITION BY symbol ORDER BY id)
    """, (run_id,)).fetchall()
    conn.close()

    for row in rows:
        symbol = row[0]
        data_src = row[1]
        start_date = row[2]
        end_date = row[3]
        interval = row[4] or "1m"
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.json"

        if cache.copy_to(symbol, data_src, interval, dest):
            logger.info("K线缓存命中: %s", symbol)
            continue

        if not data_src or not Path(data_src).exists():
            logger.warning("K线数据源不存在: %s → %s", symbol, data_src)
            continue

        kline_dict = _build_kline_dict(
            data_src, symbol, interval, start_date, end_date
        )
        if kline_dict:
            cache.put(symbol, data_src, interval, kline_dict)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info("K线已导出: %s → %s", symbol, dest.name)


def export_optuna_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出 Optuna 优化数据 JSON（含 Plotly chart specs）"""
    from .queries.optuna import get_optuna_data

    optuna_data = get_optuna_data(db_path, run_id)
    if not optuna_data:
        return

    conn = sqlite3.connect(db_path)
    study_rows = conn.execute(
        "SELECT study_name FROM run_studies WHERE run_id=?", (run_id,)
    ).fetchall()
    conn.close()

    charts_spec = {}
    if study_rows:
        try:
            from .optimizer_report import build_optuna_spec
            study_db_url = f"sqlite:///{os.path.abspath(db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_rows[0][0])
        except Exception as e:
            logger.warning("Optuna chart spec 生成失败: %s", e)

    result = {
        "study_name": optuna_data.get("study_name"),
        "trial_count": optuna_data.get("trial_count"),
        "trial_nums": optuna_data.get("trial_nums"),
        "trial_values": optuna_data.get("trial_values"),
        "best_params": optuna_data.get("best_params"),
        "param_scatter": optuna_data.get("param_scatter"),
        "charts": charts_spec,
    }
    _write_json(output_dir, f"r{run_id}/data/optuna.json", result)


def write_nav_json(db_path: str, output_dir: str) -> None:
    """导出全局导航数据 JSON"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs ORDER BY id DESC"
    ).fetchall()
    conn.close()

    runs = [
        {
            "id": r[0], "strategy": r[1], "engine": r[2],
            "symbols": r[3], "status": r[4], "created": r[5],
        }
        for r in rows
    ]
    _write_json(output_dir, "data/nav.json", runs)


# ── 前端构建 ──────────────────────────────────────────────────


def build_frontend(output_dir: str) -> None:
    """检查 React 源码 hash，必要时触发 npm run build，并复制 vendor 文件"""
    web_dir = Path(__file__).parent / "web"
    assets_dir = Path(output_dir) / "assets"

    if not (web_dir / "package.json").exists():
        logger.info("前端工程未初始化，跳过构建")
        return

    src_hash = _compute_dir_hash(web_dir / "src") + _compute_dir_hash(
        web_dir / "public"
    )
    hash_file = assets_dir / ".build_hash"

    needs_build = True
    if hash_file.exists() and hash_file.read_text().strip() == src_hash:
        logger.info("前端源码未变更，跳过构建")
        needs_build = False

    if needs_build:
        logger.info("开始前端构建...")
        _clean_old_bundles(assets_dir)
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(web_dir),
            check=True,
            env={
                **os.environ,
                "VITE_OUT_DIR": str(assets_dir.absolute()),
            },
        )
        assets_dir.mkdir(parents=True, exist_ok=True)
        hash_file.write_text(src_hash)
        logger.info("前端构建完成")

    _copy_plotly_vendor(web_dir, assets_dir)


def _copy_plotly_vendor(web_dir: Path, assets_dir: Path) -> None:
    src = web_dir / "public" / "vendor" / "plotly.min.js"
    if not src.exists():
        logger.warning("plotly.min.js 未找到: %s", src)
        return
    dest_dir = assets_dir / "vendor"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "plotly.min.js"
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        import shutil
        shutil.copy2(src, dest)
        logger.info("plotly.min.js 已复制到 %s", dest)
    else:
        logger.info("plotly.min.js 已是最新，跳过复制")


def write_entry_html(output_dir: str) -> None:
    """生成 output/index.html 单入口文件

    将所有 JSON 数据预加载为 window.__DATA__ 全局变量，
    彻底避免 file:// 协议下的 CORS 问题。
    """
    assets_dir = Path(output_dir) / "assets"

    js_file = _find_built_file(assets_dir, "index-*.js")
    css_file = _find_built_file(assets_dir, "index-*.css")

    if not js_file:
        logger.warning("未找到 Vite 构建产物，生成降级入口")
        _write_fallback_html(output_dir)
        return

    preload_script = _build_preload_script(output_dir)

    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
        '<title>量化回测监控</title>',
        f'<link rel="stylesheet" href="assets/{css_file}">' if css_file else '',
        '<script src="assets/vendor/plotly.min.js"></script>',
        '</head>',
        '<body>',
        '<div id="root"></div>',
        preload_script,
        f'<script src="assets/{js_file}"></script>',
        '</body>',
        '</html>',
    ]
    out_path = Path(output_dir) / "index.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    logger.info("入口 HTML 已生成: %s", out_path)


def _build_preload_script(output_dir: str) -> str:
    """读取所有 JSON 数据文件，嵌入为 window.__DATA__ 对象"""
    root = Path(output_dir)
    data_map: dict[str, object] = {}

    _collect_json(root / "data", "data", data_map)

    for run_dir in sorted(root.glob("r*/data")):
        prefix = run_dir.parent.name + "/data"
        _collect_json(run_dir, prefix, data_map)

    if not data_map:
        return "<script>window.__DATA__ = {};</script>"

    json_str = json.dumps(data_map, ensure_ascii=False, default=str)
    mib = len(json_str.encode("utf-8")) / (1024 * 1024)
    logger.info("预加载 %d 个数据文件 (%.1f MiB)", len(data_map), mib)

    return f"<script>window.__DATA__ = {json_str};</script>"


def _collect_json(
    data_dir: Path,
    prefix: str,
    data_map: dict[str, object],
) -> None:
    for f in sorted(data_dir.glob("*.json")):
        key = f"{prefix}/{f.name}"
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data_map[key] = json.load(fh)
        except Exception as e:
            logger.warning("预加载失败 [%s]: %s", key, e)


# ── 内部辅助 ──────────────────────────────────────────────────


def _build_kline_dict(
    csv_path: str,
    symbol: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
) -> dict | None:
    """从 CSV 构建 K 线 JSON dict (daily resampled + raw 降采样)"""
    try:
        df = pd.read_csv(csv_path)
        if "datetime" not in df.columns:
            if "date" in df.columns:
                df["datetime"] = df["date"]
            else:
                return None

        df["datetime"] = pd.to_datetime(df["datetime"])

        if start_date:
            df = df[df["datetime"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["datetime"] <= pd.Timestamp(end_date)]

        if df.empty:
            return None

        df_daily = df.set_index("datetime")
        daily_ohlc = (
            df_daily.resample("1d")
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
            .dropna()
        )

        daily_data = [
            {
                "datetime": str(idx.date()),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume),
            }
            for idx, row in daily_ohlc.iterrows()
        ]

        raw_data = []
        total = len(df)
        skip = (
            max(1, total // KLINE_DOWNSAMPLE_THRESHOLD)
            if total > KLINE_DOWNSAMPLE_THRESHOLD
            else 1
        )

        for i in range(0, total, skip):
            row = df.iloc[i]
            raw_data.append({
                "datetime": str(row["datetime"]),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            })

        return {
            "symbol": symbol,
            "interval": interval,
            "csv_source": csv_path,
            "daily": daily_data,
            "raw": raw_data,
            "raw_count": total,
            "raw_downsampled": total > KLINE_DOWNSAMPLE_THRESHOLD,
            "raw_sample_max": KLINE_DOWNSAMPLE_THRESHOLD,
        }

    except Exception as e:
        logger.error("K线数据构建失败 [%s]: %s", symbol, e)
        return None


def _write_json(output_dir: str, rel_path: str, data: object) -> None:
    full_path = Path(output_dir) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _compute_dir_hash(directory: Path) -> str:
    if not directory.exists():
        return ""
    hasher = hashlib.md5()
    for f in sorted(directory.rglob("*")):
        if f.is_file():
            hasher.update(f.read_bytes())
    return hasher.hexdigest()


def _find_built_file(directory: Path, glob_pattern: str) -> str | None:
    import glob as _glob
    matches = sorted(
        _glob.glob(str(directory / glob_pattern)),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    return Path(matches[0]).name if matches else None


def _clean_old_bundles(assets_dir: Path) -> None:
    for f in assets_dir.glob("index-*.js"):
        f.unlink()
    for f in assets_dir.glob("index-*.css"):
        f.unlink()


def _write_fallback_html(output_dir: str) -> None:
    """降级 HTML：不依赖前端构建，纯文本导航"""
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n'
        '<head><meta charset="UTF-8"><title>量化回测监控</title></head>\n'
        '<body>\n<h1>量化回测监控</h1>\n'
        '<p>前端资源未构建。请先执行 <code>cd report/web && npm run build</code></p>\n'
        '</body>\n</html>'
    )
    (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")