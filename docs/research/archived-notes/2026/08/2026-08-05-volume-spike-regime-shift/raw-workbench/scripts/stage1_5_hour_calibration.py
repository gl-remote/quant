"""
文件级元信息：
- 创建背景：Stage 1 发现 r1 全时段 trailing z 被开盘 bar 主导（41.7% spike 在 21h），
  需要去时段化口径验证是否仍有制度差异。
- 用途：同时段 z-score（每个 hour-of-day 用历史同一时段的 N=20 bar 估 mean/std）
  + 剔除开盘 bar 的稳健性变体，重算 Stage 1 全部度量。
- 注意事项：
  * 同时段 rolling 要求样本按 hour-of-day 分组后再 rolling，不是简单全时段 rolling。
  * 剔除开盘 bar 变体：hour not in {9, 21}（日盘/夜盘开盘）；14:00 下午开盘保留（样本看属于盘中节奏）。
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
from workspace.research.hurst import hurst_rs  # noqa: E402

LOOKBACK_N = 20
ATR_PERIOD = 14
Z0_MAIN = 2.0
Z_BASELINE = 0.5
HORIZONS = (1, 3, 6, 12, 20)
N_BOOT = 5000
BOOT_SEED = 20260805
MIN_BARS = 420
OPEN_HOURS = {9, 21}  # 日盘/夜盘开盘；14:00 下午开盘按盘中节奏处理

BARRIERS = {
    "R1_sym": (1.0, 1.0),
    "R2_trend": (1.0, 2.0),
    "R05_rev": (2.0, 1.0),
}


def load_bars(csv_path: Path, z_mode: str) -> pd.DataFrame:
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
    if z_mode == "full":
        mu = v.shift(1).rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean()
        sd = v.shift(1).rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1)
    elif z_mode == "by_hour":
        # 按 hour-of-day 分组做 trailing rolling
        mu = v.groupby(df["hour"]).shift(1).groupby(df["hour"]).transform(
            lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean()
        )
        sd = v.groupby(df["hour"]).shift(1).groupby(df["hour"]).transform(
            lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1)
        )
    else:
        raise ValueError(z_mode)
    df["z"] = (v - mu) / sd
    return df


def _barrier_hit(
    highs: np.ndarray,
    lows: np.ndarray,
    entry_price: float,
    entry_atr: float,
    k_s: float,
    k_t: float,
    side: int,
    h: int,
) -> int:
    if not (math.isfinite(entry_atr) and entry_atr > 0):
        return 0
    up = entry_price + k_t * entry_atr
    dn = entry_price - k_s * entry_atr
    for j in range(h):
        hi = highs[j]
        lo = lows[j]
        if side == 1:
            stop = lo <= dn
            take = hi >= up
        else:
            stop = hi >= up
            take = lo <= dn
        if stop:
            return 0
        if take:
            return 1
    return 0


def build_event_table(df: pd.DataFrame, symbol: str, prefix: str, drop_open: bool) -> list[dict[str, Any]]:
    n = len(df)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    atr = df["atr"].to_numpy()
    log_ret = df["log_ret"].to_numpy()
    z_arr = df["z"].to_numpy()
    hour_arr = df["hour"].to_numpy()
    sd_arr = df["session_date"].to_numpy()
    rng = np.random.default_rng(BOOT_SEED ^ abs(hash(symbol)) % (2**32))

    out: list[dict[str, Any]] = []
    for t in range(LOOKBACK_N * 24 + ATR_PERIOD, n - max(HORIZONS)):
        z = z_arr[t]
        if not math.isfinite(z):
            continue
        if drop_open and int(hour_arr[t]) in OPEN_HOURS:
            continue
        if z >= Z0_MAIN:
            grp = "spike"
        elif abs(z) < Z_BASELINE:
            grp = "baseline"
        else:
            continue
        entry_price = float(close[t])
        entry_atr = float(atr[t])
        r_t = float(log_ret[t]) if math.isfinite(log_ret[t]) else 0.0
        d_t = 1.0 if r_t >= 0 else -1.0
        rand_side = 1 if rng.random() < 0.5 else -1

        rec: dict[str, Any] = {
            "symbol": symbol,
            "prefix": prefix,
            "session_date": sd_arr[t],
            "t": t,
            "z": float(z),
            "group": grp,
            "hour": int(hour_arr[t]),
            "r_t": r_t,
        }
        for h in HORIZONS:
            fut = log_ret[t + 1 : t + 1 + h]
            rec[f"r_h{h}"] = float(np.nansum(fut))
            rec[f"sigma_h{h}"] = float(np.nanstd(fut, ddof=1)) if len(fut) > 1 else float("nan")
            rec[f"absr_h{h}"] = float(np.nanmean(np.abs(fut)))
            rec[f"signed_r_h{h}"] = d_t * rec[f"r_h{h}"]
            for bname, (ks, kt) in BARRIERS.items():
                for side_name, side_val in (
                    ("long", 1),
                    ("short", -1),
                    ("random", rand_side),
                ):
                    rec[f"hit_{bname}_{side_name}_h{h}"] = float(
                        _barrier_hit(
                            high[t + 1 : t + 1 + h],
                            low[t + 1 : t + 1 + h],
                            entry_price,
                            entry_atr,
                            ks,
                            kt,
                            side_val,
                            h,
                        )
                    )
            if h == 20:
                seq = fut[np.isfinite(fut)]
                try:
                    rec["H_h20"] = (
                        float(hurst_rs(seq, min_window=4, max_window=8))
                        if len(seq) >= 16
                        else float("nan")
                    )
                except ValueError:
                    rec["H_h20"] = float("nan")
        out.append(rec)
    return out


def _cluster_key(e: dict[str, Any]) -> tuple[str, object]:
    return (str(e["symbol"]), e["session_date"])


def boot_diff(spike: list[dict], base: list[dict], field: str) -> dict[str, float]:
    s = [e for e in spike if math.isfinite(e.get(field, float("nan")))]
    b = [e for e in base if math.isfinite(e.get(field, float("nan")))]
    if not s or not b:
        return {"n_spike": len(s), "n_base": len(b)}

    def stat(evts: list[dict]) -> float:
        return float(np.mean([x[field] for x in evts]))

    r_s = cluster_bootstrap(s, _cluster_key, stat, n_boot=N_BOOT, seed=BOOT_SEED)
    r_b = cluster_bootstrap(b, _cluster_key, stat, n_boot=N_BOOT, seed=BOOT_SEED + 1)
    diff = np.array(r_s.samples) - np.array(r_b.samples)
    ds = np.sort(diff)
    lo = float(ds[int(0.025 * N_BOOT)])
    hi = float(ds[int(0.975 * N_BOOT)])
    p = 2.0 * min((diff <= 0).mean(), (diff >= 0).mean())
    return {
        "n_spike": len(s),
        "n_base": len(b),
        "mean_spike": r_s.point_estimate,
        "mean_base": r_b.point_estimate,
        "delta": r_s.point_estimate - r_b.point_estimate,
        "ci_lo": lo,
        "ci_hi": hi,
        "p_two": float(min(p, 1.0)),
    }


def retention(spike: list[dict], base: list[dict], field: str) -> tuple[float, dict[str, float]]:
    by_s: dict[str, list[float]] = {}
    by_b: dict[str, list[float]] = {}
    for e in spike:
        v = e.get(field, float("nan"))
        if math.isfinite(v):
            by_s.setdefault(e["prefix"], []).append(v)
    for e in base:
        v = e.get(field, float("nan"))
        if math.isfinite(v):
            by_b.setdefault(e["prefix"], []).append(v)
    deltas = {}
    for pfx, vs in by_s.items():
        vb = by_b.get(pfx)
        if vb:
            deltas[pfx] = float(np.mean(vs) - np.mean(vb))
    if not deltas:
        return float("nan"), {}
    s_all = [x for lst in by_s.values() for x in lst]
    b_all = [x for lst in by_b.values() for x in lst]
    sign = np.sign(np.mean(s_all) - np.mean(b_all))
    if sign == 0:
        return float("nan"), deltas
    return float(sum(1 for d in deltas.values() if np.sign(d) == sign) / len(deltas)), deltas


def run(z_mode: str, drop_open: bool) -> dict[str, Any]:
    csv_dir = market_csv_dir()
    files = sorted(csv_dir.glob("*.1h.csv"))
    all_events: list[dict[str, Any]] = []
    contract_count = 0
    for p in files:
        try:
            df_head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(df_head) < MIN_BARS:
            continue
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_bars(p, z_mode)
        evs = build_event_table(df, symbol, prefix, drop_open)
        all_events.extend(evs)
        contract_count += 1
    ev_df = pd.DataFrame(all_events)
    spike = ev_df[ev_df["group"] == "spike"].to_dict("records")
    base = ev_df[ev_df["group"] == "baseline"].to_dict("records")

    fields = []
    for h in HORIZONS:
        fields.extend([f"r_h{h}", f"sigma_h{h}", f"absr_h{h}", f"signed_r_h{h}"])
        for bname in BARRIERS:
            for d in ("long", "short", "random"):
                fields.append(f"hit_{bname}_{d}_h{h}")
    fields.append("H_h20")

    results = {}
    for f in fields:
        r = boot_diff(spike, base, f)
        ret, deltas = retention(spike, base, f)
        r["retention"] = ret
        r["prefix_deltas"] = deltas
        results[f] = r

    hour_spike = (
        ev_df[ev_df["group"] == "spike"]["hour"].value_counts(normalize=True).sort_index().to_dict()
    )

    return {
        "z_mode": z_mode,
        "drop_open": drop_open,
        "n_contracts": contract_count,
        "n_spike": len(spike),
        "n_base": len(base),
        "n_clusters_spike": len({(e["symbol"], e["session_date"]) for e in spike}),
        "n_clusters_base": len({(e["symbol"], e["session_date"]) for e in base}),
        "hour_dist_spike": {str(k): float(v) for k, v in hour_spike.items()},
        "metrics": results,
    }


def print_core(res: dict[str, Any]) -> None:
    tag = f"{res['z_mode']}{'_drop_open' if res['drop_open'] else ''}"
    print(
        f"\n========== {tag} ==========\n"
        f"contracts={res['n_contracts']} spike={res['n_spike']} (clusters={res['n_clusters_spike']}) "
        f"base={res['n_base']} (clusters={res['n_clusters_base']})"
    )
    print("spike hour-of-day (top 5):")
    for h, v in sorted(res["hour_dist_spike"].items(), key=lambda x: -x[1])[:5]:
        print(f"  {h}h: {v:.2%}")

    print("\nCore continuous metrics:")
    print(f"{'metric':<18} {'Δ':>10} {'CI_lo':>10} {'CI_hi':>10} {'p':>7} {'ret':>5}")
    for h in HORIZONS:
        for f in (f"r_h{h}", f"sigma_h{h}", f"absr_h{h}", f"signed_r_h{h}"):
            r = res["metrics"][f]
            if "delta" not in r:
                continue
            print(
                f"{f:<18} {r['delta']:>10.5f} {r['ci_lo']:>10.5f} "
                f"{r['ci_hi']:>10.5f} {r['p_two']:>7.3f} {r['retention']:>5.2f}"
            )
    if "H_h20" in res["metrics"] and "delta" in res["metrics"]["H_h20"]:
        r = res["metrics"]["H_h20"]
        print(f"{'H_h20':<18} {r['delta']:>10.5f} {r['ci_lo']:>10.5f} {r['ci_hi']:>10.5f} {r['p_two']:>7.3f}")

    print("\nLong barrier hits:")
    for h in HORIZONS:
        for b in BARRIERS:
            f = f"hit_{b}_long_h{h}"
            r = res["metrics"][f]
            if "delta" not in r:
                continue
            sig = "*" if r["p_two"] < 0.05 else " "
            print(
                f"  {f:<28} Δ={r['delta']:+.4f} CI=[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] "
                f"p={r['p_two']:.3f}{sig}"
            )


def main() -> int:
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    out_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("full", False),       # r1 原始口径（作为对照应复现 Stage 1）
        ("by_hour", False),    # v2 同时段 z
        ("by_hour", True),     # v2 同时段 z + 剔除开盘
    ]
    all_res = {}
    for z_mode, drop_open in configs:
        r = run(z_mode, drop_open)
        key = f"{z_mode}{'_drop_open' if drop_open else ''}"
        all_res[key] = r
        print_core(r)

    (out_dir / "stage1_5_calibration.json").write_text(
        json.dumps(all_res, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n[OK] wrote stage1_5_calibration.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
