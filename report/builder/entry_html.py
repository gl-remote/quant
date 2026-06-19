"""入口 HTML 打包

将前端 bundle（JS/CSS）与所有 JSON 数据文件内联到单个 output/index.html，
避免 file:// 协议下的 CORS 问题，支持离线浏览。

本模块只读文件系统快照，不生成任何数据；调用方须保证调用前所有 JSON 已就绪。
"""

from __future__ import annotations

import glob as _glob
import json
from pathlib import Path

from loguru import logger


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


def _find_built_file(directory: Path, glob_pattern: str) -> str | None:
    """查找最新的构建文件"""
    matches = sorted(
        _glob.glob(str(directory / glob_pattern)),
        key=lambda p: Path(p).stat().st_mtime,
        reverse=True,
    )
    return Path(matches[0]).name if matches else None


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
