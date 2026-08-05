"""
文件级元信息：
- 创建背景：volume-spike-regime-shift 主题 Stage 1 广度扫描。
- 用途：在 26 个 1h 合约上，对 z0=2.0 spike 组 vs |Z|<0.5 baseline 组，
  计算后窗 h∈{1,3,6,12,20} 的 6 类条件度量（r/sigma/|r|/barrier hit×3/H20），
  输出事件长表 + 聚合表（含 cluster bootstrap CI、prefix 保留率、hour-of-day 诊断）。
- 注意事项：
  * 不计成本（Stage 5 才加）；不做方向选择（Stage 2 才拆）。
  * 每合约独立 rolling，不跨合约池化（KF-22）。
  * cluster key = (symbol, session_date)。
  * 临时研究脚本，产物在 project_data/research/volume-spike-regime-shift/。
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
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

# ───────── 常量 ─────────
LOOKBACK_N = 20
ATR_PERIOD = 14
Z0_MAIN = 2.0
Z_BASELINE = 0.5
HORIZONS = (1, 3, 6, 12, 20)
N_BOOT = 5000
BOOT_SEED = 20260805
MIN_BARS = 420

# barrier: (k_s, k_t) in ATR units
BARRIERS = {
    "R1_sym": (1.0, 1.0),
    "R2_trend": (1.0, 2.0),
    "R05_rev": (2.0, 1.0),
}
BAR_DIRECTIONS = ("long", "short", "random")

ACCEPTED_SYMBOLS_KEY = "accepted"  # 由 stage0 audit 决定；这里直接重读目录并过滤


# ───────── 数据加载 ─────────
def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["atr"] = atr

    # log return
    df["log_ret"] = np.log(df["close"]).diff()

    # volume z-score (trailing, excluding current)
    v = df["volume"]
    mu = v.shift(1).rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean()
    sd = v.shift(1).rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1)
    df["z"] = (v - mu) / sd

    df["session_date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    return df


# ───────── 后窗度量 ─────────
def _barrier_hit(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    entry_price: float,
    entry_atr: float,
    k_s: float,
    k_t: float,
    side: int,
    h: int,
) -> tuple[int, int, str]:
    """逐 bar 判断 stop/take。返回 (hit_take, bars_held, reason)。

    side=+1 多头：take=entry+k_t*atr 上触，stop=entry-k_s*atr 下触；
    side=-1 空头反之；同 bar 双触保守按 stop 计。
    """
    if not (math.isfinite(entry_atr) and entry_atr > 0):
        return 0, h, "no_atr"
    up = entry_price + k_t * entry_atr
    dn = entry_price - k_s * entry_atr
    for j in range(h):
        hi = highs[j]
        lo = lows[j]
        if side == 1:
            hit_stop = lo <= dn
            hit_take = hi >= up
        else:
            hit_stop = hi >= up  # stop for short: price goes up
            hit_take = lo <= dn
        if hit_stop and hit_take:
            return 0, j + 1, "both_assume_stop"
        if hit_stop:
            return 0, j + 1, "stop"
        if hit_take:
            return 1, j + 1, "take"
    return 0, h, "time_exit"


@dataclass
class EventRecord:
    symbol: str
    prefix: str
    session_date: object
    t: int
    z: float
    group: str  # 'spike' | 'baseline'
    r_t: float
    hour: int


def build_events(df: pd.DataFrame, symbol: str, prefix: str) -> list[EventRecord]:
    out: list[EventRecord] = []
    z_arr = df["z"].to_numpy()
    rt_arr = df["log_ret"].to_numpy()
    hr_arr = df["hour"].to_numpy()
    sd_arr = df["session_date"].to_numpy()
    n = len(df)
    for t in range(LOOKBACK_N + ATR_PERIOD, n):
        z = z_arr[t]
        if not math.isfinite(z):
            continue
        if z >= Z0_MAIN:
            grp = "spike"
        elif abs(z) < Z_BASELINE:
            grp = "baseline"
        else:
            continue
        if t + max(HORIZONS) >= n:
            continue
        out.append(
            EventRecord(
                symbol=symbol,
                prefix=prefix,
                session_date=sd_arr[t],
                t=t,
                z=float(z),
                group=grp,
                r_t=float(rt_arr[t]) if math.isfinite(rt_arr[t]) else 0.0,
                hour=int(hr_arr[t]) if not pd.isna(hr_arr[t]) else -1,
            )
        )
    return out


def event_metrics(
    ev: EventRecord, df: pd.DataFrame, rng: np.random.Generator
) -> dict[str, float]:
    """对单个事件算各 horizon 的响应向量。"""
    t = ev.t
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    atr = df["atr"].to_numpy()
    log_ret = df["log_ret"].to_numpy()
    entry_price = float(close[t])
    entry_atr = float(atr[t])
    # random side per event, fixed across barriers/h
    rand_side = 1 if rng.random() < 0.5 else -1

    out: dict[str, float] = {}
    for h in HORIZONS:
        fut = log_ret[t + 1 : t + 1 + h]
        r_h = float(np.nansum(fut))
        if len(fut) > 1 and np.nanstd(fut) > 0:
            sigma_h = float(np.nanstd(fut, ddof=1))
        else:
            sigma_h = float("nan")
        absr_h = float(np.nanmean(np.abs(fut)))
        out[f"r_h{h}"] = r_h
        out[f"sigma_h{h}"] = sigma_h
        out[f"absr_h{h}"] = absr_h

        # signed response (event bar direction × future return)
        d_t = 1.0 if ev.r_t >= 0 else -1.0
        out[f"signed_r_h{h}"] = d_t * r_h

        # barriers
        for bname, (ks, kt) in BARRIERS.items():
            for side_name, side_val in (
                ("long", 1),
                ("short", -1),
                ("random", rand_side),
            ):
                hit, bars, reason = _barrier_hit(
                    high[t + 1 : t + 1 + h],
                    low[t + 1 : t + 1 + h],
                    close[t + 1 : t + 1 + h],
                    entry_price,
                    entry_atr,
                    ks,
                    kt,
                    side_val,
                    h,
                )
                key = f"hit_{bname}_{side_name}_h{h}"
                out[key] = float(hit)

        # Hurst only at h=20
        if h == 20:
            seq = fut[np.isfinite(fut)]
            if len(seq) >= 16:
                try:
                    out["H_h20"] = float(hurst_rs(seq, min_window=4, max_window=8))
                except ValueError:
                    out["H_h20"] = float("nan")
            else:
                out["H_h20"] = float("nan")

    return out


def _cluster_key(e: dict[str, Any]) -> tuple[str, object]:
    return (str(e["symbol"]), e["session_date"])


def boot_diff(
    spike_events: list[dict[str, Any]],
    base_events: list[dict[str, Any]],
    field: str,
    n_boot: int = N_BOOT,
) -> dict[str, float]:
    """对 spike-baseline 的均值差做 cluster bootstrap。

    两组独立 cluster bootstrap，各自重抽，差 = spike_mean - base_mean。
    """
    s_vals = [e for e in spike_events if math.isfinite(e.get(field, float("nan")))]
    b_vals = [e for e in base_events if math.isfinite(e.get(field, float("nan")))]
    if not s_vals or not b_vals:
        return {"n_spike": len(s_vals), "n_base": len(b_vals)}

    def _stat_mean(evts: list[dict[str, Any]]) -> float:
        return float(np.mean([x[field] for x in evts]))

    r_s = cluster_bootstrap(s_vals, _cluster_key, _stat_mean, n_boot=n_boot, seed=BOOT_SEED)
    r_b = cluster_bootstrap(
        b_vals, _cluster_key, _stat_mean, n_boot=n_boot, seed=BOOT_SEED + 1
    )
    diff_samples = np.array(r_s.samples) - np.array(r_b.samples)
    diff_sorted = np.sort(diff_samples)
    lo = float(diff_sorted[int(0.025 * n_boot)])
    hi = float(diff_sorted[int(0.975 * n_boot)])
    point = r_s.point_estimate - r_b.point_estimate
    # two-sided p
    p = 2.0 * min((diff_samples <= 0).mean(), (diff_samples >= 0).mean())
    return {
        "n_spike": len(s_vals),
        "n_base": len(b_vals),
        "mean_spike": r_s.point_estimate,
        "mean_base": r_b.point_estimate,
        "delta": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "p_two": float(min(p, 1.0)),
    }


def retention_by_prefix(
    spike_events: list[dict[str, Any]],
    base_events: list[dict[str, Any]],
    field: str,
) -> tuple[float, dict[str, float]]:
    """对每个 prefix 算 Δ；返回整体 sign 一致保留率 + 分 prefix delta。"""
    by_s: dict[str, list[float]] = {}
    by_b: dict[str, list[float]] = {}
    for e in spike_events:
        v = e.get(field, float("nan"))
        if math.isfinite(v):
            by_s.setdefault(e["prefix"], []).append(v)
    for e in base_events:
        v = e.get(field, float("nan"))
        if math.isfinite(v):
            by_b.setdefault(e["prefix"], []).append(v)
    deltas: dict[str, float] = {}
    for pfx in by_s:
        if pfx in by_b and by_s[pfx] and by_b[pfx]:
            deltas[pfx] = float(np.mean(by_s[pfx]) - np.mean(by_b[pfx]))
    if not deltas:
        return float("nan"), {}
    s_all = [v for lst in by_s.values() for v in lst]
    b_all = [v for lst in by_b.values() for v in lst]
    overall_sign = np.sign(np.mean(s_all) - np.mean(b_all))
    if overall_sign == 0:
        return float("nan"), deltas
    consistent = sum(1 for d in deltas.values() if np.sign(d) == overall_sign)
    return consistent / len(deltas), deltas


def main() -> int:
    csv_dir = market_csv_dir()
    files = sorted(csv_dir.glob("*.1h.csv"))

    # 过滤 MIN_BARS
    use_paths: list[tuple[str, str, Path]] = []
    for p in files:
        try:
            df_head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(df_head) >= MIN_BARS:
            symbol = p.name.split(".tqsdk.1h.csv")[0]
            prefix = extract_contract_prefix(symbol) or ""
            use_paths.append((symbol, prefix, p))

    print(f"[INFO] {len(use_paths)} contracts eligible (n_bars>={MIN_BARS})")

    rng = np.random.default_rng(BOOT_SEED)
    all_events: list[dict[str, Any]] = []
    hour_spike: list[int] = []
    hour_base: list[int] = []

    for symbol, prefix, p in use_paths:
        df = load_bars(p)
        evs = build_events(df, symbol, prefix)
        if not evs:
            continue
        for ev in evs:
            m = event_metrics(ev, df, rng)
            rec = {
                "symbol": symbol,
                "prefix": prefix,
                "session_date": ev.session_date,
                "t": ev.t,
                "z": ev.z,
                "group": ev.group,
                "r_t": ev.r_t,
                "hour": ev.hour,
                **m,
            }
            all_events.append(rec)
            if ev.group == "spike":
                hour_spike.append(ev.hour)
            else:
                hour_base.append(ev.hour)
        print(f"  {symbol:14s} bars={len(df)} events={len(evs)}")

    ev_df = pd.DataFrame(all_events)
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    out_dir.mkdir(parents=True, exist_ok=True)
    ev_df.to_parquet(out_dir / "stage1_events.parquet", index=False)
    print(f"[OK] events: {len(ev_df)} -> stage1_events.parquet")

    spike = ev_df[ev_df["group"] == "spike"].to_dict("records")
    base = ev_df[ev_df["group"] == "baseline"].to_dict("records")
    n_clusters_s = len({(e["symbol"], e["session_date"]) for e in spike})
    n_clusters_b = len({(e["symbol"], e["session_date"]) for e in base})
    print(f"[INFO] spike n={len(spike)} clusters={n_clusters_s}")
    print(f"[INFO] base  n={len(base)} clusters={n_clusters_b}")

    # 度量字段列表
    metric_fields: list[str] = []
    for h in HORIZONS:
        metric_fields.extend([f"r_h{h}", f"sigma_h{h}", f"absr_h{h}", f"signed_r_h{h}"])
        for bname in BARRIERS:
            for d in BAR_DIRECTIONS:
                metric_fields.append(f"hit_{bname}_{d}_h{h}")
    metric_fields.append("H_h20")

    # 聚合
    results = {}
    for f in metric_fields:
        r = boot_diff(spike, base, f)
        ret, pfx_deltas = retention_by_prefix(spike, base, f)
        r["retention_prefix"] = ret
        r["prefix_deltas"] = {k: float(v) for k, v in pfx_deltas.items()}
        results[f] = r

    # hour 分布
    def _hist(arr: list[int]) -> dict[str, float]:
        if not arr:
            return {}
        s = pd.Series(arr)
        return {str(int(k)): float(v) for k, v in s.value_counts(normalize=True).sort_index().items()}

    summary = {
        "z0": Z0_MAIN,
        "baseline_abs_z": Z_BASELINE,
        "horizons": list(HORIZONS),
        "n_spike": len(spike),
        "n_base": len(base),
        "n_clusters_spike": n_clusters_s,
        "n_clusters_base": n_clusters_b,
        "n_contracts": ev_df["symbol"].nunique(),
        "n_prefixes": ev_df["prefix"].nunique(),
        "hour_dist_spike": _hist(hour_spike),
        "hour_dist_base": _hist(hour_base),
        "metrics": results,
    }
    (out_dir / "stage1_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )
    print(f"[OK] summary -> stage1_summary.json")

    # ───── 控制台简表 ─────
    print("\n=== Core metrics: Δ(spike-baseline), 95% cluster bootstrap CI ===")
    print(
        f"{'metric':<22} {'Δ':>10} {'CI_lo':>10} {'CI_hi':>10} "
        f"{'p':>8} {'retent':>7} {'n_spk':>7} {'n_base':>7}"
    )
    for h in HORIZONS:
        for key in (f"r_h{h}", f"sigma_h{h}", f"absr_h{h}", f"signed_r_h{h}"):
            r = results[key]
            if "delta" not in r:
                continue
            print(
                f"{key:<22} {r['delta']:>10.5f} {r['ci_lo']:>10.5f} {r['ci_hi']:>10.5f} "
                f"{r['p_two']:>8.3f} {r['retention_prefix']:>7.2f} "
                f"{r['n_spike']:>7d} {r['n_base']:>7d}"
            )

    print("\n=== Barrier hit (long side) Δ ===")
    for h in HORIZONS:
        for bname in BARRIERS:
            key = f"hit_{bname}_long_h{h}"
            r = results[key]
            if "delta" not in r:
                continue
            print(
                f"{key:<30} Δ={r['delta']:+.4f} CI=[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] "
                f"p={r['p_two']:.3f} retent={r['retention_prefix']:.2f}"
            )

    h_key = "H_h20"
    if h_key in results and "delta" in results[h_key]:
        r = results[h_key]
        print(
            f"\n=== Hurst h20 ===\n  spike={r['mean_spike']:.3f} base={r['mean_base']:.3f} "
            f"Δ={r['delta']:+.4f} CI=[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] p={r['p_two']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
