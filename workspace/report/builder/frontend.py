"""前端构建

检查 React 源码 hash，必要时触发 npm run build，产出到 report assets 目录。

本模块不感知数据内容，只负责前端 bundle 的构建与清理。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from loguru import logger

from ..cache import BuildCache


def build_frontend(output_dir: str) -> None:
    """检查 React 源码 hash，必要时触发 npm run build"""
    web_dir = Path(__file__).parent.parent / "web"
    assets_dir = Path(output_dir) / "assets"

    if not (web_dir / "package.json").exists():
        logger.info("前端工程未初始化，跳过构建")
        return

    cache = BuildCache()

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


def _clean_old_bundles(assets_dir: Path) -> None:
    """清理旧的构建文件"""
    for f in assets_dir.glob("index-*.js"):
        f.unlink()
    for f in assets_dir.glob("index-*.css"):
        f.unlink()
