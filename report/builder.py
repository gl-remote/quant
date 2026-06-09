"""
报告生成编排模块 — export JSON → 数据写入 → 前端构建

将 Jinja2 模板渲染替换为 JSON 数据导出 + React 前端构建。
一次 build_all() = 全部 JSON 导出 + 增量前端构建 + 入口 HTML 写入。
"""

from __future__ import annotations

import hashlib  # 用于计算文件哈希
import json  # 用于JSON序列化
import os  # 用于操作系统相关操作
import subprocess  # 用于执行子进程
from collections.abc import Callable
from pathlib import Path  # 用于路径操作

from loguru import logger  # 用于日志记录

from data import DataManager  # 导入数据管理器

from .cache import BuildCache  # 导入统一缓存管理器
from .writer import (  # 导入数据写入模块
    export_backtests_json,
    export_equity_json,
    export_kline_json,
    export_optuna_json,
    export_run_json,
    export_summary_json,
    export_trades_json,
    write_nav_json,
)
from .writer.json_writer import _build_kline_dict

_data_manager: DataManager | None = None


def get_data_manager() -> DataManager:
    """获取数据管理器实例（延迟初始化）"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


# ── 公开 API ──────────────────────────────────────────────────


def build_all(output_dir: str, run_id: int, incremental: bool = True) -> None:
    """回测完成后统一入口（支持增量构建）

    执行步骤：
    1. 增量导出 JSON 数据文件（基于数据指纹）
    2. 增量构建 React 前端（基于源码哈希）
    3. 写入入口 HTML（仅在有数据变更时）
    """
    import time

    start_time = time.time()
    success_count = 0
    fail_count = 0
    skip_count = 0
    failed_tasks: list[tuple[str, str]] = []

    logger.info("开始构建报告: run_id=%d, output_dir=%s, incremental=%s", run_id, output_dir, incremental)

    dm = get_data_manager()
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
        logger.error("✗ 构建前端失败: %s", str(e))
        fail_count += 1
        failed_tasks.append(("构建前端", str(e)))

    # 写入入口 HTML（仅在有数据变更时）
    if has_data_change:
        try:
            write_entry_html(output_dir)
            logger.info("✓ 写入入口HTML完成")
            success_count += 1
        except Exception as e:
            logger.error("✗ 写入入口HTML失败: %s", str(e))
            fail_count += 1
            failed_tasks.append(("写入入口HTML", str(e)))
    else:
        logger.info("○ 数据未变更，跳过写入入口HTML")

    duration = time.time() - start_time
    logger.info("报告构建结束: 成功=%d, 跳过=%d, 失败=%d, 耗时=%.2fs", success_count, skip_count, fail_count, duration)

    if failed_tasks:
        logger.warning("失败任务列表:")
        for task_name, error in failed_tasks:
            logger.warning("  - %s: %s", task_name, error)


# ── 数据导出任务调度 ───────────────────────────────────────


def _run_data_exports(
    cache: BuildCache | None,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> tuple[int, int]:
    """执行所有数据导出任务，返回 (实际导出数, 跳过数)

    8 个任务描述符: (类型, 指纹收集器, 直接导出函数)
    - 前 3 个 + optuna: 通用增量检查
    - equity/kline/trades/nav: 自定义增量检查
    """
    # 延迟构造: 必须在所有辅助函数定义之后再构建
    export_tasks: list[tuple[str, Callable[[DataManager, int], object], Callable[[str, int], object]]] = [
        ("run", lambda dm_, rid: dm_.get_run_info(rid), lambda out, rid: export_run_json(out, rid)),
        ("summary", lambda dm_, rid: dm_.get_run_summary(rid), lambda out, rid: export_summary_json(out, rid)),
        (
            "backtests",
            lambda dm_, rid: dm_.get_backtests_for_run(rid),
            lambda out, rid: export_backtests_json(out, rid),
        ),
        ("equity", _collect_equity_fingerprint, lambda out, rid: export_equity_json(out, rid)),
        ("kline", _collect_kline_fingerprint, lambda out, rid: export_kline_json(out, rid)),
        ("optuna", lambda dm_, rid: dm_.get_optuna_data(rid), lambda out, rid: export_optuna_json(out, rid)),
        ("trades", _collect_trades_fingerprint, lambda out, rid: export_trades_json(out, rid)),
        ("nav", lambda dm_, _rid: dm_.get_all_runs(), lambda out, _rid: write_nav_json(out)),
    ]
    custom_types = {"equity", "kline", "trades", "nav"}

    exported = 0
    skipped = 0
    for data_type, getter, exporter in export_tasks:
        if cache and data_type in custom_types:
            # 自定义增量检查（kline 有转换逻辑，trades/equity 有状态依赖）
            executed = _run_custom_incremental(cache, dm, output_dir, run_id, data_type, getter, exporter)
        elif cache:
            # 通用增量检查: 基于指纹/缓存哈希对比
            # 用默认参数 g=getter 捕获当前循环值，避免 B023 闭包陷阱
            executed = _export_with_incremental(
                cache, dm, output_dir, run_id, data_type, lambda g=getter: g(dm, run_id)
            )
        else:
            # 全量导出: 不检查缓存, 直接写入
            exporter(output_dir, run_id)
            logger.info("→ 导出 %s", data_type)
            executed = True

        if executed:
            exported += 1
        else:
            skipped += 1

    return exported, skipped


def _run_custom_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
    data_type: str,
    _getter: Callable[[DataManager, int], object],
    _exporter: Callable[[str, int], object],
) -> bool:
    """对 kline / trades / equity / nav 使用自定义增量逻辑

    注: _getter/_exporter 参数保留为占位, 供通用调度器传入, 但实际实现已内联。
    """
    if data_type == "equity":
        return _export_equity_with_incremental(cache, dm, output_dir, run_id)
    if data_type == "kline":
        return _export_kline_with_incremental(cache, dm, output_dir, run_id)
    if data_type == "trades":
        return _export_trades_with_incremental(cache, dm, output_dir, run_id)
    if data_type == "nav":
        return _export_nav_with_incremental(cache, dm, output_dir)
    return False


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
        result[symbol] = len(list(dm.query_trades(int(s_id))))
    return result


def _export_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
    data_type: str,
    data_getter: Callable[[], object],
) -> bool:
    """
    使用增量检查导出数据

    Returns:
        bool: 数据是否实际执行了导出
    """
    new_data = data_getter()
    if cache.needs_update(data_type, run_id, new_data):
        logger.info("→ 导出 %s（数据已变更）", data_type)
        _dispatch_export(data_type, output_dir, run_id)
        cache.update_fingerprint(data_type, run_id, new_data)
        return True
    else:
        logger.info("○ 跳过 %s（数据未变更）", data_type)
        return False


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
        export_equity_json(output_dir, run_id)
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
    """导出 kline 数据（使用 KlineCache 复用转换结果）"""
    from .cache import KlineCache

    summary = dm.get_run_summary(run_id)
    kline_changed = False
    cache_instance = KlineCache(output_dir)

    for s in summary:
        if not s.get("id"):
            continue
        symbol = str(s["symbol"])
        data_src = str(s.get("data_src", ""))
        start_date = str(s.get("start_date")) if s.get("start_date") else None
        end_date = str(s.get("end_date")) if s.get("end_date") else None
        interval = str(s.get("kline_interval") or "1m")
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.{interval}.json"

        if not data_src:
            continue

        # 尝试从缓存复制
        if cache_instance.copy_to(symbol, data_src, interval, dest):
            logger.debug("K线缓存命中: %s", symbol)
            continue

        # 缓存未命中，需要转换
        if not Path(data_src).exists():
            logger.warning("K线数据源不存在: %s → %s", symbol, data_src)
            continue

        kline_dict = _build_kline_dict(data_src, symbol, interval, start_date, end_date)
        if kline_dict:
            cache_instance.put(symbol, data_src, interval, kline_dict)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info("→ K线已导出: %s", symbol)
            kline_changed = True

    if kline_changed:
        cache.update_fingerprint("kline", run_id, {"symbols": len(summary)})
    return kline_changed


def _export_trades_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 trades 数据（带增量检查）"""
    summary = dm.get_run_summary(run_id)
    trades_data: dict[str, list[dict[str, object]]] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        symbol = str(s.get("symbol", ""))
        trades = dm.query_trades(int(s_id))
        trades_data[symbol] = [_format_trade_record(t) for t in trades]

    if cache.needs_update("trades", run_id, trades_data):
        logger.info("→ 导出 trades（数据已变更）")
        export_trades_json(output_dir, run_id)
        cache.update_fingerprint("trades", run_id, trades_data)
        return True
    logger.info("○ 跳过 trades（数据未变更）")
    return False


