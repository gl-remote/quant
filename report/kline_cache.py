# -*- coding: utf-8 -*-
"""K 线数据转换缓存

以 (symbol, csv_path, csv_mtime) 的 md5 为 key，
将 pandas CSV → JSON dict 的转换结果持久化缓存。
多个 run 共用相同 CSV 源时，转换只发生一次。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class KlineCache:
    """K 线数据转换缓存

    用法:
        cache = KlineCache("output")
        data = cache.get("DCE.m2601", "/path/to/data.csv", "1m")
        if data is None:
            data = build_kline_dict(...)
            cache.put("DCE.m2601", "/path/to/data.csv", "1m", data)
        cache.copy_to("DCE.m2601", "/path/to/data.csv", "1m", dest_path)
    """

    def __init__(self, output_dir: str = "output"):
        self._cache_dir = Path(output_dir) / ".kline_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, symbol: str, csv_path: str, interval: str) -> str:
        mtime = str(os.path.getmtime(csv_path)) if os.path.exists(csv_path) else "0"
        raw = f"{symbol}|{csv_path}|{interval}|{mtime}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, symbol: str, csv_path: str, interval: str = "1m") -> dict | None:
        key = self._cache_key(symbol, csv_path, interval)
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def put(self, symbol: str, csv_path: str, interval: str, data: dict) -> None:
        key = self._cache_key(symbol, csv_path, interval)
        cache_file = self._cache_dir / f"{key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def copy_to(
        self, symbol: str, csv_path: str, interval: str, dest: Path
    ) -> bool:
        """将缓存文件复制到目标路径，成功返回 True"""
        data = self.get(symbol, csv_path, interval)
        if data is None:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        return True

    def clear(self) -> None:
        """清空所有缓存"""
        import shutil
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("K线缓存已清空")