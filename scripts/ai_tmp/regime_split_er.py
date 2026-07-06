"""
文件级元信息：
- 创建背景：主题 structural-shaping-alpha 阶段 1 猜想 §8.5。用户对 §8.4
  的判决提出质疑："G/H/I 混合行情下的 mean 不能等于震荡行情下的 mean"。
  需要按行情类型分层重新评估。
- 用途：读现成 gatekeeper SCALE=1 CSV → 对每笔计算入场时（entry_idx）
  过去 20 bar 的 Efficiency Ratio (Kaufman ER) → 按三档分位切片 →
  每个 combo × 每档分别统计 mean / win_rate / paired vs E。
- 注意事项：
  1. ER 只用 entry_idx 之前的数据（entry_idx-20 到 entry_idx-1），无 look-ahead
  2. 三档分位切片使用**全局分位**（不按 combo 独立切，否则每 combo 分位
     切点不同，无法做 paired diff）
  3. 一次性诊断脚本，跑完写 workbench §8.5
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data.output_paths import market_csv_dir, project_data_root


ER_WINDOW = 20  # Kaufman ER 使用的回看 bar 数


SYMBOL_FILES: list[tuple[str, str]] = [
    ("rb2601", "SHFE.rb2601.tqsdk.5m.csv"),
    ("rb2605", "SHFE.rb2605.tqsdk.5m.csv"),
    ("i2601", "DCE.i2601.tqsdk.5m.csv"),
    ("i2509", "DCE.i2509.tqsdk.5m.csv"),
    ("cu2601", "SHFE.cu2601.tqsdk.5m.csv"),
    ("cu2509", "SHFE.cu2509.tqsdk.5m.csv"),
    ("al2601", "SHFE.al2601.tqsdk.5m.csv"),
    ("al2509", "SHFE.al2509.tqsdk.5m.csv"),
    ("sc2512", "INE.sc2512.tqsdk.5m.csv"),
    ("sc2509", "INE.sc2509.tqsdk.5m.csv"),
    ("TA601", "CZCE.TA601.tqsdk.5m.csv"),
    ("TA509", "CZCE.TA509.tqsdk.5m.csv"),
    ("m2601", "DCE.m2601.tqsdk.5m.csv"),
    ("m2605", "DCE.m2605.tqsdk.5m.csv"),
    ("p2601", "DCE.p2601.tqsdk.5m.csv"),
    ("p2605", "DCE.p2605.tqsdk.5m.csv"),
    ("SR601", "CZCE.SR601.tqsdk.5m.csv"),
    ("SR605", "CZCE.SR605.tqsdk.5m.csv"),
    ("CF601", "CZCE.CF601.tqsdk.5m.csv"),
    ("CF509", "CZCE.CF509.tqsdk.5m.csv"),
]


def load_closes(symbol: str) -> np.ndarray | None:
    for sym, f in SYMBOL_FILES:
        if sym == symbol:
            path = market_csv_dir() / f
            if not path.exists():
                return None
            df = pd.read_csv(path)
            return df["close"].to_numpy()
    return None


def efficiency_ratio(closes: np.ndarray, end_idx_exclusive: int, window: int) -> float:
    """Kaufman ER: |close_t - close_{t-N}| / Σ|close_i - close_{i-1}|.

    end_idx_exclusive 是"不参与计算"的下一根 bar；ER 用 [end_idx_exclusive-window, end_idx_exclusive) 区间。
    避免 look-ahead：entry_idx 处入场，ER 只看 entry_idx-window 到 entry_idx-1 的收盘价。
    """
    start = end_idx_exclusive - window
    if start < 1 or end_idx_exclusive > len(closes):
        return float("nan")
    seg = closes[start - 1 : end_idx_exclusive]  # 多取 1 根用于算首个 diff
    if len(seg) < window + 1:
        return float("nan")
    direction = abs(seg[-1] - seg[0])
    diffs = np.abs(np.diff(seg))
    volatility = float(diffs.sum())
    if volatility <= 0:
        return float("nan")
    return float(direction / volatility)


def main() -> None:
    args = _parse_args()
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = Path.cwd() / csv_path
    trades = pd.read_csv(csv_path)

    # 缓存每个 symbol 的 close 序列
    close_cache: dict[str, np.ndarray] = {}
    for sym in trades["symbol"].unique():
        c = load_closes(sym)
        if c is not None:
            close_cache[sym] = c

    # 对每笔算 ER（用 entry_idx 之前 20 bar）
    er_values: list[float] = []
    for _, row in trades.iterrows():
        closes = close_cache.get(row["symbol"])
        if closes is None:
            er_values.append(float("nan"))
            continue
        er = efficiency_ratio(closes, int(row["entry_idx"]), ER_WINDOW)
        er_values.append(er)
    trades["er"] = er_values

    # 用一个 combo（如 E）的事件计算全局三档分位切点，保证跨 combo 事件配对
    e_events = trades[trades["combo"] == "E"].dropna(subset=["er"])
    q33, q67 = e_events["er"].quantile([0.333, 0.667]).tolist()

    def bucket(er: float) -> str:
        if math.isnan(er):
            return "nan"
        if er <= q33:
            return "chop"
        if er <= q67:
            return "mixed"
        return "trend"

    trades["bucket"] = trades["er"].apply(bucket)

    # E baseline map: (symbol, entry_idx, side) -> net_atr
    e_map: dict[tuple[str, int, int], float] = {}
    for _, r in trades[trades["combo"] == "E"].iterrows():
        e_map[(r["symbol"], int(r["entry_idx"]), int(r["side"]))] = float(r["net_atr"])

    summary: dict[str, dict[str, dict[str, float]]] = {}
    combos = list(trades["combo"].unique())
    for combo in combos:
        summary[combo] = {}
        for bkt in ["chop", "mixed", "trend"]:
            sel = trades[(trades["combo"] == combo) & (trades["bucket"] == bkt)]
            if len(sel) == 0:
                continue
            nets = sel["net_atr"].to_numpy()
            wins = (nets > 0).sum()
            n = len(nets)
            row: dict[str, float] = {
                "n": int(n),
                "mean_net_atr": float(nets.mean()),
                "win_rate": float(wins / n),
                "median_net_atr": float(np.median(nets)),
            }
            # paired diff vs E（同 bucket 内配对）
            if combo != "E":
                diffs: list[float] = []
                for _, r in sel.iterrows():
                    key = (r["symbol"], int(r["entry_idx"]), int(r["side"]))
                    if key in e_map:
                        diffs.append(float(r["net_atr"]) - e_map[key])
                if diffs:
                    diffs_arr = np.asarray(diffs)
                    # bootstrap 5000
                    rng = np.random.default_rng(42)
                    boot = []
                    for _ in range(2000):
                        boot.append(rng.choice(diffs_arr, size=len(diffs_arr), replace=True).mean())
                    boot = np.asarray(boot)
                    row["paired_diff_mean"] = float(diffs_arr.mean())
                    row["paired_diff_ci_lo"] = float(np.quantile(boot, 0.025))
                    row["paired_diff_ci_hi"] = float(np.quantile(boot, 0.975))
                    row["paired_diff_p_gt_0"] = float((boot <= 0).mean())
            summary[combo][bkt] = row

    result = {
        "source_csv": str(csv_path),
        "er_window": ER_WINDOW,
        "q33": q33,
        "q67": q67,
        "bucket_sizes_by_E": {
            "chop": int((trades[(trades["combo"] == "E") & (trades["bucket"] == "chop")]).shape[0]),
            "mixed": int((trades[(trades["combo"] == "E") & (trades["bucket"] == "mixed")]).shape[0]),
            "trend": int((trades[(trades["combo"] == "E") & (trades["bucket"] == "trend")]).shape[0]),
        },
        "combos": summary,
    }

    out_dir = project_data_root() / "research" / "structural_shaping_gatekeeper"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"regime_split_er20_{ts}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console 打印
    print(f"\nER window = {ER_WINDOW}   q33 = {q33:.4f}   q67 = {q67:.4f}")
    print(f"Bucket sizes (by E): chop={result['bucket_sizes_by_E']['chop']}  mixed={result['bucket_sizes_by_E']['mixed']}  trend={result['bucket_sizes_by_E']['trend']}")
    print()
    header = f"{'combo':<4}"
    for bkt in ["chop", "mixed", "trend"]:
        header += f"  {bkt+' mean':>12} {bkt+' win':>10}"
    print(header)
    for combo in combos:
        line = f"{combo:<4}"
        for bkt in ["chop", "mixed", "trend"]:
            s = summary[combo].get(bkt, {})
            if s:
                line += f"  {s['mean_net_atr']:>+12.4f} {s['win_rate']:>10.4f}"
            else:
                line += f"  {'-':>12} {'-':>10}"
        print(line)

    print()
    print("Paired diff vs E (95% CI):")
    hdr = f"{'combo':<4}"
    for bkt in ["chop", "mixed", "trend"]:
        hdr += f"  {bkt+' diff':>10} {bkt+' p(<=0)':>10}"
    print(hdr)
    for combo in combos:
        if combo == "E":
            continue
        line = f"{combo:<4}"
        for bkt in ["chop", "mixed", "trend"]:
            s = summary[combo].get(bkt, {})
            d = s.get("paired_diff_mean")
            p = s.get("paired_diff_p_gt_0")
            if d is not None:
                line += f"  {d:>+10.4f} {p:>10.4f}"
            else:
                line += f"  {'-':>10} {'-':>10}"
        print(line)
    print(f"\nJSON: {json_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split gatekeeper trades by market regime (Efficiency Ratio buckets)")
    parser.add_argument("--csv", required=True, help="path to structural_shaping_gatekeeper CSV")
    return parser.parse_args()


if __name__ == "__main__":
    main()