def _format_trade_record(t: object) -> dict[str, object]:
    """格式化单条交易记录，清理 direction/offset 字符串"""
    direction = getattr(t, "direction", "")
    if "." in str(direction):
        direction = str(direction).split(".")[-1]

    offset = getattr(t, "offset", "")
    if "." in str(offset):
        offset = str(offset).split(".")[-1]

    return {
        "datetime": getattr(t, "datetime", None),
        "symbol": getattr(t, "symbol", None),
        "direction": direction,
        "offset": offset,
        "open_price": getattr(t, "open_price", None),
        "close_price": getattr(t, "close_price", None),
        "quantity": getattr(t, "quantity", None),
        "pnl": getattr(t, "pnl", None),
        "commission": getattr(t, "commission", None),
    }


def _export_nav_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
) -> bool:
    """导出 nav 数据（带增量检查）"""
    runs = dm.get_all_runs()
    if cache.needs_update("nav", None, runs):
        logger.info("→ 导出 nav（数据已变更）")
        write_nav_json(output_dir)
        cache.update_fingerprint("nav", None, runs)
        return True
    logger.info("○ 跳过 nav（数据未变更）")
    return False


def _dispatch_export(data_type: str, output_dir: str, run_id: int) -> None:
    """根据数据类型分发导出任务"""
    if data_type == "run":
        export_run_json(output_dir, run_id)
    elif data_type == "summary":
        export_summary_json(output_dir, run_id)
    elif data_type == "backtests":
        export_backtests_json(output_dir, run_id)
    elif data_type == "equity":
        export_equity_json(output_dir, run_id)
    elif data_type == "kline":
        export_kline_json(output_dir, run_id)
    elif data_type == "optuna":
        export_optuna_json(output_dir, run_id)
    elif data_type == "trades":
        export_trades_json(output_dir, run_id)
    elif data_type == "nav":
        write_nav_json(output_dir)


