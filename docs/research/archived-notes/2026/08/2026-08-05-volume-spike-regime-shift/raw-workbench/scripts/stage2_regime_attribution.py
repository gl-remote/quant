"""
文件级元信息：
- 创建背景：Stage 1.5 在 by_hour 口径下发现 σ/|r| 显著放大，但成交量 spike
  与高 ATR 天然相关。Stage 2 必须排除"放量效应其实是高波动效应"的 confound。
- 用途：对 by_hour z 口径的事件做 (a) BH-FDR 校正、(b) ATR rank 3-way ×
  spike/baseline 二维拆分、(c) ATR 最近邻 1:3 匹配 paired bootstrap。
- 注意事项：
  * ATR rank 在每合约内 trailing 百分位（无 look-ahead）。
  * paired bootstrap 的 cluster key 仍为 (symbol, session_date)。
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.common.symbol_utils import extract_contract_prefix  # noqa: E402
from workspace.data.output_paths import market_csv_dir  # noqa: E402
from workspace.research.bootstrap import cluster_bootstrap  # noqa: E402

LOOKBACK_N = 20
ATR_PERIOD = 14
ATR_RANK_LOOKBACK = 100  # 用过去 100 根 bar 的 ATR 算 rank
Z0_MAIN = 2.0
Z_BASELINE = 0.5
HORIZONS = (1, 3, 6, 12, 20)
N_BOOT = 5000
BOOT_SEED = 20260805
MIN_BARS = 420
CALIPER = 0.10
MATCH_PER_SPIKE = 3


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["log_ret"] = np.log(df["close"]).diff()
    df["session_date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    v = df["volume"]
    # by_hour z
    mu = (
        v.groupby(df["hour"])
        .shift(1)
        .groupby(df["hour"])
        .transform(lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean())
    )
    sd = (
        v.groupby(df["hour"])
        .shift(1)
        .groupby(df["hour"])
        .transform(lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1))
    )
    df["z"] = (v - mu) / sd

    # ATR rank: trailing percentile within ATR_RANK_LOOKBACK, per-contract.
    # 用向量化排名：当前 ATR 在过去 100 根 ATR 中的百分位 = (count(prev < cur)+1)/(N+1)
    atr_arr = df["atr"].to_numpy()
    n = len(atr_arr)
    atr_pct = np.full(n, np.nan)
    L = ATR_RANK_LOOKBACK
    for t in range(L, n):
        window = atr_arr[t - L : t]
        valid = window[np.isfinite(window)]
        if len(valid) >= 50:
            atr_pct[t] = (np.sum(valid < atr_arr[t]) + 1.0) / (len(valid) + 1.0)
    df["atr_pct"] = atr_pct
    return df


def build_events(df: pd.DataFrame, symbol: str, prefix: str) -> list[dict[str, Any]]:
    n = len(df)
    z = df["z"].to_numpy()
    atr = df["atr"].to_numpy()
    atr_pct = df["atr_pct"].to_numpy()
    lr = df["log_ret"].to_numpy()
    sd = df["session_date"].to_numpy()
    hr = df["hour"].to_numpy()
    out: list[dict[str, Any]] = []
    for t in range(LOOKBACK_N * 24 + ATR_PERIOD, n - max(HORIZONS)):
        if not (math.isfinite(z[t]) and math.isfinite(atr_pct[t])):
            continue
        if z[t] >= Z0_MAIN:
            grp = "spike"
        elif abs(z[t]) < Z_BASELINE:
            grp = "baseline"
        else:
            continue
        fut_dict: dict[str, float] = {}
        for h in HORIZONS:
            fut = lr[t + 1 : t + 1 + h]
            fut_dict[f"r_h{h}"] = float(np.nansum(fut))
            fut_dict[f"sigma_h{h}"] = (
                float(np.nanstd(fut, ddof=1)) if len(fut) > 1 else float("nan")
            )
            fut_dict[f"absr_h{h}"] = float(np.nanmean(np.abs(fut)))
        out.append(
            {
                "symbol": symbol,
                "prefix": prefix,
                "session_date": sd[t],
                "t": t,
                "z": float(z[t]),
                "group": grp,
                "hour": int(hr[t]),
                "atr": float(atr[t]),
                "atr_pct": float(atr_pct[t]),
                **fut_dict,
            }
        )
    return out


def cluster_key(e: dict[str, Any]) -> tuple[str, object]:
    return (str(e["symbol"]), e["session_date"])


def boot_mean(events: list[dict[str, Any]], field: str, seed: int) -> tuple[float, float, float]:
    vals = [e for e in events if math.isfinite(e.get(field, float("nan")))]
    if not vals:
        return float("nan"), float("nan"), float("nan")
    r = cluster_bootstrap(
        vals, cluster_key, lambda evts: float(np.mean([x[field] for x in evts])),
        n_boot=N_BOOT, seed=seed,
    )
    return r.point_estimate, r.ci_low, r.ci_high


def boot_paired_diff(pairs: list[tuple[dict, dict]], field: str, seed: int) -> dict[str, float]:
    """每个 pair = (spike_event, matched_baseline_event)；cluster by spike side."""
    clean = [
        (s, b)
        for s, b in pairs
        if math.isfinite(s.get(field, float("nan"))) and math.isfinite(b.get(field, float("nan")))
    ]
    if not clean:
        return {"n_pairs": 0}

    def stat(pair_list: list[tuple[dict, dict]]) -> float:
        return float(np.mean([s[field] - b[field] for s, b in pair_list]))

    # cluster bootstrap：按 spike 侧 (symbol, session_date) 整簇抽
    clusters: dict[tuple, list[tuple[dict, dict]]] = {}
    for s, b in clean:
        clusters.setdefault(cluster_key(s), []).append((s, b))
    keys = list(clusters.keys())
    rng = np.random.default_rng(seed)
    point = stat(clean)
    samples = []
    for _ in range(N_BOOT):
        picked = rng.choice(len(keys), size=len(keys), replace=True)
        batch = []
        for i in picked:
            batch.extend(clusters[keys[i]])
        samples.append(stat(batch))
    s_arr = np.sort(np.array(samples))
    lo = float(s_arr[int(0.025 * N_BOOT)])
    hi = float(s_arr[int(0.975 * N_BOOT)])
    p = 2.0 * min((s_arr <= 0).mean(), (s_arr >= 0).mean())
    return {
        "n_pairs": len(clean),
        "delta": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "p_two": float(min(p, 1.0)),
    }


def bh_fdr(pvals: list[tuple[str, float]], q: float = 0.10) -> dict[str, bool]:
    """BH-FDR；返回 {metric: passed}。"""
    valid = [(m, p) for m, p in pvals if math.isfinite(p)]
    valid.sort(key=lambda x: x[1])
    m_total = len(valid)
    out: dict[str, bool] = {}
    k_max = -1
    for rank, (metric, p) in enumerate(valid, start=1):
        if p <= (rank / m_total) * q:
            k_max = rank
    for i, (metric, _) in enumerate(valid):
        out[metric] = i < k_max if k_max >= 0 else False
    return out


def atr_bucket(pct: float) -> str:
    if pct < 0.33:
        return "low"
    if pct < 0.67:
        return "mid"
    return "high"


def match_baseline(
    spike: list[dict[str, Any]], baseline: list[dict[str, Any]], caliper: float, k: int
) -> list[tuple[dict, dict]]:
    """每个 spike 从 baseline 找同 prefix、atr_pct 距离 ≤ caliper 的最近 k 个 baseline。"""
    base_by_prefix: dict[str, list[dict]] = {}
    for b in baseline:
        base_by_prefix.setdefault(b["prefix"], []).append(b)
    for lst in base_by_prefix.values():
        lst.sort(key=lambda e: e["atr_pct"])

    pairs: list[tuple[dict, dict]] = []
    for s in spike:
        cands = base_by_prefix.get(s["prefix"], [])
        if not cands:
            continue
        target = s["atr_pct"]
        # 二分找最接近
        import bisect

        keys = [e["atr_pct"] for e in cands]
        idx = bisect.bisect_left(keys, target)
        picked: list[dict] = []
        # 向两侧扩张
        lo_i, hi_i = idx - 1, idx
        while len(picked) < k and (lo_i >= 0 or hi_i < len(cands)):
            candidates = []
            if lo_i >= 0:
                candidates.append((abs(keys[lo_i] - target), lo_i))
            if hi_i < len(cands):
                candidates.append((abs(keys[hi_i] - target), hi_i))
            candidates.sort()
            if not candidates or candidates[0][0] > caliper:
                break
            _, i = candidates[0]
            picked.append(cands[i])
            if i == lo_i:
                lo_i -= 1
            else:
                hi_i += 1
        for b in picked:
            pairs.append((s, b))
    return pairs


def main() -> int:
    csv_dir = market_csv_dir()
    all_events: list[dict[str, Any]] = []
    for p in sorted(csv_dir.glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < MIN_BARS:
            continue
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_bars(p)
        all_events.extend(build_events(df, symbol, prefix))

    ev = pd.DataFrame(all_events)
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    ev.to_parquet(out_dir / "stage2_events.parquet", index=False)

    spike = ev[ev["group"] == "spike"].to_dict("records")
    base = ev[ev["group"] == "baseline"].to_dict("records")
    print(f"spike={len(spike)} base={len(base)}")

    # ATR 分布
    print("\nATR percentile by group:")
    print(ev.groupby("group")["atr_pct"].describe())

    fields = []
    for h in HORIZONS:
        fields.extend([f"sigma_h{h}", f"absr_h{h}", f"r_h{h}"])

    # 1) 未匹配的 Δ with bootstrap
    raw_results = {}
    pvals = []
    for f in fields:
        ms, ls, hs = boot_mean(spike, f, BOOT_SEED)
        mb, lb, hb = boot_mean(base, f, BOOT_SEED + 1)
        # 独立 bootstrap 差
        # 用 cluster_bootstrap 直接在合并数据上做组差
        def stat_diff(evts: list[dict[str, Any]]) -> float:
            s_vals = [e[f] for e in evts if e["group"] == "spike" and math.isfinite(e.get(f, float("nan")))]
            b_vals = [e[f] for e in evts if e["group"] == "baseline" and math.isfinite(e.get(f, float("nan")))]
            return float(np.mean(s_vals) - np.mean(b_vals)) if s_vals and b_vals else float("nan")

        # 为了高效，直接复用 spike/base 各自 bootstrap samples 差
        # boot_mean 只返回 ci，需要重新跑一次取 samples
        s_clean = [e for e in spike if math.isfinite(e.get(f, float("nan")))]
        b_clean = [e for e in base if math.isfinite(e.get(f, float("nan")))]
        if not s_clean or not b_clean:
            continue
        r_s = cluster_bootstrap(
            s_clean,
            cluster_key,
            lambda evts: float(np.mean([x[f] for x in evts])),
            n_boot=N_BOOT, seed=BOOT_SEED,
        )
        r_b = cluster_bootstrap(
            b_clean,
            cluster_key,
            lambda evts: float(np.mean([x[f] for x in evts])),
            n_boot=N_BOOT, seed=BOOT_SEED + 1,
        )
        diff = np.array(r_s.samples) - np.array(r_b.samples)
        ds = np.sort(diff)
        lo = float(ds[int(0.025 * N_BOOT)])
        hi = float(ds[int(0.975 * N_BOOT)])
        p = float(min(1.0, 2.0 * min((diff <= 0).mean(), (diff >= 0).mean())))
        raw_results[f] = {
            "mean_spike": r_s.point_estimate,
            "mean_base": r_b.point_estimate,
            "delta": r_s.point_estimate - r_b.point_estimate,
            "ci_lo": lo, "ci_hi": hi, "p_two": p,
        }
        pvals.append((f, p))

    fdr_pass = bh_fdr(pvals, q=0.10)
    for f in raw_results.values():
        pass

    print("\n=== Raw Δ + BH-FDR ===")
    print(f"{'metric':<14}{'Δ':>12}{'CI_lo':>12}{'CI_hi':>12}{'p':>8}{'FDR':>6}")
    for f in fields:
        r = raw_results.get(f)
        if not r:
            continue
        ok = "✓" if fdr_pass.get(f, False) else "·"
        print(f"{f:<14}{r['delta']:>12.6f}{r['ci_lo']:>12.6f}{r['ci_hi']:>12.6f}{r['p_two']:>8.4f}{ok:>6}")

    # 2) ATR 二维拆分
    ev["atr_bucket"] = ev["atr_pct"].apply(atr_bucket)
    split_results: dict[str, dict[str, Any]] = {}
    print("\n=== ATR bucket × group (σ_h6 / |r|_h6) ===")
    for f in ("sigma_h6", "absr_h6"):
        split_results[f] = {}
        print(f"\n  {f}:")
        for ab in ("low", "mid", "high"):
            s = ev[(ev["group"] == "spike") & (ev["atr_bucket"] == ab)].to_dict("records")
            b = ev[(ev["group"] == "baseline") & (ev["atr_bucket"] == ab)].to_dict("records")
            if len(s) < 5 or len(b) < 5:
                print(f"    {ab:<4}: n_spike={len(s)} n_base={len(b)} (too small)")
                continue
            ms, _, _ = boot_mean(s, f, BOOT_SEED)
            mb, _, _ = boot_mean(b, f, BOOT_SEED + 1)
            # diff CI
            r_s = cluster_bootstrap(
                [e for e in s if math.isfinite(e.get(f, float("nan")))],
                cluster_key,
                lambda evts: float(np.mean([x[f] for x in evts])),
                n_boot=N_BOOT, seed=BOOT_SEED,
            )
            r_b = cluster_bootstrap(
                [e for e in b if math.isfinite(e.get(f, float("nan")))],
                cluster_key,
                lambda evts: float(np.mean([x[f] for x in evts])),
                n_boot=N_BOOT, seed=BOOT_SEED + 1,
            )
            diff = np.array(r_s.samples) - np.array(r_b.samples)
            ds = np.sort(diff)
            lo = float(ds[int(0.025 * N_BOOT)])
            hi = float(ds[int(0.975 * N_BOOT)])
            p = float(min(1.0, 2 * min((diff <= 0).mean(), (diff >= 0).mean())))
            split_results[f][ab] = {
                "n_spike": len(s), "n_base": len(b),
                "mean_spike": ms, "mean_base": mb,
                "delta": ms - mb, "ci_lo": lo, "ci_hi": hi, "p_two": p,
            }
            print(
                f"    {ab:<4}: n_s={len(s):>4} n_b={len(b):>4} "
                f"spike={ms:.5f} base={mb:.5f} Δ={ms-mb:+.5f} "
                f"CI=[{lo:+.5f},{hi:+.5f}] p={p:.3f}"
            )

    # 3) ATR 最近邻匹配
    pairs = match_baseline(spike, base, caliper=CALIPER, k=MATCH_PER_SPIKE)
    print(f"\n=== ATR 1:{MATCH_PER_SPIKE} matched pairs (caliper={CALIPER}) ===")
    print(f"total pairs: {len(pairs)} (from {len(spike)} spikes)")
    matched_results = {}
    print(f"{'metric':<14}{'Δ':>12}{'CI_lo':>12}{'CI_hi':>12}{'p':>8}")
    for f in fields:
        r = boot_paired_diff(pairs, f, BOOT_SEED + 2)
        matched_results[f] = r
        if "delta" in r:
            print(
                f"{f:<14}{r['delta']:>12.6f}{r['ci_lo']:>12.6f}"
                f"{r['ci_hi']:>12.6f}{r['p_two']:>8.4f}"
            )

    summary = {
        "n_spike": len(spike),
        "n_base": len(base),
        "raw": raw_results,
        "fdr_pass": fdr_pass,
        "atr_split": split_results,
        "matched": matched_results,
        "caliper": CALIPER,
        "match_per_spike": MATCH_PER_SPIKE,
    }
    (out_dir / "stage2_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n[OK] stage2_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
