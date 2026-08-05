"""
1h 口径调整实验：尝试让 1h 成交量也携带信息。

1h 原始口径的问题：
1. N=20 短窗 σ 噪声大，N=60/120 同时段 z 下效应消失；
2. z-score 混入了"近期低波动"状态；
3. 1h 的 20 根 bar（~4 天）对反转机制可能太短。

测试的调整口径：
A. Volume ratio: V_t / median(V_{t-N..t-1})，不用 σ，对离群值稳健；
B. 长 N 同时段 z: N=60, 120，后窗拉长到 H=60/120（~2-4 周）；
C. 百分位 rank: V_t 在过去 N 根的百分位（非参数，不依赖分布）；
D. 量价配合：放量 + 价格涨幅（spike bar return 大）联合条件；
E. 日级聚合后的 1h 确认：日线 spike 日里的 1h 分布。

每个口径都测 spike vs baseline 的 r^H 均值差，cluster bootstrap by (symbol, session_date)。
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from workspace.common.symbol_utils import extract_contract_prefix  # noqa
from workspace.data.output_paths import market_csv_dir  # noqa

ATR_PERIOD = 14
MIN_BARS = 420
N_BOOT = 2000


def load_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    hi, lo, cl = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pcl = np.concatenate([[cl[0]], cl[:-1]])
    tr = np.maximum.reduce([hi - lo, np.abs(hi - pcl), np.abs(lo - pcl)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["lr"] = np.log(df.close).diff()
    df["session_date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour
    return df


def make_factor(df: pd.DataFrame, kind: str, N: int) -> pd.Series:
    v = df.volume
    hour = df.hour
    if kind == "z_by_hour":
        mu = (v.groupby(hour).shift(1).groupby(hour)
                .transform(lambda s: s.rolling(N, min_periods=N).mean()))
        sd = (v.groupby(hour).shift(1).groupby(hour)
                .transform(lambda s: s.rolling(N, min_periods=N).std(ddof=1)))
        return (v - mu) / sd
    if kind == "z_global":
        mu = v.shift(1).rolling(N, min_periods=N).mean()
        sd = v.shift(1).rolling(N, min_periods=N).std(ddof=1)
        return (v - mu) / sd
    if kind == "ratio_by_hour":
        med = (v.groupby(hour).shift(1).groupby(hour)
                 .transform(lambda s: s.rolling(N, min_periods=N).median()))
        return v / med
    if kind == "ratio_global":
        med = v.shift(1).rolling(N, min_periods=N).median()
        return v / med
    if kind == "pctrank_by_hour":
        # 过去 N 根同时段里 V_t 的百分位
        def pct_rank(s: pd.Series) -> pd.Series:
            return s.rolling(N, min_periods=N).apply(
                lambda x: (x.iloc[-1] >= x).mean(), raw=False
            )
        return v.groupby(hour).shift(1).groupby(hour).transform(pct_rank)
    raise ValueError(kind)


def scan(kind: str, N: int, H: int, thresh: float,
         direction: str = "high",
         require_price: str | None = None,
         price_thresh: float = 1.0) -> dict:
    """扫描一个口径。direction='high' 取因子≥thresh，'low' 取≤thresh。
    require_price: None/'up'/'down'/'big'，要求 spike bar 收益满足条件（ATR 单位）。
    返回 spike vs baseline 的 r^H 差、cluster bootstrap CI。
    """
    N = int(N); H = int(H); thresh = float(thresh)
    spike_vals = []
    base_vals = []
    spike_clusters = []
    base_clusters = []
    cluster_id = 0
    cluster_map = {}

    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < MIN_BARS:
            continue
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_df(p)
        df["f"] = make_factor(df, kind, N)
        r = df.lr.to_numpy()
        f = df.f.to_numpy()
        atr = df.atr.to_numpy()
        sess = df.session_date.to_numpy()
        n = len(df)
        for t in range(max(N, H) + 1, n - H):
            fv = f[t]
            if not math.isfinite(fv):
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            post = r[t + 1:t + 1 + H]
            if not np.all(np.isfinite(post)):
                continue
            rh = float(post.sum())
            # price condition: spike bar 振幅/收益占 ATR 比例
            spike_ret_atr = abs(r[t]) / a if math.isfinite(r[t]) and a > 0 else 0
            if require_price == "up" and r[t] <= price_thresh * a:
                continue
            if require_price == "down" and r[t] >= -price_thresh * a:
                continue
            if require_price == "big" and spike_ret_atr < price_thresh:
                continue

            is_spike = fv >= thresh if direction == "high" else fv <= thresh
            is_base = abs(fv) < 0.5 if kind.startswith("z") else (
                (fv >= 0.9) & (fv <= 1.1) if "ratio" in kind else (fv > 0.4) & (fv < 0.6)
            )
            if is_spike:
                spike_vals.append(rh)
                key = (symbol, str(sess[t]))
                if key not in cluster_map:
                    cluster_map[key] = cluster_id
                    cluster_id += 1
                spike_clusters.append(cluster_map[key])
            elif is_base:
                base_vals.append(rh)
                key = (symbol, str(sess[t]))
                if key not in cluster_map:
                    cluster_map[key] = cluster_id
                    cluster_id += 1
                base_clusters.append(cluster_map[key])

    s = np.array(spike_vals)
    b = np.array(base_vals)
    cs = np.array(spike_clusters, dtype=np.int32)
    cb = np.array(base_clusters, dtype=np.int32)
    if len(s) < 10 or len(b) < 30:
        return {"n_spike": int(len(s)), "n_base": int(len(b)), "skip": True}

    # cluster bootstrap diff
    def boot_mean(vals, cid):
        nc = int(cid.max()) + 1
        sums = np.bincount(cid, weights=vals, minlength=nc)
        cnt = np.bincount(cid, minlength=nc).astype(np.float64)
        rng = np.random.default_rng(42)
        idx = rng.integers(0, nc, size=(N_BOOT, nc))
        return sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    bs_dist = boot_mean(s, cs)
    bb_dist = boot_mean(b, cb)
    diff = bs_dist - bb_dist
    p = float(min(1, 2 * min((diff <= 0).mean(), (diff >= 0).mean())))
    return {
        "n_spike": int(len(s)),
        "n_base": int(len(b)),
        "mean_spike": float(s.mean()),
        "mean_base": float(b.mean()),
        "delta": float(s.mean() - b.mean()),
        "ci_lo": float(np.quantile(diff, 0.025)),
        "ci_hi": float(np.quantile(diff, 0.975)),
        "p_two": p,
        "n_clusters_spike": int(len(np.unique(cs))),
    }


def main():
    out = {}
    print(f"{'kind':<22} {'N':>4} {'H':>4} {'thresh':>8} {'filter':>8} "
          f"{'n_s':>6} {'Δr^H':>10} {'CI':>22} {'p':>6}")
    configs = [
        # A. volume ratio
        ("ratio_by_hour", 20, 20, 1.5, None),
        ("ratio_by_hour", 20, 20, 2.0, None),
        ("ratio_by_hour", 20, 20, 3.0, None),
        ("ratio_global", 20, 20, 2.0, None),
        ("ratio_global", 60, 20, 2.0, None),
        # B. 长 N 同时段 z + 长后窗
        ("z_by_hour", 60, 20, 2.0, None),
        ("z_by_hour", 60, 60, 2.0, None),
        ("z_by_hour", 120, 20, 2.0, None),
        ("z_by_hour", 120, 60, 2.0, None),
        ("z_by_hour", 120, 120, 2.0, None),
        # C. percentile
        ("pctrank_by_hour", 60, 20, 0.95, None),
        ("pctrank_by_hour", 60, 60, 0.95, None),
        ("pctrank_by_hour", 120, 60, 0.95, None),
        # D. 量价配合：z≥2 + spike bar |return|≥1 ATR
        ("z_by_hour", 20, 20, 2.0, "big"),
        ("z_by_hour", 20, 20, 2.0, "up"),
        ("z_by_hour", 20, 20, 2.0, "down"),
        ("z_by_hour", 60, 60, 2.0, "big"),
        ("z_by_hour", 60, 60, 2.0, "up"),
        ("z_by_hour", 60, 60, 2.0, "down"),
        # ratio + price
        ("ratio_by_hour", 60, 60, 2.0, "big"),
        ("ratio_by_hour", 60, 60, 2.0, "up"),
        ("ratio_by_hour", 60, 60, 2.0, "down"),
    ]
    for kind, N, H, thresh, pf in configs:
        r = scan(kind, N, H, thresh, require_price=pf)
        key = f"{kind}_N{N}_H{H}_t{thresh}_{pf or 'none'}"
        out[key] = r
        if r.get("skip"):
            print(f"{kind:<22} {N:>4} {H:>4} {thresh:>8} {str(pf):>8} {r['n_spike']:>6} SKIP")
            continue
        ci = f"[{r['ci_lo']:+.5f},{r['ci_hi']:+.5f}]"
        print(f"{kind:<22} {N:>4} {H:>4} {thresh:>8} {str(pf):>8} "
              f"{r['n_spike']:>6} {r['delta']:>+10.5f} {ci:>22} {r['p_two']:>6.3f}")

    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    (out_dir / "1h_calibration.json").write_text(json.dumps(out, indent=2))
    print(f"\n[OK] {out_dir / '1h_calibration.json'}")


if __name__ == "__main__":
    main()
