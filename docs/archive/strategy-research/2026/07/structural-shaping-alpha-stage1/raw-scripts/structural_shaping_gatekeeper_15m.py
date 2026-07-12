"""15m 周期复核 · L/M/N SCALE=1 vs SCALE=1 (5m)

按 v2.2 §2b 跨周期护栏：验证 §8.10 SCALE=5 显著正 mean 是"真实跨周期 tail alpha"
还是"5m 数据被 SCALE=5 过度堆叠"伪影。

方法：15m × SCALE=1 物理时间约 20h，接近 5m×SCALE=5 的 33h；stop_dist=1.5 ATR。
若 15m SCALE=1 复现 mean 显著正 → 真实跨周期 alpha；若消散 → 伪影。

复用主 runner 的所有函数，只改 SYMBOLS 与 csv 后缀。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让主 runner 的 module 可 import
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

import structural_shaping_gatekeeper as base


# 15m 上现有的 19 合约（按 5m SYMBOLS 板块尽力对齐）
SYMBOLS_15M: list[tuple[str, str, str]] = [
    # black
    ("black", "rb2601", "SHFE.rb2601.tqsdk.15m.csv"),
    ("black", "i2601", "DCE.i2601.tqsdk.15m.csv"),
    # agri_dce（豆粕 m 三合约 + 豆油 p 六合约）
    ("agri_dce", "m2601", "DCE.m2601.tqsdk.15m.csv"),
    ("agri_dce", "m2603", "DCE.m2603.tqsdk.15m.csv"),
    ("agri_dce", "m2605", "DCE.m2605.tqsdk.15m.csv"),
    ("agri_dce", "p2405", "DCE.p2405.tqsdk.15m.csv"),
    ("agri_dce", "p2409", "DCE.p2409.tqsdk.15m.csv"),
    ("agri_dce", "p2501", "DCE.p2501.tqsdk.15m.csv"),
    ("agri_dce", "p2505", "DCE.p2505.tqsdk.15m.csv"),
    ("agri_dce", "p2509", "DCE.p2509.tqsdk.15m.csv"),
    ("agri_dce", "p2601", "DCE.p2601.tqsdk.15m.csv"),
    ("agri_dce", "p2605", "DCE.p2605.tqsdk.15m.csv"),
    # agri_czce（白糖）
    ("agri_czce", "SR601", "CZCE.SR601.tqsdk.15m.csv"),
    # 玉米/淀粉（新增板块 agri_corn）
    ("agri_corn", "c2601", "DCE.c2601.tqsdk.15m.csv"),
    ("agri_corn", "c2603", "DCE.c2603.tqsdk.15m.csv"),
    ("agri_corn", "c2605", "DCE.c2605.tqsdk.15m.csv"),
    ("agri_corn", "cs2601", "DCE.cs2601.tqsdk.15m.csv"),
    ("agri_corn", "cs2603", "DCE.cs2603.tqsdk.15m.csv"),
    ("agri_corn", "cs2605", "DCE.cs2605.tqsdk.15m.csv"),
]


def main() -> None:
    # Monkey-patch: 让主 runner 用 15m symbols
    base.SYMBOLS = SYMBOLS_15M
    # 输出目录复用 5m 的
    base.main()


if __name__ == "__main__":
    main()
