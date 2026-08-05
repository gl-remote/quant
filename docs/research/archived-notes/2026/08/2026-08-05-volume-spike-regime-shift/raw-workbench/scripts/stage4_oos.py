"""
文件级元信息：
- 创建背景：Stage A 发现左尾风险（ES5/VaR5）是唯一稳健可操作结论。
  Stage 4 验证时间 OOS + 品种 LOPO。
- 用途：
  1) 每合约按 bar 顺序前 70% / 后 30% 切；IS/OOS 独立算 ES5/VaR5/path_disp/mean 的 spike-base diff；
  2) LOPO：每留出一个 prefix，其余当 IS 估计 tail diff，在留出 prefix 上验证 sign；
  3) 输出每指标的 IS/OOS 点估计 + cluster bootstrap CI + sign 一致性。
- 注意事项：OOS 样本小（每合约约 30% bar），CI 宽；不据此选参数。
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


def build_events(split: str | None = None) -> pd.DataFrame:
    """split: None=all, 'is'=前 70%, 'oos'=后 30%（按合约内切）。"""
    recs = []
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
        n = len(df)
        cut = int(n * 0.7)
        rng = range(H, n - H)
        if split == "is":
            rng = range(H, min(cut, n - H))
        elif split == "oos":
            rng = range(max(H, cut), n - H)
        r = df["lr"].to_numpy()
        z = df["z"].to_numpy()
        atr = df["atr"].to_numpy()
        sess = df["session_date"].to_numpy()
        for t in rng:
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
            post = r[t + 1 : t + 1 + H]
            if not np.all(np.isfinite(post)):
                continue
            recs.append({
                "symbol": symbol, "prefix": prefix, "session_date": sess[t],
                "group": grp, "post_cum": float(post.sum()),
                "post_abs": float(np.abs(post).mean()),
                "path_disp": float(np.cumsum(post).std(ddof=1)),
                "t": t,
            })
    return pd.DataFrame(recs)


def cid(df: pd.DataFrame) -> np.ndarray:
    keys = sorted({(s, d) for s, d in zip(df["symbol"], df["session_date"])})
    km = {k: i for i, k in enumerate(keys)}
    return np.array([km[(s, d)] for s, d in zip(df["symbol"], df["session_date"])], dtype=np.int32)


def tail_stats(vals: np.ndarray, c: np.ndarray, seed: int) -> dict[str, Any]:
    """cluster bootstrap 估 mean / VaR5 / ES5 / path_disp 均值。"""
    nc = int(c.max()) + 1
    clusters = [vals[c == k] for k in range(nc)]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nc, size=(N_BOOT, nc), dtype=np.int32)
    means, var5, es5 = [], [], []
    for i in range(N_BOOT):
        s = np.concatenate([clusters[k] for k in idx[i]])
        q5 = np.quantile(s, 0.05)
        means.append(s.mean())
        var5.append(q5)
        es5.append(s[s <= q5].mean())
    return {
        "mean_point": float(vals.mean()),
        "mean_ci": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
        "var5_point": float(np.quantile(vals, 0.05)),
        "var5_ci": [float(np.quantile(var5, 0.025)), float(np.quantile(var5, 0.975))],
        "es5_point": float(vals[vals <= np.quantile(vals, 0.05)].mean()),
        "es5_ci": [float(np.quantile(es5, 0.025)), float(np.quantile(es5, 0.975))],
        "n": int(len(vals)),
    }


def diff_stats(sp: pd.DataFrame, bs: pd.DataFrame, seed: int) -> dict[str, Any]:
    """spike-baseline 在 mean / VaR5 / ES5 / path_disp 上的差及 bootstrap CI。"""
    cs, cb = cid(sp), cid(bs)
    # 用 cluster bootstrap 同种子抽样算差
    nc_s, nc_b = int(cs.max()) + 1, int(cb.max()) + 1
    clust_s = [sp["post_cum"].to_numpy()[cs == k] for k in range(nc_s)]
    clust_b = [bs["post_cum"].to_numpy()[cb == k] for k in range(nc_b)]
    # path_disp clusters
    pds = sp["path_disp"].to_numpy()
    pdb = bs["path_disp"].to_numpy()
    pclust_s = [pds[cs == k] for k in range(nc_s)]
    pclust_b = [pdb[cb == k] for k in range(nc_b)]
    rng = np.random.default_rng(seed)
    idx_s = rng.integers(0, nc_s, size=(N_BOOT, nc_s), dtype=np.int32)
    rng2 = np.random.default_rng(seed + 1)
    idx_b = rng2.integers(0, nc_b, size=(N_BOOT, nc_b), dtype=np.int32)

    d_mean, d_var5, d_es5, d_pd = [], [], [], []
    for i in range(N_BOOT):
        sv = np.concatenate([clust_s[k] for k in idx_s[i]])
        bv = np.concatenate([clust_b[k] for k in idx_b[i]])
        q5s, q5b = np.quantile(sv, 0.05), np.quantile(bv, 0.05)
        d_mean.append(sv.mean() - bv.mean())
        d_var5.append(q5s - q5b)
        d_es5.append(sv[sv <= q5s].mean() - bv[bv <= q5b].mean())
        spd = np.concatenate([pclust_s[k] for k in idx_s[i]])
        bpd = np.concatenate([pclust_b[k] for k in idx_b[i]])
        d_pd.append(spd.mean() - bpd.mean())

    def block(arr: list[float]) -> dict[str, float]:
        a = np.array(arr)
        return {
            "delta": float(a.mean()),
            "ci_lo": float(np.quantile(a, 0.025)),
            "ci_hi": float(np.quantile(a, 0.975)),
            "p_two": float(min(1.0, 2 * min((a <= 0).mean(), (a >= 0).mean()))),
        }

    return {
        "mean": block(d_mean),
        "var5": block(d_var5),
        "es5": block(d_es5),
        "path_disp": block(d_pd),
    }


def time_oos() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("is", "oos"):
        ev = build_events(split)
        sp = ev[ev.group == "spike"]
        bs = ev[ev.group == "baseline"]
        out[split] = {
            "n_spike": int(len(sp)),
            "n_base": int(len(bs)),
            "spike": tail_stats(sp["post_cum"].to_numpy(), cid(sp), hash(split) % 2**30),
            "base": tail_stats(bs["post_cum"].to_numpy(), cid(bs), hash(split + "b") % 2**30),
            "diff": diff_stats(sp, bs, hash(split + "d") % 2**30),
        }
    return out


def lopo() -> dict[str, Any]:
    ev = build_events(None)
    prefixes = sorted(ev.prefix.unique())
    result: dict[str, Any] = {"per_prefix": {}, "sign_retention": {}}
    for holdout in prefixes:
        is_ev = ev[ev.prefix != holdout]
        oos_ev = ev[ev.prefix == holdout]
        is_sp = is_ev[is_ev.group == "spike"]
        is_bs = is_ev[is_ev.group == "baseline"]
        if len(is_sp) < 30 or len(is_bs) < 30:
            continue
        is_diff = diff_stats(is_sp, is_bs, hash(holdout) % 2**30)
        # OOS：留出 prefix 内的 spike/base 简单点估计
        oos_sp = oos_ev[oos_ev.group == "spike"]["post_cum"].to_numpy()
        oos_bs = oos_ev[oos_ev.group == "baseline"]["post_cum"].to_numpy()
        if len(oos_sp) < 5 or len(oos_bs) < 5:
            continue
        q5s, q5b = np.quantile(oos_sp, 0.05), np.quantile(oos_bs, 0.05)
        oos_diff = {
            "n_spike": int(len(oos_sp)),
            "n_base": int(len(oos_bs)),
            "mean": float(oos_sp.mean() - oos_bs.mean()),
            "var5": float(q5s - q5b),
            "es5": float(oos_sp[oos_sp <= q5s].mean() - oos_bs[oos_bs <= q5b].mean()),
        }
        result["per_prefix"][holdout] = {"is": is_diff, "oos": oos_diff}

    # sign retention：IS Δ sign 与 OOS Δ sign 一致比例
    for metric in ("mean", "var5", "es5"):
        same = 0
        tot = 0
        for holdout, d in result["per_prefix"].items():
            is_sign = np.sign(d["is"][metric]["delta"])
            oos_sign = np.sign(d["oos"][metric])
            if is_sign != 0 and oos_sign != 0:
                tot += 1
                if is_sign == oos_sign:
                    same += 1
        result["sign_retention"][metric] = float(same / tot) if tot else float("nan")
    return result


def main() -> int:
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    print("=== Stage 4a: time OOS ===")
    t = time_oos()
    for split in ("is", "oos"):
        d = t[split]
        print(f"\n[{split}] n_spike={d['n_spike']} n_base={d['n_base']}")
        for m in ("mean", "var5", "es5", "path_disp"):
            x = d["diff"][m]
            print(f"  {m:<10} Δ={x['delta']:+.6f} CI=[{x['ci_lo']:+.6f},{x['ci_hi']:+.6f}] p={x['p_two']:.3f}")

    print("\n=== Stage 4b: LOPO sign retention ===")
    lp = lopo()
    for m, v in lp["sign_retention"].items():
        print(f"  {m}: sign retention = {v:.1%}")
    print("\n  per-prefix OOS ES5 Δ:")
    for pfx, d in sorted(lp["per_prefix"].items(), key=lambda x: x[1]["oos"]["es5"]):
        print(f"    {pfx:>4}: n_s={d['oos']['n_spike']:>3} "
              f"Δmean={d['oos']['mean']:+.5f} ΔVaR5={d['oos']['var5']:+.5f} ΔES5={d['oos']['es5']:+.5f}")

    summary = {"time_oos": t, "lopo": lp}
    (out_dir / "stage4_oos.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"\n[OK] {out_dir / 'stage4_oos.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
