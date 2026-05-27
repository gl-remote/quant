# -*- coding: utf-8 -*-
"""
报告生成编排模块 — export JSON → 数据写入 → 前端构建

将 Jinja2 模板渲染替换为 JSON 数据导出 + React 前端构建。
一次 build_all() = 全部 JSON 导出 + 增量前端构建 + 入口 HTML 写入。
"""

from __future__ import annotations

import hashlib  # 用于计算文件哈希
import json  # 用于JSON序列化
import logging  # 用于日志记录
import os  # 用于操作系统相关操作
import subprocess  # 用于执行子进程
import sqlite3  # 用于SQLite数据库操作
from pathlib import Path  # 用于路径操作

import pandas as pd  # 用于数据处理

from .kline_cache import KlineCache  # 导入K线缓存类

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器

KLINE_DOWNSAMPLE_THRESHOLD = 5000  # K线数据降采样阈值，超过此数量时进行降采样


# ── 公开 API ──────────────────────────────────────────────────


def build_all(db_path: str, output_dir: str, run_id: int) -> None:
    """
    回测完成后统一入口

    执行步骤：
    1. 导出全部 JSON 数据文件
    2. 增量构建 React 前端
    3. 写入入口 HTML

    Args:
        db_path: SQLite 数据库路径
        output_dir: 输出根目录 (e.g. "output")
        run_id: 回测运行ID
    """
    # 依次导出各类数据
    export_run_json(db_path, output_dir, run_id)
    export_summary_json(db_path, output_dir, run_id)
    export_backtests_json(db_path, output_dir, run_id)
    export_equity_json(db_path, output_dir, run_id)
    export_kline_json(db_path, output_dir, run_id)
    export_optuna_json(db_path, output_dir, run_id)
    write_nav_json(db_path, output_dir)
    # 构建前端和入口HTML
    build_frontend(output_dir)
    write_entry_html(output_dir)
    logger.info("报告构建完成: output/r%d/", run_id)


# ── JSON 导出函数 ────────────────────────────────────────────────


def export_run_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出单次 run 的元信息到 JSON 文件
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    # 连接数据库并查询运行信息
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs WHERE id=?",
        (run_id,),
    ).fetchone()
    conn.close()

    # 检查是否找到记录
    if not row:
        logger.warning("run_id=%d 不存在", run_id)
        return

    # 构建数据字典
    data = {
        "id": row[0],
        "strategy": row[1],
        "engine": row[2],
        "symbols": row[3],
        "status": row[4],
        "created_at": row[5],
    }
    # 写入JSON文件
    _write_json(output_dir, f"r{run_id}/data/run.json", data)


def export_summary_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出品种汇总表（每品种最优回测记录）
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    from .queries.backtest import get_run_summary  # 导入查询函数
    # 获取汇总数据并写入
    data = get_run_summary(db_path, run_id)
    _write_json(output_dir, f"r{run_id}/data/summary.json", data)


def export_backtests_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出所有回测记录完整信息（含指标、参数、日线数据）
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    conn = sqlite3.connect(db_path)
    # 查询所有成功的回测记录
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
        # 查询回测参数
        params = conn.execute(
            "SELECT param_name, param_value FROM backtest_params "
            "WHERE backtest_id=? ORDER BY param_name",
            (bt_id,),
        ).fetchall()

        # 查询日线数据
        daily = conn.execute(
            "SELECT date, equity, daily_return, drawdown "
            "FROM backtest_daily WHERE backtest_id=? ORDER BY date",
            (bt_id,),
        ).fetchall()

        # 格式化日线数据
        daily_data = [
            {"date": d[0], "equity": d[1], "daily_return": d[2], "drawdown": d[3]}
            for d in daily
        ]

        # 构建完整回测记录
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

    # 写入JSON文件
    _write_json(output_dir, f"r{run_id}/data/backtests.json", result)


def export_equity_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出资金曲线数据（每品种最优回测的日线权益/回撤）
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    from .queries.backtest import get_equity_data, get_run_summary

    # 获取汇总信息
    summary = get_run_summary(db_path, run_id)
    result = {}
    # 为每个品种获取权益数据
    for s in summary:
        equity = get_equity_data(db_path, s["symbol"], run_id)
        if equity:
            result[s["symbol"]] = equity
    _write_json(output_dir, f"r{run_id}/data/equity.json", result)


