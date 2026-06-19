"""报告生成编排模块

thin 编排层，负责：
1. 统一创建 DataManager 实例
2. 增量检查（通过 BuildCache 管理数据指纹）
3. 调用 report/writer 层的 export_* 函数写出 JSON
4. 构建 React 前端
5. 生成入口 HTML

本模块不做任何具体的"数据格式化/写文件"逻辑，只负责调度。
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from data import DataManager

from .cache import BuildCache
from .writer import (
    export_backtests_json,
    export_equity_json,
    export_kline_json,
    export_optuna_json,
    export_run_json,
    export_summary_json,
    export_trades_json,
    write_nav_json,
)

# ── 公开 API ─────────────────────────────────────────────────────────────


def build_all(output_dir: str, run_id: int, incremental: bool = True) -> None:
    """回测完成后统一入口，生成完整报告

    执行步骤：
    1. 增量导出 JSON 数据文件（基于数据指纹对比）
    2. 构建 React 前端
    3. 写入入口 HTML（仅在有数据变更时）
    """
    import time

    start_time = time.time()
    success_count = 0
    skip_count = 0
    failed_tasks: list[tuple[str, str]] = []

    logger.info("开始构建报告: run_id={}, output_dir={}, incremental={}", run_id, output_dir, incremental)

    dm = DataManager()
    cache = BuildCache(output_dir) if incremental else None

    exported, skipped = _run_data_exports(cache, dm, output_dir, run_id)
    success_count += exported
    skip_count += skipped
    has_data_change = exported > 0 or not incremental

    # 构建前端
    try:
        build_frontend(output_dir)
        logger.info("✓ 构建前端完成")
        success_count += 1
    except Exception as e:
        logger.error("✗ 构建前端失败: {}", str(e))
        failed_tasks.append(("构建前端", str(e)))

    # 写入入口 HTML
    if has_data_change:
        try:
            write_entry_html(output_dir)
            logger.info("✓ 写入入口HTML完成")
            success_count += 1
        except Exception as e:
            logger.error("✗ 写入入口HTML失败: {}", str(e))
            failed_tasks.append(("写入入口HTML", str(e)))
    else:
        logger.info("○ 数据未变更，跳过写入入口HTML")

    duration = time.time() - start_time
    logger.info(
        "报告构建结束: 成功={}, 跳过={}, 失败={}, 耗时={:.2f}s", success_count, skip_count, len(failed_tasks), duration
    )

    if failed_tasks:
        logger.warning("失败任务列表:")
        for task_name, error in failed_tasks:
            logger.warning("  - {}: {}", task_name, error)


# ── 数据导出任务调度 ────────────────────────────────────────────────────


def _run_data_exports(
    cache: BuildCache | None,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> tuple[int, int]:
    """执行所有数据导出任务，返回 (实际导出数, 跳过数)

    任务分两类：
    - 通用类型（run/summary/backtests/optuna）: 基于指纹的增量检查
    - 自定义类型（equity/kline/trades/nav）: 有特殊的增量检查逻辑
    """
    # 任务描述符: (类型名, 指纹收集函数, 全量导出函数)
    export_tasks: list[tuple[str, Callable[[DataManager, int], object], Callable[..., object]]] = [
        ("run", lambda d, rid: d.get_run_info(rid), lambda rid, d: export_run_json(rid, d)),
        ("summary", lambda d, rid: d.get_run_summary(rid), lambda rid, d: export_summary_json(rid, d)),
        (
            "backtests",
            lambda d, rid: d.get_backtests_for_run(rid),
            lambda rid, d: export_backtests_json(rid, d),
        ),
        ("equity", _collect_equity_fingerprint, lambda rid, d: export_equity_json(rid, d)),
        ("kline", _collect_kline_fingerprint, lambda rid, d: export_kline_json(rid, d)),
        ("optuna", lambda d, rid: d.get_optuna_data(rid), lambda rid, d: export_optuna_json(rid, d)),
        ("trades", _collect_trades_fingerprint, lambda rid, d: export_trades_json(rid, d)),
        ("nav", lambda d, _rid: d.get_all_runs(), lambda _rid, d: write_nav_json(d)),
    ]

    exported = 0
    skipped = 0

    for data_type, getter, exporter in export_tasks:
        if cache and data_type == "kline":
            # K线有独立的 KlineCache，直接调用自定义增量导出
            executed = _export_kline_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "equity":
            executed = _export_equity_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "trades":
            executed = _export_trades_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "nav":
            executed = _export_nav_with_incremental(cache, dm, output_dir)
        elif cache:
            # 通用增量检查: 基于指纹/缓存哈希对比
            new_data = getter(dm, run_id)
            if cache.needs_update(data_type, run_id, new_data):
                exporter(run_id, dm)
                cache.update_fingerprint(data_type, run_id, new_data)
                logger.info("→ 导出 {}（数据已变更）", data_type)
                executed = True
            else:
                logger.info("○ 跳过 {}（数据未变更）", data_type)
                executed = False
        else:
            # 全量导出: 不检查缓存，直接写入
            exporter(run_id, dm)
            logger.info("→ 导出 {}", data_type)
            executed = True

        if executed:
            exported += 1
        else:
            skipped += 1

    return exported, skipped


# ── 指纹收集函数 ─────────────────────────────────────────────────────────


def _collect_equity_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 equity 指纹用于增量检查"""
    summary = dm.get_run_summary(run_id)
    result: dict[str, object] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        equity = dm.get_equity_data(int(s_id))  # type: ignore[call-overload]
        if equity:
            result[str(s["symbol"])] = equity
    return result


