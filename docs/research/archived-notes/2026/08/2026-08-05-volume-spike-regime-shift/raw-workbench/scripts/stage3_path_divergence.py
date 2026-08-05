"""
文件级元信息：
- 创建背景：回答"放量后行情有统一规律还是发散"。stage3_path_divergence.py
  在大矩阵 bootstrap 时触发 OOM；本脚本改为逐合约累积 + 流式 cluster bootstrap，
  只保留回答问题必要的统计量，避免把全部 20×20 路径矩阵放进内存。
- 用途：
  1) post_cum 分布（均值/中位数/分位数/正负比例）对比 spike vs baseline；
  2) 按 pre 窗趋势三分位（pre_down/pre_flat/pre_up）看 post_cum 是否一致反转；
  3) 按 spike bar 颜色（阳/阴）看 post 是否反向；
  4) 逐 bar 累计路径均值（不保留全路径矩阵，逐 bar 累积）；
  5) 路径离散度：post 窗内 cum path std 与 max favorable/adverse；
  6) per-prefix 方向一致率。
- 注意事项：cluster=(symbol,session_date)；所有 bootstrap 用 2000 次重采样。
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
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
    mu = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).mean()
    )
    sd = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(LOOKBACK_N, min_periods=LOOKBACK_N).std(ddof=1)
    )
    df["z"] = (v - mu) / sd
    df["session_date"] = df["datetime"].dt.date
    return df


def main() -> int:
    csv_dir = market_csv_dir()
    # 累积事件属性 + 每个 spike 的 post cum path（用于逐 bar）
    # 为控内存：spike post path 用 list[np.ndarray]（约 1500*20 floats = 240KB）
    recs: list[dict[str, Any]] = []
    post_paths_s: list[np.ndarray] = []
    post_paths_b: list[np.ndarray] = []

    n_contracts = 0
    for p in sorted(csv_dir.glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < MIN_BARS:
            continue
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_df(p)
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
            cum_post = np.cumsum(post)
            rec = {
                "symbol": symbol,
                "prefix": prefix,
                "session_date": sess[t],
                "group": grp,
                "z": float(zv),
                "spike_ret": float(r[t]),
                "pre_cum": float(pre.sum()),
                "post_cum": float(cum_post[-1]),
                "path_disp": float(cum_post.std(ddof=1)),
                "max_fav": float(cum_post.max()),
                "max_adv": float(cum_post.min()),
                "post_abs": float(np.abs(post).mean()),
            }
            recs.append(rec)
            if grp == "spike":
                post_paths_s.append(post.copy())
            else:
                post_paths_b.append(post.copy())
        n_contracts += 1

    ev = pd.DataFrame(recs)
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    out_dir.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(out_dir / "stage3_paths.parquet", index=False)
    print(f"contracts={n_contracts} events={len(ev)}")
    print(ev.groupby("group").size())

    sp = ev[ev.group == "spike"].reset_index(drop=True)
    bs = ev[ev.group == "baseline"].reset_index(drop=True)

    # ---------- helpers ----------
    def cluster_boot(vals: np.ndarray, cid: np.ndarray, seed: int) -> dict[str, float]:
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

    def cid_of(df_: pd.DataFrame) -> np.ndarray:
        keys = sorted({(s, d) for s, d in zip(df_["symbol"], df_["session_date"])})
        km = {k: i for i, k in enumerate(keys)}
        return np.array([km[(s, d)] for s, d in zip(df_["symbol"], df_["session_date"])], dtype=np.int32)

    def quant(vals: np.ndarray) -> dict[str, float]:
        return {
            "mean": float(np.mean(vals)),
            "median": float(np.median(vals)),
            "std": float(np.std(vals, ddof=1)),
            "skew": float(pd.Series(vals).skew()),
            "p10": float(np.quantile(vals, 0.10)),
            "p25": float(np.quantile(vals, 0.25)),
            "p75": float(np.quantile(vals, 0.75)),
            "p90": float(np.quantile(vals, 0.90)),
            "pct_neg": float((vals < 0).mean()),
            "pct_pos": float((vals > 0).mean()),
        }

    summary: dict[str, Any] = {"n_spike": len(sp), "n_base": len(bs)}

    # 1) post_cum 分布
    print("\n=== post_cum (h=20) distribution ===")
    for name, d in (("spike", sp), ("base", bs)):
        q = quant(d["post_cum"].to_numpy())
        summary[f"post_cum_{name}"] = q
        print(f"  {name:<6}: mean={q['mean']:+.5f} med={q['median']:+.5f} "
              f"std={q['std']:.5f} skew={q['skew']:+.2f} "
              f"p10..90=[{q['p10']:+.5f},{q['p90']:+.5f}] "
              f"%neg={q['pct_neg']:.1%} %pos={q['pct_pos']:.1%}")

    # 2) 按 pre 趋势三分位
    print("\n=== spike post_cum by pre-trend tertile ===")
    q1, q2 = sp["pre_cum"].quantile([1/3, 2/3])
    def bucket(x: float) -> str:
        if x < q1: return "pre_down"
        if x > q2: return "pre_up"
        return "pre_flat"
    sp["pre_bkt"] = sp["pre_cum"].apply(bucket)
    by_pre: dict[str, Any] = {}
    for b in ("pre_down", "pre_flat", "pre_up"):
        sub = sp[sp.pre_bkt == b]
        cid = cid_of(sub)
        bm = cluster_boot(sub["post_cum"].to_numpy(), cid, BOOT_SEED + hash(b) % 1000)
        q = quant(sub["post_cum"].to_numpy())
        by_pre[b] = {
            "n": int(len(sub)),
            "pre_cum_mean": float(sub.pre_cum.mean()),
            "spike_ret_mean": float(sub.spike_ret.mean()),
            "boot": bm,
            "dist": q,
        }
        print(f"  {b:<9} n={len(sub):>4} pre={by_pre[b]['pre_cum_mean']:+.5f} "
              f"spike_ret={by_pre[b]['spike_ret_mean']:+.5f} | "
              f"post_mean={bm['point']:+.5f} CI=[{bm['ci_lo']:+.5f},{bm['ci_hi']:+.5f}] "
              f"med={q['median']:+.5f} %neg={q['pct_neg']:.1%}")
    summary["by_pre_trend"] = by_pre

    # 3) 按 spike bar 颜色
    print("\n=== spike post_cum by spike bar color ===")
    by_col: dict[str, Any] = {}
    for name, mask in (("up", sp.spike_ret > 0), ("dn", sp.spike_ret < 0)):
        sub = sp[mask]
        cid = cid_of(sub)
        bm = cluster_boot(sub["post_cum"].to_numpy(), cid, BOOT_SEED + hash(name) % 1000)
        by_col[name] = {"n": int(len(sub)),
                        "spike_ret_mean": float(sub.spike_ret.mean()),
                        "boot": bm}
        print(f"  {name:<3} n={len(sub):>4} spike_ret={by_col[name]['spike_ret_mean']:+.5f} "
              f"post_mean={bm['point']:+.5f} CI=[{bm['ci_lo']:+.5f},{bm['ci_hi']:+.5f}]")
    summary["by_color"] = by_col

    # 4) 逐 bar 均值 + bootstrap（逐列，避免大矩阵）
    print("\n=== mean cumulative path at t+k (selected) ===")
    paths_s = np.stack(post_paths_s)  # (n_s, H)
    paths_b = np.stack(post_paths_b)
    cum_s = np.cumsum(paths_s, axis=1)
    cum_b = np.cumsum(paths_b, axis=1)
    cid_s = cid_of(sp)
    cid_b = cid_of(bs)
    nc_s = int(cid_s.max()) + 1
    nc_b = int(cid_b.max()) + 1
    sums_s = np.zeros((nc_s, H))
    sums_b = np.zeros((nc_b, H))
    np.add.at(sums_s, cid_s, cum_s)
    np.add.at(sums_b, cid_b, cum_b)
    cnt_s = np.bincount(cid_s, minlength=nc_s).astype(np.float64)
    cnt_b = np.bincount(cid_b, minlength=nc_b).astype(np.float64)
    rng = np.random.default_rng(BOOT_SEED)
    idx_s = rng.integers(0, nc_s, size=(N_BOOT, nc_s), dtype=np.int32)
    rng2 = np.random.default_rng(BOOT_SEED + 1)
    idx_b = rng2.integers(0, nc_b, size=(N_BOOT, nc_b), dtype=np.int32)
    boot_s = sums_s[idx_s].sum(axis=1) / cnt_s[idx_s].sum(axis=1, keepdims=True)
    boot_b = sums_b[idx_b].sum(axis=1) / cnt_b[idx_b].sum(axis=1, keepdims=True)
    bsort_s = np.sort(boot_s, axis=0)
    bsort_b = np.sort(boot_b, axis=0)
    path_rows = []
    for k in range(H):
        row = {
            "bar": k + 1,
            "spike_mean": float(cum_s[:, k].mean()),
            "spike_ci_lo": float(bsort_s[int(0.025*N_BOOT), k]),
            "spike_ci_hi": float(bsort_s[int(0.975*N_BOOT), k]),
            "base_mean": float(cum_b[:, k].mean()),
            "did": float(cum_s[:, k].mean() - cum_b[:, k].mean()),
        }
        path_rows.append(row)
        if (k + 1) in (1, 3, 6, 12, 20):
            print(f"  t+{k+1:<3} spike={row['spike_mean']:+.5f} "
                  f"[{row['spike_ci_lo']:+.5f},{row['spike_ci_hi']:+.5f}] "
                  f"base={row['base_mean']:+.5f} DiD={row['did']:+.5f}")
    summary["cum_path"] = path_rows

    # 5) 路径离散度
    print("\n=== post path dispersion ===")
    disp_fields = ["path_disp", "max_fav", "max_adv", "post_abs"]
    disp_out: dict[str, Any] = {}
    for i, f in enumerate(disp_fields):
        vs = sp[f].to_numpy()
        vb = bs[f].to_numpy()
        rs = cluster_boot(vs, cid_s, BOOT_SEED + 200 + i)
        rb = cluster_boot(vb, cid_b, BOOT_SEED + 300 + i)
        disp_out[f] = {"spike": rs, "base": rb, "did": rs["point"] - rb["point"]}
        print(f"  {f:<10} spike={rs['point']:.5f}[{rs['ci_lo']:.5f},{rs['ci_hi']:.5f}]  "
              f"base={rb['point']:.5f}  DiD={rs['point']-rb['point']:+.5f}")
    summary["dispersion"] = disp_out

    # 6) per-prefix sign consistency
    print("\n=== per-prefix dominant sign ratio (spike post_cum) ===")
    sign_by_prefix: dict[str, float] = {}
    for pfx, sub in sp.groupby("prefix"):
        v = sub["post_cum"].to_numpy()
        sign_by_prefix[pfx] = float(max((v < 0).mean(), (v > 0).mean()))
        print(f"  {pfx:>4}: {sign_by_prefix[pfx]:.1%} (post_mean={v.mean():+.5f})")
    summary["sign_by_prefix"] = sign_by_prefix

    (out_dir / "stage3_path_analysis.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )
    print("\n[OK] stage3_paths.parquet + stage3_path_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