def export_kline_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出 K 线数据 JSON（使用 KlineCache 避免重复转换）

    从 backtests 表获取各品种的 CSV 路径和日期范围，
    按品种独立生成 kline_{symbol}.json。
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    cache = KlineCache(output_dir)  # 初始化缓存

    # 连接数据库查询K线源信息
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

    # 处理每个品种的K线数据
    for row in rows:
        symbol = row[0]
        data_src = row[1]
        start_date = row[2]
        end_date = row[3]
        interval = row[4] or "1m"
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.json"

        # 尝试从缓存复制
        if cache.copy_to(symbol, data_src, interval, dest):
            logger.info("K线缓存命中: %s", symbol)
            continue

        # 检查数据源文件是否存在
        if not data_src or not Path(data_src).exists():
            logger.warning("K线数据源不存在: %s → %s", symbol, data_src)
            continue

        # 构建K线字典
        kline_dict = _build_kline_dict(
            data_src, symbol, interval, start_date, end_date
        )
        if kline_dict:
            cache.put(symbol, data_src, interval, kline_dict)  # 存入缓存
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info("K线已导出: %s → %s", symbol, dest.name)


def export_optuna_json(db_path: str, output_dir: str, run_id: int) -> None:
    """
    导出 Optuna 优化数据 JSON（含图表配置）
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        run_id: 运行ID
    """
    from .queries.optuna import get_optuna_data

    # 获取Optuna数据
    optuna_data = get_optuna_data(db_path, run_id)
    if not optuna_data:
        return

    # 查询study名称
    conn = sqlite3.connect(db_path)
    study_rows = conn.execute(
        "SELECT study_name FROM run_studies WHERE run_id=?", (run_id,)
    ).fetchall()
    conn.close()

    # 构建图表配置
    charts_spec = {}
    if study_rows:
        try:
            from .optimizer_report import build_optuna_spec
            study_db_url = f"sqlite:///{os.path.abspath(db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_rows[0][0])
        except Exception as e:
            logger.warning("Optuna chart spec 生成失败: %s", e)

    # 整合数据
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
    """
    导出全局导航数据 JSON（所有运行记录）
    
    Args:
        db_path: 数据库路径
        output_dir: 输出目录
    """
    conn = sqlite3.connect(db_path)
    # 查询所有运行记录
    rows = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs ORDER BY id DESC"
    ).fetchall()
    conn.close()

    # 格式化运行记录
    runs = [
        {
            "id": r[0], "strategy": r[1], "engine": r[2],
            "symbols": r[3], "status": r[4], "created": r[5],
        }
        for r in rows
    ]
    _write_json(output_dir, "data/nav.json", runs)


# ── 前端构建相关函数 ──────────────────────────────────────────────────


def build_frontend(output_dir: str) -> None:
    """
    检查 React 源码 hash，必要时触发 npm run build，并复制 vendor 文件
    
    Args:
        output_dir: 输出目录
    """
    web_dir = Path(__file__).parent / "web"  # 前端工程目录
    assets_dir = Path(output_dir) / "assets"  # 输出资源目录

    # 检查前端工程是否初始化
    if not (web_dir / "package.json").exists():
        logger.info("前端工程未初始化，跳过构建")
        return

    # 计算源码哈希值，用于判断是否需要重新构建
    src_hash = _compute_dir_hash(web_dir / "src") + _compute_dir_hash(
        web_dir / "public"
    )
    hash_file = assets_dir / ".build_hash"  # 哈希值存储文件

    # 检查是否需要重新构建
    needs_build = True
    if hash_file.exists() and hash_file.read_text().strip() == src_hash:
        logger.info("前端源码未变更，跳过构建")
        needs_build = False

    # 执行构建
    if needs_build:
        logger.info("开始前端构建...")
        _clean_old_bundles(assets_dir)  # 清理旧构建产物
        # 运行npm构建
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
        hash_file.write_text(src_hash)  # 保存新哈希值
        logger.info("前端构建完成")

