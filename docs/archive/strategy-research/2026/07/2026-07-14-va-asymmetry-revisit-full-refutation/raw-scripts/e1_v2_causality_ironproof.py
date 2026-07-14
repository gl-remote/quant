"""
文件级元信息：
- 创建背景：e1 因验证脚本的截断参数错误（用 bars_full.iloc[:eidx] 不含 event
  bar）导致 atr / trend 出现"看起来像未来函数"的微小 diff。本脚本用正确
  语义重跑：event 在 bar[eidx] 的 close 时刻发生（close 已定，可见），
  所以严格 causal 允许使用 bars_full.iloc[:eidx+1]（含 event bar 自身）
  的全部数据。
- 用途：对 200+ 随机 event，用 bars_full.iloc[:eidx+1] 作 truncated 数据，
  验证 A3_skew / atr_intra / trend_intra 三特征值与 full-data 计算结果
  完全一致（max_abs_diff = 0）。
- 注意事项：临时研究脚本，产物在 outputs/e1_v2/。这是因果性铁证的正确版。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from c1_causal_tier_scan import ATR_WIN_5M, TREND_WIN_5M  # noqa: E402
from h1_a3_skew_pooled_ic import (  # noqa: E402
    ROLLING_BARS_5M, TICK_SIZE, build_w3_profile, parse_prefix, sample_hourly_events,
)

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/e1_v2"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "SHFE.rb2601", "SHFE.rb2605", "DCE.i2601", "DCE.m2601",
    "SHFE.cu2601", "SHFE.al2601", "INE.sc2512", "CZCE.TA601",
    "CZCE.SR601", "CZCE.CF601", "DCE.y2601", "DCE.c2601",
    "SHFE.hc2601", "SHFE.ag2601", "CZCE.RM601",
]


def compute_features(bars: pd.DataFrame, at_idx: int, tick: float) -> dict:
    """在 bars DataFrame 中的位置 at_idx 处计算三特征。
    at_idx 是 event 所在的 5m bar 索引 · event 在 bar close 时刻发生。
    """
    # A3_skew: W3 rolling 12h profile，用 bars.iloc[at_idx-144 : at_idx]（不含 at_idx 自身）
    p = build_w3_profile(bars, at_idx, tick)
    a3 = p.skew if p is not None else float("nan")
    # atr_intra / trend_intra: 已在 bars 中含 shift(1)，取 at_idx 位置的值
    atr = float(bars["atr_intra"].iloc[at_idx]) if pd.notna(bars["atr_intra"].iloc[at_idx]) else float("nan")
    trend = float(bars["trend_intra"].iloc[at_idx]) if pd.notna(bars["trend_intra"].iloc[at_idx]) else float("nan")
    return {"A3_skew": a3, "atr_intra": atr, "trend_intra": trend}


def enrich(bars: pd.DataFrame) -> pd.DataFrame:
    b = bars.copy()
    b["log_close"] = np.log(b["close"])
    b["ret_5m"] = b["log_close"].diff()
    b["abs_ret_5m"] = b["ret_5m"].abs()
    b["atr_intra"] = (
        b["abs_ret_5m"].rolling(ATR_WIN_5M, min_periods=48).mean().shift(1)
    )
    b["trend_intra"] = (
        b["ret_5m"].rolling(TREND_WIN_5M, min_periods=48).sum().shift(1)
    )
    return b


def main() -> None:
    rng = np.random.default_rng(20260714)
    probes: list[dict] = []

    for symbol in SYMBOLS:
        path = CSV_DIR / f"{symbol}.tqsdk.5m.csv"
        if not path.exists():
            print(f"[{symbol}] SKIP: no file")
            continue
        raw = pd.read_csv(path)
        raw["datetime"] = pd.to_datetime(raw["datetime"])
        raw = raw.sort_values("datetime").reset_index(drop=True)
        raw["date"] = raw["datetime"].dt.date

        bars_full = enrich(raw)
        prefix = parse_prefix(symbol)
        tick = TICK_SIZE.get(prefix)
        if tick is None:
            continue

        # 采样 15 个 hourly event
        hourly = sample_hourly_events(bars_full)
        dt_to_idx = {dt: i for i, dt in enumerate(bars_full["datetime"])}
        cands = [
            dt_to_idx[dt] for dt in hourly["datetime"]
            if dt in dt_to_idx and ROLLING_BARS_5M + 200 <= dt_to_idx[dt] <= len(bars_full) - 200
        ]
        if len(cands) < 15:
            continue
        picked = rng.choice(cands, size=15, replace=False)

        for eidx in picked:
            eidx = int(eidx)
            # (1) Full data
            f_full = compute_features(bars_full, eidx, tick)

            # (2) Causal truncated: 保留 [0, eidx] 全部（含 event bar 自身）
            #     语义：event 在 bar[eidx].close 时刻发生 → close 已定 → 可见
            #     未来 bars [eidx+1, ...] 全部丢弃 → 严格无未来信息
            raw_trunc = raw.iloc[: eidx + 1].copy().reset_index(drop=True)
            bars_trunc = enrich(raw_trunc)
            # 在 truncated 版本里，event 位置就是 trunc 末尾 (idx = eidx)
            f_trunc = compute_features(bars_trunc, eidx, tick)

            diffs = {
                k: (abs(f_full[k] - f_trunc[k])
                    if not (math.isnan(f_full[k]) or math.isnan(f_trunc[k]))
                    else float("nan"))
                for k in f_full
            }
            probes.append({
                "symbol": symbol, "event_idx": eidx,
                "A3_skew_full": f_full["A3_skew"], "A3_skew_trunc": f_trunc["A3_skew"],
                "A3_skew_diff": diffs["A3_skew"],
                "atr_full": f_full["atr_intra"], "atr_trunc": f_trunc["atr_intra"],
                "atr_diff": diffs["atr_intra"],
                "trend_full": f_full["trend_intra"], "trend_trunc": f_trunc["trend_intra"],
                "trend_diff": diffs["trend_intra"],
            })
            if len(probes) % 30 == 0:
                print(f"  probed {len(probes)} events …", flush=True)

    df = pd.DataFrame(probes)
    df.to_csv(OUT_DIR / "e1_v2_probes.csv", index=False)
    print(f"\nTotal probes: {len(df)}")

    def report(col: str) -> tuple[float, int, int]:
        d = df[col].dropna()
        max_d = float(d.max()) if len(d) > 0 else float("nan")
        n_zero = int((d < 1e-12).sum())
        return max_d, n_zero, len(d)

    print("\n=== 因果性铁证（正确 truncation：bars.iloc[:eidx+1]） ===")
    all_zero = True
    for col in ["A3_skew_diff", "atr_diff", "trend_diff"]:
        max_d, n_zero, n = report(col)
        pct = n_zero / max(n, 1) * 100
        print(f"  {col}: n={n}, max_abs_diff={max_d:.4e}, "
              f"n_zero(<1e-12)={n_zero}/{n} = {pct:.1f}%")
        if max_d > 1e-12:
            all_zero = False

    print("\n" + "=" * 60)
    if all_zero:
        print("✅ 因果性铁证通过：causal tier pipeline 无未来函数。")
        print(f"   探测 {len(df)} events × 3 特征，全部 diff = 0")
        print("   语义等价性：")
        print("   - 用完整数据算 (含未来 bars) 与 用严格截断数据算 (event 之后 bars 全删)")
        print("   - 两者在 event 时刻的特征值完全相同 → 未来 bars 未参与特征计算")
    else:
        print("❌ 因果性检验失败：存在残留未来信息。")
    print("=" * 60)


if __name__ == "__main__":
    main()
