"""H4 · 跨周期趋势泄漏假设检验 · Higher-Frequency Trend Leakage Probe.

文件级元信息：
- 创建背景：§2.14.2 KF-11 归因语言修正后引出新问题：K_S=4/RR=2 @ 5m 上 P_win 从零漂移
  Fourier null 的 0.6% 抬到实测 26.3%，机制层来源是什么？H4 假设：**长周期（如 1h）
  的趋势凝聚泄漏到 5m barrier**——由 KF-16 Hurst H_1h ≈ 0.60 支持。若为真，则同一批
  5m trades 按"入场时刻的 1h EMA 方向"分组，趋势同向组 P_win 应显著高于反向组。
- 用途：读 5m 完整 trades CSV，对 K_S=4/RR=2 combo 取所有 trade，用同合约 1h close
  序列计算 EMA20，判断入场 bar 对应的 1h 方向 (close - EMA20 > 0 = 上行趋势)。按
  ("trade side × trend direction") 是否一致分组，重算 P_win / E_gross / SE 与 z 检验。
- 注意事项：入场 bar 时间通过 5m CSV 的 datetime 字段取；找对应 1h close 用 asof 匹配
  （不超过入场时刻的最近 1h close）。EMA 前 20 bar 数据不足则跳过。

研究命题：
    H4：K_S=4/RR=2 @ 5m 上 P_win 抬升源于 1h 趋势凝聚泄漏。
    若为真：
    (a) 趋势同向组 P_win_up ≫ 反向组 P_win_down
    (b) 两组 E_gross 差应显著 > 0（"如果能挑对方向就能兑现 alpha"）

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/hf_trend_leakage_probe.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from data.output_paths import market_csv_dir, project_data_root

# ────────────────────── 常量 ──────────────────────
# 20 合约 (与 boundary_explorer 一致)
SYMBOLS: list[tuple[str, str]] = [
    ("rb2601", "SHFE.rb2601"),
    ("rb2605", "SHFE.rb2605"),
    ("i2601", "DCE.i2601"),
    ("i2509", "DCE.i2509"),
    ("cu2601", "SHFE.cu2601"),
    ("cu2509", "SHFE.cu2509"),
    ("al2601", "SHFE.al2601"),
    ("al2509", "SHFE.al2509"),
    ("sc2512", "INE.sc2512"),
    ("sc2509", "INE.sc2509"),
    ("TA601", "CZCE.TA601"),
    ("TA509", "CZCE.TA509"),
    ("m2601", "DCE.m2601"),
    ("m2605", "DCE.m2605"),
    ("p2601", "DCE.p2601"),
    ("p2605", "DCE.p2605"),
    ("SR601", "CZCE.SR601"),
    ("SR605", "CZCE.SR605"),
    ("CF601", "CZCE.CF601"),
    ("CF509", "CZCE.CF509"),
]

# 检验的 combo 组合
KEY_COMBOS = [
    (4.0, 2.0),  # KF-11 核心（P_win 从 0.6% 抬到 26.3%）
    (2.5, 2.0),  # 相邻长期区
    (2.5, 1.0),
    (4.0, 1.0),
    (1.5, 2.0),  # 过渡区
    (1.0, 1.0),  # martingale 参照
]

EMA_WINDOW = 20
TREND_THRESHOLD_ATR_FRAC = 0.0  # (1h close - EMA) / 1h ATR > 0 视为上行


def _latest_5m_trades_csv(out_dir: Path) -> Path:
    # 极端 RR 扫描 (21:39) 之后 K_S<1 扫描 (23:20) 覆盖了 5m—— 需要用完整 65 combo 的 5m trades
    # 完整 65 combo 5m trades 是 15:31 的
    legacy = out_dir / "boundary_explorer_trades_realcost_20260714_153121.csv"
    if legacy.exists():
        return legacy
    raise SystemExit("[error] 需要完整 65 combo 5m trades CSV (15:31 版本)")


def _load_1h_series(csv_dir: Path, symbol_full: str) -> pd.DataFrame:
    path = csv_dir / f"{symbol_full}.tqsdk.1h.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["datetime"])
    df["ema20"] = df["close"].ewm(span=EMA_WINDOW, adjust=False).mean()
    df["trend_score"] = df["close"] - df["ema20"]
    return df


def _load_5m_series(csv_dir: Path, symbol_full: str) -> pd.DataFrame:
    path = csv_dir / f"{symbol_full}.tqsdk.5m.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["datetime"])


def match_trend_direction(entry_time: pd.Timestamp, df_1h: pd.DataFrame) -> int:
    """返回 +1 (上行), -1 (下行), 0 (无 EMA 数据)."""
    # 找不超过 entry_time 的最近 1h bar
    mask = df_1h["datetime"] <= entry_time
    if not mask.any():
        return 0
    row = df_1h.loc[mask].iloc[-1]
    if pd.isna(row["ema20"]):
        return 0
    score = row["trend_score"]
    if score > TREND_THRESHOLD_ATR_FRAC:
        return 1
    if score < -TREND_THRESHOLD_ATR_FRAC:
        return -1
    return 0


def stratify(out_dir: Path, csv_dir: Path) -> dict:
    # 1. 加载 5m trades CSV
    trades_path = _latest_5m_trades_csv(out_dir)

    # 2. 预加载所有品种的 1h 与 5m 数据
    symbol_to_1h: dict[str, pd.DataFrame] = {}
    symbol_to_5m: dict[str, pd.DataFrame] = {}
    for _short, full in SYMBOLS:
        d1h = _load_1h_series(csv_dir, full)
        d5m = _load_5m_series(csv_dir, full)
        if not d1h.empty and not d5m.empty:
            symbol_to_1h[full] = d1h
            symbol_to_5m[full] = d5m

    # 3. 按 (K_S, RR) 过滤 trades，标记方向
    combo_buckets: dict[tuple, list[dict]] = defaultdict(list)
    with trades_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            k_s = float(r["K_S"])
            rr = float(r["RR"])
            if (k_s, rr) not in KEY_COMBOS:
                continue
            if int(r["max_bars"]) != 80:
                continue
            symbol_short = r["symbol"]
            # 找到对应完整 symbol
            symbol_full = None
            for s, full in SYMBOLS:
                if s == symbol_short:
                    symbol_full = full
                    break
            if symbol_full is None or symbol_full not in symbol_to_5m:
                continue

            entry_idx = int(r["entry_idx"])
            df_5m = symbol_to_5m[symbol_full]
            if entry_idx >= len(df_5m):
                continue
            entry_time = df_5m["datetime"].iat[entry_idx]

            trend_dir = match_trend_direction(entry_time, symbol_to_1h[symbol_full])
            if trend_dir == 0:
                continue

            side = int(r["side"])  # +1 or -1
            trade_aligned = side == trend_dir

            combo_buckets[(k_s, rr)].append(
                {
                    "symbol": symbol_short,
                    "side": side,
                    "trend_dir": trend_dir,
                    "aligned": trade_aligned,
                    "exit_reason": r["exit_reason"],
                    "gross_atr": float(r["gross_atr"]),
                    "net_atr": float(r["net_atr"]),
                }
            )

    # 4. 分组统计
    results: list[dict] = []
    for (k_s, rr), trades in combo_buckets.items():
        for group_name, filter_fn in [
            ("all", lambda t: True),  # noqa: ARG005
            ("aligned", lambda t: t["aligned"]),
            ("opposed", lambda t: not t["aligned"]),
        ]:
            subset = [t for t in trades if filter_fn(t)]
            n = len(subset)
            if n == 0:
                continue
            n_wins = sum(1 for t in subset if t["exit_reason"] == "take")
            n_time = sum(1 for t in subset if t["exit_reason"] in ("time_exit", "data_end"))
            p_win = n_wins / n
            p_time = n_time / n
            e_gross = float(np.mean([t["gross_atr"] for t in subset]))
            e_net = float(np.mean([t["net_atr"] for t in subset]))
            std_gross = float(np.std([t["gross_atr"] for t in subset], ddof=1)) if n > 1 else 0.0
            se_gross = std_gross / math.sqrt(n) if n > 0 else float("nan")
            z_gross = e_gross / se_gross if se_gross > 0 else float("nan")

            results.append(
                {
                    "K_S": k_s,
                    "RR": rr,
                    "group": group_name,
                    "n": n,
                    "P_win": p_win,
                    "P_time_exit": p_time,
                    "E_gross": e_gross,
                    "E_net": e_net,
                    "SE_gross": se_gross,
                    "z_gross": z_gross,
                }
            )

    # 5. Aligned vs Opposed 差异检验
    diffs: list[dict] = []
    for k_s, rr in KEY_COMBOS:
        aligned = next((r for r in results if r["K_S"] == k_s and r["RR"] == rr and r["group"] == "aligned"), None)
        opposed = next((r for r in results if r["K_S"] == k_s and r["RR"] == rr and r["group"] == "opposed"), None)
        all_g = next((r for r in results if r["K_S"] == k_s and r["RR"] == rr and r["group"] == "all"), None)
        if aligned is None or opposed is None:
            continue
        delta_pwin = aligned["P_win"] - opposed["P_win"]
        delta_egross = aligned["E_gross"] - opposed["E_gross"]
        # Welch t on P_win
        pa, na = aligned["P_win"], aligned["n"]
        po, no = opposed["P_win"], opposed["n"]
        se_diff = math.sqrt(pa * (1 - pa) / na + po * (1 - po) / no)
        z_pwin_diff = delta_pwin / se_diff if se_diff > 0 else float("nan")
        diffs.append(
            {
                "K_S": k_s,
                "RR": rr,
                "n_aligned": na,
                "n_opposed": no,
                "n_all": all_g["n"] if all_g else na + no,
                "P_win_aligned": pa,
                "P_win_opposed": po,
                "P_win_all": all_g["P_win"] if all_g else float("nan"),
                "delta_P_win": delta_pwin,
                "z_P_win": z_pwin_diff,
                "E_gross_aligned": aligned["E_gross"],
                "E_gross_opposed": opposed["E_gross"],
                "delta_E_gross": delta_egross,
                "significant": abs(z_pwin_diff) > 2 if not math.isnan(z_pwin_diff) else False,
            }
        )

    return {
        "config": {
            "key_combos": KEY_COMBOS,
            "ema_window": EMA_WINDOW,
            "trades_csv": str(trades_path),
        },
        "groupwise": results,
        "aligned_vs_opposed": diffs,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 100}")
    print("H4 跨周期趋势泄漏假设检验 · K_S=4/RR=2 @ 5m 分组重算")
    print(f"{'=' * 100}")
    print(
        f"\n{'K_S':>5} {'RR':>4} {'group':>10} {'n':>6} {'P_win':>7} {'time%':>7} {'E_gross':>9} {'E_net':>9} {'z_gross':>8}"
    )
    print("-" * 80)
    for r in sorted(summary["groupwise"], key=lambda x: (-x["K_S"], -x["RR"], x["group"])):
        print(
            f"{r['K_S']:>5.2f} {r['RR']:>4.1f} {r['group']:>10} {r['n']:>6} "
            f"{r['P_win']:>7.4f} {r['P_time_exit'] * 100:>6.2f}% "
            f"{r['E_gross']:>+9.4f} {r['E_net']:>+9.4f} {r['z_gross']:>+8.2f}"
        )

    print()
    print(f"{'=' * 100}")
    print("Aligned vs Opposed 差异检验")
    print(f"{'=' * 100}")
    print(
        f"\n{'K_S':>5} {'RR':>4} {'n_al':>7} {'n_op':>7} {'P_win_al':>9} {'P_win_op':>9} {'ΔP_win':>8} {'z':>7} {'ΔE_gross':>10} {'sig?':>6}"
    )
    print("-" * 90)
    for d in summary["aligned_vs_opposed"]:
        sig = "✓" if d["significant"] else "✗"
        print(
            f"{d['K_S']:>5.2f} {d['RR']:>4.1f} {d['n_aligned']:>7d} {d['n_opposed']:>7d} "
            f"{d['P_win_aligned']:>9.4f} {d['P_win_opposed']:>9.4f} "
            f"{d['delta_P_win']:>+8.4f} {d['z_P_win']:>+7.2f} "
            f"{d['delta_E_gross']:>+10.4f} {sig:>6}"
        )

    # 结论
    print()
    print(f"{'=' * 60}")
    print("结论")
    print(f"{'=' * 60}")
    n_sig = sum(1 for d in summary["aligned_vs_opposed"] if d["significant"])
    print(f"  {n_sig}/{len(summary['aligned_vs_opposed'])} 行 Aligned vs Opposed 差异显著 (|z|>2)")
    print("  若 ΔP_win > 0 且 z>2 → H4 假设支持：1h 趋势泄漏到 5m barrier")
    print("  若 ΔE_gross > 0 且显著 → 可挑方向兑现 alpha (阶段 2a 潜力)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=str, default=None)
    args = parser.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else project_data_root() / "research" / "first_passage_boundary"
    csv_dir = market_csv_dir()

    print("读取 5m trades ...")
    summary = stratify(out_dir, csv_dir)
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"hf_trend_leakage_{timestamp}.json"
    csv_path = out_dir / f"hf_trend_leakage_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "K_S",
                "RR",
                "group",
                "n",
                "P_win",
                "P_time_exit",
                "E_gross",
                "E_net",
                "SE_gross",
                "z_gross",
            ]
        )
        for r in summary["groupwise"]:
            writer.writerow(
                [
                    f"{r['K_S']:.2f}",
                    f"{r['RR']:.1f}",
                    r["group"],
                    r["n"],
                    f"{r['P_win']:.6f}",
                    f"{r['P_time_exit']:.6f}",
                    f"{r['E_gross']:+.6f}",
                    f"{r['E_net']:+.6f}",
                    f"{r['SE_gross']:.6f}",
                    f"{r['z_gross']:+.4f}",
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
