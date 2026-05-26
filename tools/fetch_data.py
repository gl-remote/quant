#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键拉取近期适配数据 — 默认用 tqsdk 导出多品种 1m 分钟线

用法:
    python tools/fetch_data.py              # 默认品种 + tqsdk + 1m
    python tools/fetch_data.py --source akshare  # 改用 akshare
"""

from __future__ import annotations

import sys
import time
import logging
from pathlib import Path

# 确保项目根在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import ConfigManager
from data import DataManager, export_csv

logger = logging.getLogger(__name__)

# ── 推荐品种：主力连续合约，数据更全 ──────────────────────
#  KQ 格式: KQ.{产品}@{交易所}  — tqsdk 主力连续，自动跟随换月
#  start/end 为 None 时由合约代码自动推算（KQ 合约需显式指定日期）
TARGET_SYMBOLS: list[tuple[str, str | None, str | None, str]] = [
    # (symbol, start_date, end_date, 说明)
    ("KQ.m@DCE",  "2024-01-01", "2026-05-01", "豆粕主力连续"),
    ("KQ.c@DCE",  "2024-01-01", "2026-05-01", "玉米主力连续"),
    ("KQ.i@DCE",  "2024-01-01", "2026-05-01", "铁矿主力连续"),
    ("KQ.p@DCE",  "2024-01-01", "2026-05-01", "棕榈主力连续"),
    ("KQ.rb@SHFE","2024-01-01", "2026-05-01", "螺纹主力连续"),
    ("KQ.SR@CZCE","2024-01-01", "2026-05-01", "白糖主力连续"),
]


def fetch_all(
    source: str = "tqsdk",
    interval: str = "1m",
    force: bool = True,
) -> dict[str, dict]:
    """批量导出数据

    Args:
        source: 数据源 (tqsdk / akshare)
        interval: K 线周期
        force: 是否覆盖已有文件

    Returns:
        {symbol: {success, rows, path, date_range, elapsed}}
    """
    cm = ConfigManager()
    results: dict[str, dict] = {}

    print(f"\n{'='*65}")
    print(f"  一键拉取数据  |  数据源: {source}  |  周期: {interval}")
    print(f"{'='*65}\n")

    for i, (symbol, start, end, desc) in enumerate(TARGET_SYMBOLS, 1):
        t0 = time.time()
        print(f"[{i:2d}/{len(TARGET_SYMBOLS)}] {symbol:<16s} {desc}")
        
        dm = DataManager(cm)
        try:
            success = export_csv(
                symbol=symbol,
                start_date=start,
                end_date=end,
                dm=dm,
                config_manager=cm,
                force=force,
                interval=interval,
                source=source,
            )
            elapsed = time.time() - t0
            if success:
                results[symbol] = {
                    "success": True,
                    "elapsed": elapsed,
                }
                print(f"       ✅ 成功  ({elapsed:.1f}s)")
            else:
                results[symbol] = {"success": False, "elapsed": elapsed}
                print(f"       ❌ 无可用数据  ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            results[symbol] = {"success": False, "elapsed": elapsed, "error": str(e)}
            print(f"       ❌ 失败: {e}  ({elapsed:.1f}s)")

    # 汇总
    print(f"\n{'='*65}")
    ok = sum(1 for r in results.values() if r["success"])
    fail = len(results) - ok
    total_time = sum(r["elapsed"] for r in results.values())
    print(f"  完成: {ok}/{len(results)} 成功  |  耗时 {total_time:.0f}s")
    if fail:
        print(f"  失败: {fail} 个")
    print(f"{'='*65}\n")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    import argparse
    parser = argparse.ArgumentParser(description="一键拉取近期适配数据")
    parser.add_argument("--source", default="tqsdk", choices=["tqsdk", "akshare"],
                        help="数据源 (默认 tqsdk)")
    parser.add_argument("--interval", default="1m", help="K线周期 (默认 1m)")
    parser.add_argument("--no-force", action="store_true", help="不覆盖已有文件")
    args = parser.parse_args()

    fetch_all(source=args.source, interval=args.interval, force=not args.no_force)
