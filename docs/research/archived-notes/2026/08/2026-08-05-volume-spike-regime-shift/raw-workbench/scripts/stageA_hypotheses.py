"""
文件级元信息：
- 创建背景：Stage 3 收敛后，验证四个可立即用现有 1h 数据检验的猜想：
  A1 波动见顶：spike 后未来 20 bar 波动率相对当前回落；
  A2 左尾恶化：spike 后 VaR/ES 显著差于 baseline（即使均值无差异）；
  A3 exhaustion：前涨+放量的下行尾部比前跌+放量更厚（非对称）；
  A4 feature 价值：spike 作为 filter 是否改变固定止损策略的被扫概率。
- 用途：一次性输出四个猜想的点估计 + cluster bootstrap CI，决定哪个值得深化。
- 注意事项：
  * 复用 by-hour z-score 口径与 stage3_paths.parquet 的事件定义；
  * A4 需要重新加载价格并做固定 ATR 止损命中模拟，其他直接用 stage3_paths；
  * cluster = (symbol, session_date)，bootstrap 2000 次。
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

LOOKBACK_N = 20
ATR_PERIOD = 14
Z0_MAIN = 2.0
Z_BASELINE = 0.5
H = 20
MIN_BARS = 420
N_BOOT = 2000
BOOT_SEED = 20260805

OUT_DIR = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"


# ───────── 数据加载（与 stage3 同口径） ─────────
def load_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["lr"] = np.log(df["close"]).diff()
    v = df["volume"]
    hour = df["datetime"].dt.hour
    mu = (
        v.groupby(hour).shift(1).groupby(hour)
        .transform(lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean())
    )
    sd = (
        v.groupby(hour).shift(1).groupby(hour)
        .transform(lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1))
    )
    df["z"] = (v - mu) / sd
    df["session_date"] = df["datetime"].dt.date
    return df


def build_events() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """返回事件表 + 每合约 DataFrame（A4 用）。"""
    recs: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
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
        frames[symbol] = df
        r = df["lr"].to_numpy()
        z = df["z"].to_numpy()
        atr = df["atr"].to_numpy()
        sess = df["session_date"].to_numpy()
        n = len(df)
        for t in range(H, n - H):
            zv = z[t]
            if not math.isfinite(zv):
                continue
            if zv >= Z0_MAIN:
                grp = "spike"
            elif abs(zv) < Z_BASELINE:
                grp = "baseline"
            else:
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            pre = r[t - H : t]
            post = r[t + 1 : t + 1 + H]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))):
                continue
            recs.append({
                "symbol": symbol, "prefix": prefix, "session_date": sess[t], "t": t,
                "group": grp, "z": float(zv),
                "spike_ret": float(r[t]),
                "pre_cum": float(pre.sum()),
                "post_cum": float(post.sum()),
                "pre_abs": float(np.abs(pre).mean()),
                "post_abs": float(np.abs(post).mean()),
                "post_path_std": float(np.cumsum(post).std(ddof=1)),
                "entry_atr": float(a),
            })
    ev = pd.DataFrame(recs)
    return ev, frames


# ───────── cluster bootstrap 工具 ─────────
def _cids(df: pd.DataFrame) -> np.ndarray:
    keys = sorted({(s, d) for s, d in zip(df["symbol"], df["session_date"])})
    km = {k: i for i, k in enumerate(keys)}
    return np.array([km[(s, d)] for s, d in zip(df["symbol"], df["session_date"])], dtype=np.int32)


def boot(vals: np.ndarray, cid: np.ndarray, seed: int) -> dict[str, float]:
    nc = int(cid.max()) + 1
    sums = np.bincount(cid, weights=vals, minlength=nc)
    cnt = np.bincount(cid, minlength=nc).astype(np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nc, size=(N_BOOT, nc), dtype=np.int32)
    boot = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    b = np.sort(boot)
    return {
        "point": float(vals.mean()),
        "ci_lo": float(b[int(0.025 * N_BOOT)]),
        "ci_hi": float(b[int(0.975 * N_BOOT)]),
        "n": int(len(vals)),
    }


def boot_diff(s: np.ndarray, b: np.ndarray, cid_s: np.ndarray, cid_b: np.ndarray, seed: int) -> dict[str, float]:
    rs = boot(s, cid_s, seed)
    rb = boot(b, cid_b, seed + 1)
    # 独立 bootstrap 差的 CI：对原始 bootstrap 样本直接相减更精确，这里重新抽样
    nc_s, nc_b = int(cid_s.max()) + 1, int(cid_b.max()) + 1
    sums_s = np.bincount(cid_s, weights=s, minlength=nc_s)
    cnt_s = np.bincount(cid_s, minlength=nc_s).astype(np.float64)
    sums_b = np.bincount(cid_b, weights=b, minlength=nc_b)
    cnt_b = np.bincount(cid_b, minlength=nc_b).astype(np.float64)
    rng = np.random.default_rng(seed + 2)
    idx_s = rng.integers(0, nc_s, size=(N_BOOT, nc_s), dtype=np.int32)
    idx_b = rng.integers(0, nc_b, size=(N_BOOT, nc_b), dtype=np.int32)
    diff = (sums_s[idx_s].sum(axis=1) / cnt_s[idx_s].sum(axis=1)) - (
        sums_b[idx_b].sum(axis=1) / cnt_b[idx_b].sum(axis=1)
    )
    ds = np.sort(diff)
    point = float(s.mean() - b.mean())
    p = float(2 * min((diff <= 0).mean(), (diff >= 0).mean()))
    return {
        "delta": point,
        "ci_lo": float(ds[int(0.025 * N_BOOT)]),
        "ci_hi": float(ds[int(0.975 * N_BOOT)]),
        "p_two": min(p, 1.0),
        "mean_spike": float(s.mean()),
        "mean_base": float(b.mean()),
    }


# ───────── A1: 波动见顶 ─────────
def a1_vol_peak(ev: pd.DataFrame) -> dict[str, Any]:
    """spike 事件的 post_abs / pre_abs，与 baseline 比较；
    理想结果：spike 的 pre_abs 高、post_abs 显著下降，baseline 无此变化。"""
    sp = ev[ev.group == "spike"]
    bs = ev[ev.group == "baseline"]
    cs, cb = _cids(sp), _cids(bs)
    ratio_s = (sp["post_abs"] / sp["pre_abs"]).to_numpy()
    ratio_b = (bs["post_abs"] / bs["pre_abs"]).to_numpy()
    diff_s = (sp["post_abs"] - sp["pre_abs"]).to_numpy()
    diff_b = (bs["post_abs"] - bs["pre_abs"]).to_numpy()
    return {
        "spike_pre_abs": boot(sp["pre_abs"].to_numpy(), cs, 10),
        "spike_post_abs": boot(sp["post_abs"].to_numpy(), cs, 11),
        "base_pre_abs": boot(bs["pre_abs"].to_numpy(), cb, 12),
        "base_post_abs": boot(bs["post_abs"].to_numpy(), cb, 13),
        "ratio_post_pre_spike": boot(ratio_s, cs, 14),
        "ratio_post_pre_base": boot(ratio_b, cb, 15),
        "did_abs_diff": boot_diff(diff_s, diff_b, cs, cb, 16),
    }


# ───────── A2: 左尾 ─────────
def a2_left_tail(ev: pd.DataFrame) -> dict[str, Any]:
    sp = ev[ev.group == "spike"]
    bs = ev[ev.group == "baseline"]
    cs, cb = _cids(sp), _cids(bs)
    s = sp["post_cum"].to_numpy()
    b = bs["post_cum"].to_numpy()
    # 用 bootstrap 分布的 5%/10% 分位估计 VaR，以及 5% 条件均值（ES）
    nc_s = int(cs.max()) + 1
    nc_b = int(cb.max()) + 1
    # 对 cluster bootstrap 样本算每次的 5%/10% 分位与 ES
    def tail_boot(vals: np.ndarray, cid: np.ndarray, seed: int) -> dict[str, Any]:
        nc = int(cid.max()) + 1
        # 按 cluster 重采样得到经验分布，然后在合并样本上算分位（非参数 percentile bootstrap）
        cluster_values = [vals[cid == k] for k in range(nc)]
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, nc, size=(N_BOOT, nc), dtype=np.int32)
        var5, var10, es5, es10, means = [], [], [], [], []
        for i in range(N_BOOT):
            sample = np.concatenate([cluster_values[k] for k in idx[i]])
            var5.append(np.quantile(sample, 0.05))
            var10.append(np.quantile(sample, 0.10))
            es5.append(sample[sample <= np.quantile(sample, 0.05)].mean())
            es10.append(sample[sample <= np.quantile(sample, 0.10)].mean())
            means.append(sample.mean())
        return {
            "var5_point": float(np.quantile(vals, 0.05)),
            "var5_ci": [float(np.quantile(var5, 0.025)), float(np.quantile(var5, 0.975))],
            "var10_point": float(np.quantile(vals, 0.10)),
            "var10_ci": [float(np.quantile(var10, 0.025)), float(np.quantile(var10, 0.975))],
            "es5_point": float(vals[vals <= np.quantile(vals, 0.05)].mean()),
            "es5_ci": [float(np.quantile(es5, 0.025)), float(np.quantile(es5, 0.975))],
            "es10_point": float(vals[vals <= np.quantile(vals, 0.10)].mean()),
            "es10_ci": [float(np.quantile(es10, 0.025)), float(np.quantile(es10, 0.975))],
            "pct_neg": float((vals < 0).mean()),
        }
    return {
        "spike": tail_boot(s, cs, 20),
        "baseline": tail_boot(b, cb, 21),
        "mean_diff": boot_diff(s, b, cs, cb, 22),
    }


# ───────── A3: exhaustion 非对称 ─────────
def a3_exhaustion(ev: pd.DataFrame) -> dict[str, Any]:
    """按 pre_cum 三分位（在 spike 内切）比较 post_cum 与尾部。"""
    sp = ev[ev.group == "spike"].copy()
    bs = ev[ev.group == "baseline"].copy()
    q1, q2 = sp["pre_cum"].quantile([1/3, 2/3])

    def bkt(x: float) -> str:
        if x < q1:
            return "pre_down"
        if x > q2:
            return "pre_up"
        return "pre_flat"

    sp["pre_bkt"] = sp["pre_cum"].apply(bkt)
    bs["pre_bkt"] = bs["pre_cum"].apply(bkt)

    out: dict[str, Any] = {"cutoffs": [float(q1), float(q2)], "by_bucket": {}}
    for b in ("pre_down", "pre_flat", "pre_up"):
        s = sp[sp.pre_bkt == b]
        base = bs[bs.pre_bkt == b]
        cs, cb = _cids(s), _cids(base)
        # post mean / VaR5 / ES5 / max favorable vs adverse (用 post_cum 近似)
        entry = {
            "n_spike": int(len(s)),
            "n_base": int(len(base)),
            "pre_cum_mean": float(s.pre_cum.mean()),
            "post_mean_spike": float(s.post_cum.mean()),
            "post_mean_base": float(base.post_cum.mean()),
            "did_post_cum": boot_diff(
                s["post_cum"].to_numpy(), base["post_cum"].to_numpy(), cs, cb, 30 + hash(b) % 100
            ),
        }
        # spike 内下行比例 / 上行比例
        entry["spike_pct_neg"] = float((s.post_cum < 0).mean())
        entry["spike_pct_pos"] = float((s.post_cum > 0).mean())
        # spike post 5%/95% 分位（非对称幅度）
        entry["spike_p5"] = float(s.post_cum.quantile(0.05))
        entry["spike_p95"] = float(s.post_cum.quantile(0.95))
        entry["spike_down_up_ratio"] = float(abs(entry["spike_p5"]) / max(abs(entry["spike_p95"]), 1e-9))
        out["by_bucket"][b] = entry
    return out


# ───────── A4: feature 价值（固定 ATR 止损命中） ─────────
def a4_feature_stop_hit(ev: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """对 spike/baseline 事件，在 post 20 bar 内模拟 1×ATR 固定止损。
    测两种设定：
      long-only: entry=close[t], stop=entry-1*ATR, 无 take profit；
      short-only: 对称。
    比较 spike vs baseline 的 stop-hit 概率。
    若 spike 后命中显著更高，因子可作为"减仓/拉宽止损"信号。
    """
    out: dict[str, Any] = {}
    for side in ("long", "short"):
        hits_s: list[int] = []
        hits_b: list[int] = []
        cid_s: list[tuple[str, Any]] = []
        cid_b: list[tuple[str, Any]] = []
        bars_s: list[int] = []
        bars_b: list[int] = []
        for _, row in ev.iterrows():
            sym = row["symbol"]
            t = int(row["t"])
            df = frames[sym]
            a = float(row["entry_atr"])
            entry = float(df["close"].iat[t])
            h = df["high"].to_numpy()[t + 1 : t + 1 + H]
            l = df["low"].to_numpy()[t + 1 : t + 1 + H]
            hit = 0
            hit_bar = H
            if side == "long":
                stop = entry - a
                for j in range(H):
                    if l[j] <= stop:
                        hit, hit_bar = 1, j + 1
                        break
            else:
                stop = entry + a
                for j in range(H):
                    if h[j] >= stop:
                        hit, hit_bar = 1, j + 1
                        break
            if row["group"] == "spike":
                hits_s.append(hit)
                bars_s.append(hit_bar)
                cid_s.append((row["symbol"], row["session_date"]))
            else:
                hits_b.append(hit)
                bars_b.append(hit_bar)
                cid_b.append((row["symbol"], row["session_date"]))

        s_arr = np.array(hits_s, dtype=np.float64)
        b_arr = np.array(hits_b, dtype=np.float64)
        cs = np.array([{k: i for i, k in enumerate(sorted(set(cid_s)))}[k] for k in cid_s], dtype=np.int32)
        cb = np.array([{k: i for i, k in enumerate(sorted(set(cid_b)))}[k] for k in cid_b], dtype=np.int32)
        out[side] = {
            "spike_hit_rate": boot(s_arr, cs, 40 if side == "long" else 50),
            "base_hit_rate": boot(b_arr, cb, 41 if side == "long" else 51),
            "did": boot_diff(s_arr, b_arr, cs, cb, 42 if side == "long" else 52),
            "spike_hit_bar_mean": float(np.mean(bars_s)),
            "base_hit_bar_mean": float(np.mean(bars_b)),
        }
    return out


def main() -> int:
    print("Building events...")
    ev, frames = build_events()
    ev.to_parquet(OUT_DIR / "stageA_events.parquet", index=False)
    print(f"events={len(ev)}  spike={(ev.group=='spike').sum()}  base={(ev.group=='baseline').sum()}")

    print("\n=== A1: 波动见顶（post/pre 波动比）===")
    a1 = a1_vol_peak(ev)
    print(f"  spike  pre_abs={a1['spike_pre_abs']['point']:.5f} [{a1['spike_pre_abs']['ci_lo']:.5f},{a1['spike_pre_abs']['ci_hi']:.5f}]")
    print(f"  spike post_abs={a1['spike_post_abs']['point']:.5f} [{a1['spike_post_abs']['ci_lo']:.5f},{a1['spike_post_abs']['ci_hi']:.5f}]")
    print(f"  base   pre_abs={a1['base_pre_abs']['point']:.5f}")
    print(f"  base  post_abs={a1['base_post_abs']['point']:.5f}")
    print(f"  spike post/pre ratio={a1['ratio_post_pre_spike']['point']:.3f} [{a1['ratio_post_pre_spike']['ci_lo']:.3f},{a1['ratio_post_pre_spike']['ci_hi']:.3f}]")
    print(f"  base  post/pre ratio={a1['ratio_post_pre_base']['point']:.3f} [{a1['ratio_post_pre_base']['ci_lo']:.3f},{a1['ratio_post_pre_base']['ci_hi']:.3f}]")
    d = a1["did_abs_diff"]
    print(f"  DiD(post-pre): spike={d['mean_spike']:+.6f} base={d['mean_base']:+.6f} Δ={d['delta']:+.6f} CI=[{d['ci_lo']:+.6f},{d['ci_hi']:+.6f}] p={d['p_two']:.4f}")

    print("\n=== A2: 左尾（VaR / ES）===")
    a2 = a2_left_tail(ev)
    for grp in ("spike", "baseline"):
        x = a2[grp]
        print(f"  {grp:<9}: mean={x.get('mean_point', float('nan')) if 'mean_point' in x else a2['mean_diff']['mean_spike' if grp=='spike' else 'mean_base']:+.5f}  "
              f"VaR5={x['var5_point']:+.5f}{x['var5_ci']}  ES5={x['es5_point']:+.5f}{x['es5_ci']}  "
              f"VaR10={x['var10_point']:+.5f}  %neg={x['pct_neg']:.1%}")
    d = a2["mean_diff"]
    print(f"  mean Δ(spike-base)={d['delta']:+.6f} CI=[{d['ci_lo']:+.6f},{d['ci_hi']:+.6f}] p={d['p_two']:.3f}")

    print("\n=== A3: pre-trend × exhaustion ===")
    a3 = a3_exhaustion(ev)
    for b, x in a3["by_bucket"].items():
        print(f"  {b:<9} n_s={x['n_spike']:>4} pre_cum={x['pre_cum_mean']:+.5f}  "
              f"post_spike={x['post_mean_spike']:+.5f} post_base={x['post_mean_base']:+.5f}  "
              f"DiD={x['did_post_cum']['delta']:+.6f} p={x['did_post_cum']['p_two']:.3f}  "
              f"spike_p5={x['spike_p5']:+.4f} p95={x['spike_p95']:+.4f} down/up={x['spike_down_up_ratio']:.2f}")

    print("\n=== A4: 固定 1×ATR 止损命中（20 bar 内）===")
    a4 = a4_feature_stop_hit(ev, frames)
    for side, x in a4.items():
        print(f"  {side:<5}: spike hit={x['spike_hit_rate']['point']:.3f} [{x['spike_hit_rate']['ci_lo']:.3f},{x['spike_hit_rate']['ci_hi']:.3f}]  "
              f"base hit={x['base_hit_rate']['point']:.3f}  DiD={x['did']['delta']:+.4f} "
              f"CI=[{x['did']['ci_lo']:+.4f},{x['did']['ci_hi']:+.4f}] p={x['did']['p_two']:.4f}")

    result = {"A1_vol_peak": a1, "A2_left_tail": a2, "A3_exhaustion": a3, "A4_stop_hit": a4}
    (OUT_DIR / "stageA_hypotheses.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n[OK] {OUT_DIR / 'stageA_hypotheses.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