def write_entry_html(output_dir: str) -> None:
    """
    生成 output/index.html 单入口文件

    【完全内联版本】将所有资源（JS、CSS、JSON数据）打包到单个 HTML 文件中，
    彻底避免 file:// 协议下的 CORS 问题，实现真正的离线浏览。

    内联内容：
    1. JS 代码 → <script> 标签内联
    2. CSS 样式 → <style> 标签内联（通过 JS 注入）
    3. JSON 数据 → window.__DATA__ 变量
    
    Args:
        output_dir: 输出目录
    """
    assets_dir = Path(output_dir) / "assets"

    # 查找构建产物
    js_file = _find_built_file(assets_dir, "index*.js")
    css_file = _find_built_file(assets_dir, "index*.css")

    # 如果没有找到JS文件，生成降级HTML
    if not js_file:
        logger.warning("未找到 Vite 构建产物，生成降级入口")
        _write_fallback_html(output_dir)
        return

    # 读取 JS 文件内容（内联到 HTML）
    js_content = (assets_dir / js_file).read_text(encoding="utf-8")
    # 转义 </script> 和 <\/script> 为 \x3C/script\x3E，避免 HTML 提前闭合
    # 转义 <script> 为 \x3Cscript\x3E，避免 HTML 解析器误解析
    js_content = js_content.replace("<script>", "\\x3Cscript\\x3E")
    js_content = js_content.replace("<\\/script>", "\\x3C/script\\x3E")
    js_content = js_content.replace("</script>", "\\x3C/script\\x3E")
    js_size = len(js_content.encode("utf-8")) / (1024 * 1024)  # 计算JS大小(MB)

    # 读取 CSS 文件内容（如果存在）
    css_content = ""
    if css_file:
        css_content = (assets_dir / css_file).read_text(encoding="utf-8")

    # 构建预加载脚本（JSON数据）
    preload_script = _build_preload_script(output_dir)

    # 生成完全内联的 HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
        '<title>量化回测监控</title>',
        # CSS 内联
        css_content and f'<style>{css_content}</style>' or '',
        '</head>',
        '<body>',
        '<div id="root"></div>',
        # JSON 数据预加载
        preload_script,
        # 主 JS 代码内联
        f'<script>{js_content}</script>',
        '</body>',
        '</html>',
    ]

    # 写入HTML文件
    out_path = Path(output_dir) / "index.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")

    # 计算并记录文件大小
    total_size = out_path.stat().st_size / (1024 * 1024)
    logger.info("入口 HTML 已生成: %s (JS: %.1f MiB, 总大小: %.1f MiB)", out_path, js_size, total_size)


def _build_preload_script(output_dir: str) -> str:
    """
    读取所有 JSON 数据文件，嵌入为 window.__DATA__ 对象

    【重要特性】数据预加载机制 - 保持此特性不变

    设计目的：
    1. 支持 file:// 协议访问（避免 CORS 问题）
    2. 实现离线浏览能力
    3. 提升页面加载性能（一次加载，无需多次网络请求）

    工作原理：
    1. 遍历 output 目录下的所有 JSON 文件
    2. 按规则生成数据键：
       - 公共数据: data/{filename}.json
       - 回测数据: r{runId}/data/{filename}.json
    3. 序列化为 JSON 字符串，嵌入到 <script> 标签中
    4. 前端通过 fetchJson() 从 window.__DATA__ 读取数据

    注意事项（修改此函数时必须保持）：
    1. 必须保持数据键格式与 web/src/data/loader.ts 中的 dataKey() 一致
    2. 必须将所有 JSON 数据嵌入到 HTML 中，不依赖网络请求
    3. 保持 JSON 序列化时 ensure_ascii=False（支持中文）
    4. 异常处理：单个文件加载失败不应中断整体流程

    Args:
        output_dir: 输出目录路径

    Returns:
        包含 window.__DATA__ 赋值的 script 标签字符串
    """
    root = Path(output_dir)
    data_map: dict[str, object] = {}  # 存储所有数据

    # 收集公共数据
    _collect_json(root / "data", "data", data_map)

    # 收集每个运行的数据
    for run_dir in sorted(root.glob("r*/data")):
        prefix = run_dir.parent.name + "/data"
        _collect_json(run_dir, prefix, data_map)

    # 如果没有数据，返回空对象
    if not data_map:
        return "<script>window.__DATA__ = {};</script>"

    # 序列化为JSON
    json_str = json.dumps(data_map, ensure_ascii=False, default=str)
    # 转义 </script> 和 <\/script> 为 \x3C/script\x3E，避免 HTML 提前闭合
    json_str = json_str.replace("<\\/script>", "\\x3C/script\\x3E")
    json_str = json_str.replace("</script>", "\\x3C/script\\x3E")
    mib = len(json_str.encode("utf-8")) / (1024 * 1024)  # 计算大小
    logger.info("预加载 %d 个数据文件 (%.1f MiB)", len(data_map), mib)

    return f"<script>window.__DATA__ = {json_str};</script>"