# ── 前端构建相关函数 ──────────────────────────────────────────────────


def build_frontend(output_dir: str) -> None:
    """
    检查 React 源码 hash，必要时触发 npm run build

    使用 BuildCache 统一管理前端构建缓存，支持增量构建。

    Args:
        output_dir: 输出目录
    """
    web_dir = Path(__file__).parent / "web"  # 前端工程目录
    assets_dir = Path(output_dir) / "assets"  # 输出资源目录

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

    【完全内联版本】将所有资源（JS、CSS、JSON数据）打包到单个 HTML 文件中，
    彻底避免 file:// 协议下的 CORS 问题，实现真正的离线浏览。
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
    js_content = _read_and_escape_js(assets_dir / js_file)
    js_size = len(js_content.encode("utf-8")) / (1024 * 1024)

    # 读取 CSS 文件内容（如果存在）
    css_content = (assets_dir / css_file).read_text(encoding="utf-8") if css_file else ""

    # 构建预加载脚本（JSON数据）
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
    logger.info("入口 HTML 已生成: %s (JS: %.1f MiB, 总大小: %.1f MiB)", out_path, js_size, total_size)


def _read_and_escape_js(path: Path) -> str:
    """读取 JS 文件并转义可能导致 HTML 解析问题的标记"""
    js_content = path.read_text(encoding="utf-8")
    # 转义 </script> 和 <\/script> 为 \x3C/script\x3E，避免 HTML 提前闭合
    # 转义 <script> 为 \x3Cscript\x3E，避免 HTML 解析器误解析
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

    注意事项（修改此函数时必须保持）：
    1. 必须保持数据键格式与 web/src/data/loader.ts 中的 dataKey() 一致
    2. 必须将所有 JSON 数据嵌入到 HTML 中，不依赖网络请求
    3. 保持 JSON 序列化时 ensure_ascii=False（支持中文）
    4. 异常处理：单个文件加载失败不应中断整体流程
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
    logger.info("预加载 %d 个数据文件 (%.1f MiB)", len(data_map), mib)
    return f"<script>window.__DATA__ = {json_str};</script>"


def _collect_json(data_dir: Path, prefix: str, data_map: dict[str, object]) -> None:
    """收集指定目录下的所有JSON文件"""
    for f in sorted(data_dir.glob("*.json")):
        key = f"{prefix}/{f.name}"
        try:
            with open(f, encoding="utf-8") as fh:
                data_map[key] = json.load(fh)
        except Exception as e:
            logger.warning("预加载失败 [%s]: %s", key, e)


# ── 内部辅助函数 ──────────────────────────────────────────────────


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
        "<body>\n<h1>量化回测监控</h1>\n"
        "<p>前端资源未构建。请先执行 <code>cd report/web && npm run build</code></p>\n"
        "</body>\n</html>"
    )
    (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")
