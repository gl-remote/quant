"""增量构建缓存管理器

统一管理报告构建过程中的各类缓存：
- 数据指纹（JSON 数据哈希）
- 前端构建哈希（源码哈希）
- K线转换缓存（复用 KlineCache）

目录结构：
    output/.build_cache/
    ├── fingerprints/         # 数据指纹
    │   ├── run_{run_id}.json
    │   ├── summary_{run_id}.json
    │   ├── backtests_{run_id}.json
    │   ├── equity_{run_id}.json
    │   └── optuna_{run_id}.json
    ├── frontend_hash        # 前端源码哈希
    └── kline/              # K线缓存（由 KlineCache 管理）
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from loguru import logger

from data.output_paths import output_root


class BuildCache:
    """统一增量构建缓存管理器"""

    FINGERPRINT_DIR = "fingerprints"
    FRONTEND_HASH_FILE = "frontend_hash"

    def __init__(self, output_dir: str = ""):
        root = Path(output_dir) if output_dir else output_root()
        self._output_dir = root
        self._cache_dir = root / ".build_cache"
        self._fingerprint_dir = self._cache_dir / self.FINGERPRINT_DIR
        self._ensure_cache_dirs()

    def _ensure_cache_dirs(self) -> None:
        """确保缓存目录存在"""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._fingerprint_dir.mkdir(parents=True, exist_ok=True)

    def _compute_fingerprint(self, data: Any) -> str:
        """计算数据的 MD5 指纹"""
        if data is None:
            return hashlib.md5(b"").hexdigest()

        try:
            content = json.dumps(data, sort_keys=True, default=str)
        except (TypeError, ValueError):
            content = str(data)
        return hashlib.md5(content.encode()).hexdigest()

    def _get_fingerprint_path(self, data_type: str, run_id: int | None = None) -> Path:
        """获取指纹文件路径"""
        if run_id is not None:
            return self._fingerprint_dir / f"{data_type}_{run_id}.json"
        return self._fingerprint_dir / f"{data_type}.json"

    def needs_update(self, data_type: str, run_id: int | None, new_data: Any) -> bool:
        """
        检查数据是否需要更新

        Args:
            data_type: 数据类型（如 "run", "summary", "backtests"）
            run_id: 运行ID（可选）
            new_data: 新的数据内容

        Returns:
            bool: True 表示需要更新，False 表示可以跳过
        """
        fingerprint_path = self._get_fingerprint_path(data_type, run_id)

        if not fingerprint_path.exists():
            logger.debug("指纹文件不存在，需要更新: {}", fingerprint_path.name)
            return True

        try:
            stored = json.loads(fingerprint_path.read_text(encoding="utf-8"))
            stored_fingerprint = stored.get("fingerprint", "")
            new_fingerprint = self._compute_fingerprint(new_data)

            needs_update = stored_fingerprint != new_fingerprint
            if needs_update:
                logger.debug("数据变更检测到，需要更新: {}", fingerprint_path.name)
            else:
                logger.debug("数据未变更，跳过: {}", fingerprint_path.name)
            return bool(needs_update)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("指纹文件读取失败，需要更新: {} - {}", fingerprint_path.name, e)
            return True

    def update_fingerprint(self, data_type: str, run_id: int | None, data: Any) -> None:
        """
        更新数据指纹

        Args:
            data_type: 数据类型
            run_id: 运行ID（可选）
            data: 数据内容
        """
        fingerprint_path = self._get_fingerprint_path(data_type, run_id)
        fingerprint = self._compute_fingerprint(data)

        fingerprint_info = {
            "fingerprint": fingerprint,
            "updated_at": self._get_timestamp(),
            "data_type": data_type,
            "run_id": run_id,
        }

        try:
            with open(fingerprint_path, "w", encoding="utf-8") as f:
                json.dump(fingerprint_info, f, ensure_ascii=False, indent=2)
            logger.debug("指纹已更新: {}", fingerprint_path.name)
        except OSError as e:
            logger.error("指纹更新失败: {} - {}", fingerprint_path.name, e)

    def get_frontend_hash(self) -> str | None:
        """获取前端源码哈希"""
        hash_file = self._cache_dir / self.FRONTEND_HASH_FILE
        if not hash_file.exists():
            return None
        return hash_file.read_text(encoding="utf-8").strip()

    def set_frontend_hash(self, src_hash: str) -> None:
        """设置前端源码哈希"""
        hash_file = self._cache_dir / self.FRONTEND_HASH_FILE
        hash_file.write_text(src_hash, encoding="utf-8")

    def needs_frontend_rebuild(self, web_dir: Path) -> bool:
        """
        检查前端是否需要重新构建

        Args:
            web_dir: 前端工程目录

        Returns:
            bool: True 表示需要重新构建
        """
        src_hash = self.compute_dir_hash(web_dir / "src") + self.compute_dir_hash(web_dir / "public")
        stored_hash = self.get_frontend_hash()

        if stored_hash is None or stored_hash != src_hash:
            logger.debug("前端源码变更，标记需要重建")
            return True

        logger.debug("前端源码未变更，跳过构建")
        return False

    def compute_dir_hash(self, directory: Path) -> str:
        """
        计算目录的哈希值（基于文件内容）

        Args:
            directory: 目录路径

        Returns:
            str: 目录哈希值
        """
        if not directory.exists():
            return ""

        files_content = []
        for root, _, files in os.walk(directory):
            for filename in sorted(files):
                if filename.startswith("."):
                    continue
                filepath = Path(root) / filename
                try:
                    content = filepath.read_bytes()
                    files_content.append(f"{filename}:{len(content)}")
                except OSError:
                    pass

        content_str = "|".join(files_content)
        return hashlib.md5(content_str.encode()).hexdigest()

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def clear(self) -> None:
        """清空所有缓存"""
        import shutil

        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)
            self._ensure_cache_dirs()
            logger.info("构建缓存已清空")

    def clear_fingerprints(self, run_id: int | None = None) -> None:
        """
        清空指定 run_id 的指纹缓存

        Args:
            run_id: 运行ID，为 None 时清空所有指纹
        """
        if run_id is not None:
            for fp in self._fingerprint_dir.glob(f"*_{run_id}.json"):
                fp.unlink()
                logger.debug("已删除指纹: {}", fp.name)
        else:
            for fp in self._fingerprint_dir.glob("*.json"):
                fp.unlink()
            logger.debug("已删除所有指纹")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            dict: 缓存统计信息
        """
        fingerprint_files = list(self._fingerprint_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in self._fingerprint_dir.glob("*.json"))

        run_ids = set()
        for fp in fingerprint_files:
            name = fp.stem
            parts = name.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                run_ids.add(int(parts[1]))

        return {
            "cache_dir": str(self._cache_dir),
            "fingerprint_count": len(fingerprint_files),
            "total_size_bytes": total_size,
            "run_ids": sorted(run_ids),
        }