def _collect_json(
    data_dir: Path,
    prefix: str,
    data_map: dict[str, object],
) -> None:
    """
    收集指定目录下的所有JSON文件
    
    Args:
        data_dir: 数据目录
        prefix: 键前缀
        data_map: 数据字典，用于存储收集到的数据
    """
    for f in sorted(data_dir.glob("*.json")):
        key = f"{prefix}/{f.name}"  # 构建数据键
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data_map[key] = json.load(fh)
        except Exception as e:
            logger.warning("预加载失败 [%s]: %s", key, e)


# ── 内部辅助函数 ──────────────────────────────────────────────────


def _build_kline_dict(
    csv_path: str,
    symbol: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
) -> dict | None:
    """
    从 CSV 构建 K 线 JSON dict (daily resampled + raw 降采样)
    
    Args:
        csv_path: CSV文件路径
        symbol: 品种代码
        interval: K线周期
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        K线数据字典，失败返回None
    """
    try:
        df = pd.read_csv(csv_path)  # 读取CSV
        # 处理时间列
        if "datetime" not in df.columns:
            if "date" in df.columns:
                df["datetime"] = df["date"]
            else:
                return None

        df["datetime"] = pd.to_datetime(df["datetime"])

        # 按日期范围筛选
        if start_date:
            df = df[df["datetime"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["datetime"] <= pd.Timestamp(end_date)]

        if df.empty:
            return None

        # 重采样生成日线数据
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

        # 格式化日线数据
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

        # 处理原始数据（可能降采样）
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

        # 返回完整数据
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
    """
    将数据写入JSON文件
    
    Args:
        output_dir: 输出目录
        rel_path: 相对路径
        data: 要写入的数据
    """
    full_path = Path(output_dir) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)  # 创建目录
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _compute_dir_hash(directory: Path) -> str:
    """
    计算目录下所有文件的哈希值
    
    Args:
        directory: 目录路径
        
    Returns:
        MD5哈希字符串
    """
    if not directory.exists():
        return ""
    hasher = hashlib.md5()
    # 遍历所有文件并更新哈希
    for f in sorted(directory.rglob("*")):
        if f.is_file():
            hasher.update(f.read_bytes())
    return hasher.hexdigest()


def _find_built_file(directory: Path, glob_pattern: str) -> str | None:
    """
    查找最新的构建文件
    
    Args:
        directory: 目录路径
        glob_pattern: 匹配模式
        
    Returns:
        最新文件的文件名，没有找到返回None
    """
    import glob as _glob
    matches = sorted(
        _glob.glob(str(directory / glob_pattern)),
        key=lambda p: Path(p).stat().st_mtime,  # 按修改时间排序
        reverse=True,  # 最新的在前
    )
    return Path(matches[0]).name if matches else None


def _clean_old_bundles(assets_dir: Path) -> None:
    """
    清理旧的构建文件
    
    Args:
        assets_dir: 资源目录
    """
    for f in assets_dir.glob("index-*.js"):
        f.unlink()
    for f in assets_dir.glob("index-*.css"):
        f.unlink()


def _write_fallback_html(output_dir: str) -> None:
    """
    生成降级 HTML：不依赖前端构建，纯文本导航
    
    Args:
        output_dir: 输出目录
    """
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n'
        '<head><meta charset="UTF-8"><title>量化回测监控</title></head>\n'
        '<body>\n<h1>量化回测监控</h1>\n'
        '<p>前端资源未构建。请先执行 <code>cd report/web && npm run build</code></p>\n'
        '</body>\n</html>'
    )
    (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")