def _collect_kline_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 kline 指纹用于增量检查（仅记录 symbol+interval 级元数据）"""
    summary = dm.get_run_summary(run_id)
    return {str(s["symbol"]): s.get("data_src") for s in summary if s.get("id")}


def _collect_trades_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 trades 指纹用于增量检查"""
    summary = dm.get_run_summary(run_id)
    result: dict[str, object] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        symbol = str(s.get("symbol", ""))
        result[symbol] = len(list(dm.query_trades(int(str(s_id)))))
    return result


# ── 自定义增量检查 ─────────────────────────────────────────────────────


def _export_equity_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 equity 数据（带增量检查）"""
    equity_data = _collect_equity_fingerprint(dm, run_id)

    if cache.needs_update("equity", run_id, equity_data):
        logger.info("→ 导出 equity（数据已变更）")
        export_equity_json(run_id, dm)
        cache.update_fingerprint("equity", run_id, equity_data)
        return True
    logger.info("○ 跳过 equity（数据未变更）")
    return False


def _export_kline_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 K 线数据（带增量检查）"""
    kline_data = _collect_kline_fingerprint(dm, run_id)

    if cache.needs_update("kline", run_id, kline_data):
        logger.info("→ 导出 kline（数据已变更）")
        has_changes = export_kline_json(run_id, dm)
        cache.update_fingerprint("kline", run_id, kline_data)
        return has_changes
    logger.info("○ 跳过 kline（数据未变更）")
    return False


