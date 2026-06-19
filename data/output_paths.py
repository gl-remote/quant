"""输出目录根路径

提供项目 output/ 目录的根路径抽象，所有模块通过此函数获取输出根，
不在代码中硬编码 `"output"` 字符串。

将来如果切换到云存储（OSS/S3），只需修改此函数的实现，
其余所有消费者无需改动。
"""

from __future__ import annotations

from pathlib import Path

# 从本文件位置推算项目根（data/output_paths.py → data/ → 项目根/）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def output_root() -> Path:
    """返回项目输出根目录: <项目根>/output/"""
    return _PROJECT_ROOT / "output"
