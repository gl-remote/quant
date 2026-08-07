#!/usr/bin/env python3
"""下载 2022-2023 年熊市/震荡市数据用于 out-of-sample 验证。

选取 2022-2023 期间主力合约：
- 2022 年加息周期商品大幅波动
- 2023 年震荡市
- 需要 1h 和 15m 数据

用法：
    .venv/bin/python scripts/fetch_bear_market.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# 添加 workspace 到 path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

from config import ConfigManager
from data import DataManager, export_csv
from loguru import logger

# 2022-2023 主力合约（覆盖农产品/有色/能化/黑色）
# 格式: (symbol, start, end, 说明)
TARGETS = [
    # 农产品
    ("DCE.m2301", "2022-05-01", "2023-01-31", "豆粕 2301"),
    ("DCE.m2305", "2022-09-01", "2023-05-31", "豆粕 2305"),
    ("DCE.c2301", "2022-05-01", "2023-01-31", "玉米 2301"),
    ("DCE.c2305", "2022-09-01", "2023-05-31", "玉米 2305"),
    ("CZCE.SR301", "2022-05-01", "2023-01-31", "白糖 301"),
    ("CZCE.SR305", "2022-09-01", "2023-05-31", "白糖 305"),
    ("DCE.p2301", "2022-05-01", "2023-01-31", "棕榈 2301"),
    ("DCE.p2305", "2022-09-01", "2023-05-31", "棕榈 2305"),
    # 有色
    ("SHFE.cu2301", "2022-05-01", "2023-01-31", "铜 2301"),
    ("SHFE.cu2305", "2022-09-01", "2023-05-31", "铜 2305"),
    ("SHFE.al2301", "2022-05-01", "2023-01-31", "铝 2301"),
    ("SHFE.al2305", "2022-09-01", "2023-05-31", "铝 2305"),
    # 能化
    ("INE.sc2301", "2022-05-01", "2023-01-31", "原油 2301"),
    ("INE.sc2305", "2022-09-01", "2023-05-31", "原油 2305"),
    ("CZCE.TA301", "2022-05-01", "2023-01-31", "PTA 301"),
    ("CZCE.TA305", "2022-09-01", "2023-05-31", "PTA 305"),
    # 黑色
    ("DCE.i2301", "2022-05-01", "2023-01-31", "铁矿 2301"),
    ("DCE.i2305", "2022-09-01", "2023-05-31", "铁矿 2305"),
    ("SHFE.rb2301", "2022-05-01", "2023-01-31", "螺纹 2301"),
    ("SHFE.rb2305", "2022-09-01", "2023-05-31", "螺纹 2305"),
]


def main():
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    cm = ConfigManager(env="backtest")
    dc = cm.get_data_config()

    for interval in ["1h", "15m", "5m"]:
        print(f"\n{'='*60}")
        print(f"  下载周期: {interval}")
        print(f"  输出目录: {dc.export_dir}")
        print(f"{'='*60}\n")

        ok = 0
        skip = 0
        fail = 0
        t_start = time.time()

        for i, (sym, start, end, desc) in enumerate(TARGETS, 1):
            t0 = time.time()
            expected = Path(dc.export_dir) / dc.filename_template.format(
                symbol=sym, provider="tqsdk", interval=interval
            )
            if expected.exists():
                print(f"[{i:2d}/{len(TARGETS)}] {sym:<16s} ⏭ 跳过 (已存在)")
                skip += 1
                continue

            print(f"[{i:2d}/{len(TARGETS)}] {sym:<16s} {desc} ({start}~{end})")
            try:
                dm = DataManager(cm)
                success = export_csv(
                    symbol=sym,
                    start_date=start,
                    end_date=end,
                    dm=dm,
                    config_manager=cm,
                    force=False,
                    interval=interval,
                    source="tqsdk",
                )
                elapsed = time.time() - t0
                if success:
                    ok += 1
                    print(f"       ✅ 成功 ({elapsed:.1f}s)")
                else:
                    fail += 1
                    print(f"       ❌ 无数据 ({elapsed:.1f}s)")
            except Exception as e:
                fail += 1
                print(f"       ❌ 失败: {e}")

        total = time.time() - t_start
        print(f"\n  完成: 新下载 {ok} / 跳过 {skip} / 失败 {fail}  耗时 {total:.0f}s")


if __name__ == "__main__":
    main()