def _export_trades_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 trades 数据（带增量检查）"""
    trades_data = _collect_trades_fingerprint(dm, run_id)

    if cache.needs_update("trades", run_id, trades_data):
        logger.info("→ 导出 trades（数据已变更）")
        export_trades_json(run_id, dm)
        cache.update_fingerprint("trades", run_id, trades_data)
        return True
    logger.info("○ 跳过 trades（数据未变更）")
    return False


def _export_nav_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
) -> bool:
    """导出 nav 数据（带增量检查）"""
    runs = dm.get_all_runs()
    if cache.needs_update("nav", None, runs):
        logger.info("→ 导出 nav（数据已变更）")
        write_nav_json(dm)
        cache.update_fingerprint("nav", None, runs)
        return True
    logger.info("○ 跳过 nav（数据未变更）")
    return False


# ── 前端构建 ───────────────────────────────────────────────────────────


def build_frontend(output_dir: str) -> None:
    """检查 React 源码 hash，必要时触发 npm run build"""
    web_dir = Path(__file__).parent / "web"
    assets_dir = Path(output_dir) / "assets"

    if not (web_dir / "package.json").exists():
        logger.info("前端工程未初始化，跳过构建")
        return

    cache = BuildCache(output_dir)

    if not cache.needs_frontend_rebuild(web_dir):
        logger.info("前端源码未变更，跳过构建")
        return

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
    cache.set_frontend_hash(cache.compute_dir_hash(web_dir / "src") + cache.compute_dir_hash(web_dir / "public"))
    logger.info("前端构建完成")


def write_entry_html(output_dir: str) -> None:
    """生成 output/index.html 单入口文件

    完全内联版本：将所有资源（JS、CSS、JSON 数据）打包到单个 HTML 文件，
    避免 file:// 协议下的 CORS 问题。
    """
    assets_dir = Path(output_dir) / "assets"

    # 查找构建产物
    js_file = _find_built_file(assets_dir, "index*.js")
    css_file = _find_built_file(assets_dir, "index*.css")

    if not js_file:
        logger.warning("未找到 Vite 构建产物，生成降级入口")
        _write_fallback_html(output_dir)
        return

    # 读取 JS 文件内容（内联到 HTML）
    js_content = _read_and_escape_js(assets_dir / js_file)
    js_size = len(js_content.encode("utf-8")) / (1024 * 1024)

    # 读取 CSS 文件内容
    css_content = (assets_dir / css_file).read_text(encoding="utf-8") if css_file else ""

    # 构建预加载脚本（JSON 数据内联）
    preload_script = _build_preload_script(output_dir)

    # 生成完全内联的 HTML
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">',
        "<title>量化回测监控</title>",
        css_content and f"<style>{css_content}</style>" or "",
        "</head>",
        "<body>",
        '<div id="root"></div>',
        preload_script,
        f"<script>{js_content}</script>",
        "</body>",
        "</html>",
    ]

    out_path = Path(output_dir) / "index.html"
    out_path.write_text("\n".join(html_parts), encoding="utf-8")
    total_size = out_path.stat().st_size / (1024 * 1024)
    logger.info("入口 HTML 已生成: {} (JS: {:.1f} MiB, 总大小: {:.1f} MiB)", out_path, js_size, total_size)


def _read_and_escape_js(path: Path) -> str:
    """读取 JS 文件并转义可能导致 HTML 解析问题的标记"""
    js_content = path.read_text(encoding="utf-8")
    js_content = js_content.replace("<script>", "\\x3Cscript\\x3E")
    js_content = js_content.replace("<\\/script>", "\\x3C/script\\x3E")
    js_content = js_content.replace("</script>", "\\x3C/script\\x3E")
    return js_content


def _build_preload_script(output_dir: str) -> str:
    """读取所有 JSON 数据文件，嵌入为 window.__DATA__ 对象

    设计目的：
    1. 支持 file:// 协议访问（避免 CORS 问题）
    2. 实现离线浏览能力
    3. 提升页面加载性能（一次加载，无需多次网络请求）
    """
    root = Path(output_dir)
    data_map: dict[str, object] = {}

    # 收集公共数据
    _collect_json(root / "data", "data", data_map)

    # 收集每个运行的数据
    for run_dir in sorted(root.glob("r*/data")):
        prefix = run_dir.parent.name + "/data"
        _collect_json(run_dir, prefix, data_map)

    if not data_map:
        return "<script>window.__DATA__ = {};</script>"

    json_str = json.dumps(data_map, ensure_ascii=False, default=str)
    json_str = json_str.replace("<\\/script>", "\\x3C/script\\x3E")
    json_str = json_str.replace("</script>", "\\x3C/script\\x3E")
    mib = len(json_str.encode("utf-8")) / (1024 * 1024)
    logger.info("预加载 {} 个数据文件 ({:.1f} MiB)", len(data_map), mib)
    return f"<script>window.__DATA__ = {json_str};</script>"


def _collect_json(data_dir: Path, prefix: str, data_map: dict[str, object]) -> None:
    """收集指定目录下的所有 JSON 文件"""
    for f in sorted(data_dir.glob("*.json")):
        key = f"{prefix}/{f.name}"
        try:
            with open(f, encoding="utf-8") as fh:
                data_map[key] = json.load(fh)
        except Exception as e:
            logger.warning("预加载失败 [{}]: {}", key, e)


# ── 辅助函数 ───────────────────────────────────────────────────────────


def _find_built_file(directory: Path, glob_pattern: str) -> str | None:
    """查找最新的构建文件"""
    import glob as _glob

    matches = sorted(
        _glob.glob(str(directory / glob_pattern)),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    return Path(matches[0]).name if matches else None


def _clean_old_bundles(assets_dir: Path) -> None:
    """清理旧的构建文件"""
    for f in assets_dir.glob("index-*.js"):
        f.unlink()
    for f in assets_dir.glob("index-*.css"):
        f.unlink()


def _write_fallback_html(output_dir: str) -> None:
    """生成降级 HTML：不依赖前端构建，纯文本导航"""
    html = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n'
        '<head><meta charset="UTF-8"><title>量化回测监控</title></head>\n'
        "<body>\n<h1>量化回测监控</h1>\n"
        "<p>前端资源未构建。请先执行 <code>cd report/web && npm run build</code></p>\n"
        "</body>\n</html>"
    )
    (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")
