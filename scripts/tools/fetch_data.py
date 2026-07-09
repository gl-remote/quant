#!/usr/bin/env python3
"""一键拉取近期适配数据 — 默认用 tqsdk 导出多品种 1m 分钟线

用法:
    uv run python scripts/tools/fetch_data.py              # 默认品种 + tqsdk + 1m
    uv run python scripts/tools/fetch_data.py --source akshare  # 改用 akshare
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from config import ConfigManager
from data import DataManager, export_csv
from loguru import logger

# ── 推荐品种：2026 年已到期合约为主，覆盖完整行情 ──
#  原则：优先选 2026 已到期合约（01/03/05 月），数据完整，便于回测
#  start/end 为 None 时由 parse_contract 自动推算默认日期范围
TARGET_SYMBOLS: list[tuple[str, str | None, str | None, str]] = [
    # (symbol, start_date, end_date, 说明)
    # 豆粕系列 — 2026 已到期合约
    ("DCE.m2601", None, None, "豆粕 2601  已到期"),
    ("DCE.m2603", None, None, "豆粕 2603  已到期"),
    ("DCE.m2605", None, None, "豆粕 2605  已到期"),
    # 玉米系列 — 2026 已到期合约
    ("DCE.c2601", None, None, "玉米 2601  已到期"),
    ("DCE.c2603", None, None, "玉米 2603  已到期"),
    ("DCE.c2605", None, None, "玉米 2605  已到期"),
    # 淀粉系列 — 2026 已到期合约
    ("DCE.cs2601", None, None, "淀粉 2601  已到期"),
    ("DCE.cs2603", None, None, "淀粉 2603  已到期"),
    ("DCE.cs2605", None, None, "淀粉 2605  已到期"),
    # 其他品种做对比验证
    ("DCE.i2601", None, None, "铁矿 2601  已到期"),
    ("DCE.p2601", None, None, "棕榈 2601  已到期"),
    # 棕榈 R29 扩样组（Group_P 主验证样本，需完整 5m 序列）
    ("DCE.p2405", None, None, "棕榈 2405  已到期 (R29 Group_P)"),
    ("DCE.p2409", None, None, "棕榈 2409  已到期 (R29 Group_P)"),
    ("DCE.p2501", None, None, "棕榈 2501  已到期 (R29 Group_P)"),
    ("DCE.p2505", None, None, "棕榈 2505  已到期 (R29 Group_P)"),
    ("DCE.p2509", None, None, "棕榈 2509  已到期 (R29 Group_P)"),
    ("DCE.p2605", None, None, "棕榈 2605  已到期 (R29 Group_P)"),
    ("SHFE.rb2601", None, None, "螺纹 2601  已到期"),
    ("CZCE.SR601", None, None, "白糖 601  已到期"),
]


def fetch_all(
    source: str = "tqsdk",
    interval: str = "1m",
    force: bool = False,
) -> dict[str, dict]:
    """批量导出数据

    Args:
        source: 数据源 (tqsdk / akshare)
        interval: K 线周期
        force: 强制重新拉取（默认跳过已有文件）

    Returns:
        {symbol: {success, rows, path, date_range, elapsed}}
    """
    cm = ConfigManager(env="backtest")
    dc = cm.get_data_config()
    results: dict[str, dict] = {}

    print(f"\n{'=' * 65}")
    print(f"  一键拉取数据  |  数据源: {source}  |  周期: {interval}")
    print(f"  CSV 目录: {dc.export_dir}")
    print(f"{'=' * 65}\n")

    for i, (symbol, start, end, desc) in enumerate(TARGET_SYMBOLS, 1):
        t0 = time.time()
        print(f"[{i:2d}/{len(TARGET_SYMBOLS)}] {symbol:<16s} {desc}")

        # 检查是否已有数据，跳过
        expected_file = Path(dc.export_dir) / dc.filename_template.format(
            symbol=symbol, provider=source, interval=interval
        )
        if expected_file.exists() and not force:
            elapsed = time.time() - t0
            results[symbol] = {"success": True, "elapsed": elapsed, "skipped": True}
            print(f"       ⏭ 跳过 (已存在 {expected_file.name})")
            continue

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
    print(f"\n{'=' * 65}")
    ok = sum(1 for r in results.values() if r.get("success"))
    skipped = sum(1 for r in results.values() if r.get("skipped"))
    new_ok = ok - skipped
    fail = sum(1 for r in results.values() if not r.get("success"))
    total_time = sum(r["elapsed"] for r in results.values())
    parts = []
    if new_ok:
        parts.append(f"新拉取 {new_ok}")
    if skipped:
        parts.append(f"跳过 {skipped}")
    parts.append(f"失败 {fail}")
    print(f"  完成: {' / '.join(parts)}  |  耗时 {total_time:.0f}s")
    print(f"{'=' * 65}\n")

    return results


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    import argparse

    parser = argparse.ArgumentParser(description="一键拉取近期适配数据")
    parser.add_argument("--source", default="tqsdk", choices=["tqsdk", "akshare"], help="数据源 (默认 tqsdk)")
    parser.add_argument("--interval", default="1m", help="K线周期 (默认 1m)")
    parser.add_argument("--force", action="store_true", help="强制重新拉取")
    args = parser.parse_args()

    fetch_all(source=args.source, interval=args.interval, force=args.force)
