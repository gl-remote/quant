"""
文件级元信息：
- 创建背景：c1 发现 causal L_seg2_low_flat (低 ATR + flat trend + 高 skew·多头方向)
  在 h=8h/10h 持仓下 net p<0.05、CI 排 0，但品种保留率仅 46-51% 未达 80% 门。
  按 methodology KF-23，必须先做过拟合排查再判 alpha。本脚本对 L_seg2 做四重检验：
  (1) 8:2 walk-forward · train/test 独立 net；
  (2) 品种保留率 & IR；
  (3) 时段（hour-of-day）稳定性；
  (4) S_seg12_high_dn 反向 (spec 判空 → 实际多) 平行验证。
- 用途：判定 L_seg2 是真 alpha / 制度依赖 / 过拟合。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/c2/。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")
from h1b_regime_stratified import cluster_bootstrap_mean  # noqa: E402

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c2"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/c1/c1_events_with_tier.csv"
)


def load_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["hour"] = df["event_time"].dt.hour
    return df


def cluster_bootstrap_ir(y: np.ndarray, cluster_id: np.ndarray) -> tuple[float, float, float]:
    """returns (mean, std, ir=mean/std)"""
    mask = ~np.isnan(y)
    y = y[mask]
    if len(y) < 30:
        return float("nan"), float("nan"), float("nan")
    mu = float(np.mean(y))
    sd = float(np.std(y, ddof=1))
    ir = mu / sd if sd > 0 else float("nan")
    return mu, sd, ir


def main() -> None:
    df = load_events()
    print(f"Loaded {len(df)} events, tiers: {df['tier'].value_counts().to_dict()}")

    HORIZONS = ["ret_6h", "ret_8h", "ret_10h", "ret_12h"]

    # ========= L_seg2_low_flat: 8:2 walk-forward =========
    print("\n=== [1] L_seg2_low_flat · 8:2 walk-forward ===")
    l2 = df[df["tier"] == "L_seg2_low_flat"].sort_values("event_time").reset_index(drop=True)
    print(f"L_seg2 total events: {len(l2)}")
    split = int(len(l2) * 0.8)
    l2_tr = l2.iloc[:split]
    l2_te = l2.iloc[split:]
    print(f"train: {len(l2_tr)} ({l2_tr['event_time'].min()} → {l2_tr['event_time'].max()})")
    print(f"test:  {len(l2_te)} ({l2_te['event_time'].min()} → {l2_te['event_time'].max()})")

    wf_rows = []
    for name, sub in [("train", l2_tr), ("test", l2_te)]:
        for h in HORIZONS:
            y_gross = sub[h].to_numpy()  # long, direction=+1
            y_net = y_gross - sub["cost_rt"].to_numpy()
            for lbl, y in [("gross", y_gross), ("net", y_net)]:
                mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
                wf_rows.append({
                    "split": name, "horizon": h, "cost": lbl,
                    "n": n, "mean": mu, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                })
    wf_df = pd.DataFrame(wf_rows)
    wf_df.to_csv(OUT_DIR / "c2_l2_walkforward.csv", index=False)
    print(wf_df.to_string(index=False))

    # ========= L_seg2: 品种保留率 =========
    print("\n=== [2] L_seg2_low_flat · per-symbol IR (train subset) ===")
    sym_rows = []
    for sym, sub in l2_tr.groupby("symbol"):
        if len(sub) < 5:
            continue
        for h in ["ret_8h", "ret_10h"]:
            y = sub[h].to_numpy() - sub["cost_rt"].to_numpy()
            mu, sd, ir = cluster_bootstrap_ir(y, sub["ce_key"].to_numpy())
            sym_rows.append({
                "symbol": sym, "horizon": h, "n": len(sub),
                "mean_net": mu, "std": sd, "ir": ir,
            })
    sym_df = pd.DataFrame(sym_rows)
    sym_df.to_csv(OUT_DIR / "c2_l2_train_symbol_ir.csv", index=False)
    print(sym_df.to_string(index=False))
    # 保留率
    for h in ["ret_8h", "ret_10h"]:
        subh = sym_df[sym_df["horizon"] == h].dropna(subset=["mean_net"])
        pos = (subh["mean_net"] > 0).sum()
        tot = len(subh)
        print(f"[TRAIN] {h}: positive symbols {pos}/{tot} = {pos/max(tot,1):.1%}")

    # 用 train 阳性 symbol 子集在 test 上复验
    print("\n=== [3] L_seg2 · TRAIN-positive symbols → TEST ===")
    for h in ["ret_8h", "ret_10h"]:
        pos_syms = sym_df[(sym_df["horizon"] == h) & (sym_df["mean_net"] > 0)]["symbol"].tolist()
        te_sub = l2_te[l2_te["symbol"].isin(pos_syms)]
        y = te_sub[h].to_numpy() - te_sub["cost_rt"].to_numpy()
        mu, lo, hi, p, n = cluster_bootstrap_mean(y, te_sub["ce_key"].to_numpy())
        print(f"[TEST-selected] {h}: n_syms={len(pos_syms)}, n_events={n}, "
              f"net mean={mu:.6f} CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    # ========= S_seg12_high_dn 反向 =========
    print("\n=== [4] S_seg12_high_dn 反向（当作多头信号） ===")
    s12 = df[df["tier"] == "S_seg12_high_dn"].sort_values("event_time").reset_index(drop=True)
    print(f"S_seg12 total events: {len(s12)}")
    split2 = int(len(s12) * 0.8)
    s12_tr = s12.iloc[:split2]
    s12_te = s12.iloc[split2:]
    for name, sub in [("train", s12_tr), ("test", s12_te)]:
        for h in HORIZONS:
            # 反向：direction=+1（原 spec 为 -1 空，我们反过来测多）
            y_gross = sub[h].to_numpy() * 1.0
            y_net = y_gross - sub["cost_rt"].to_numpy()
            mu, lo, hi, p, n = cluster_bootstrap_mean(y_net, sub["ce_key"].to_numpy())
            print(f"  {name} {h} REV-LONG net: n={n}, mean={mu:.6f} "
                  f"CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    # ========= 组合 L_seg2 + S_seg12(反向) 的联合信号，看是否互补 =========
    print("\n=== [5] 组合 L_seg2 + S_seg12(REV) 单信号池 · 8h/10h · walk-forward ===")
    for h in ["ret_8h", "ret_10h"]:
        for name, l2sub, s12sub in [
            ("train", l2_tr, s12_tr),
            ("test", l2_te, s12_te),
        ]:
            # 都当多头
            y1 = l2sub[h].to_numpy() - l2sub["cost_rt"].to_numpy()
            y2 = s12sub[h].to_numpy() - s12sub["cost_rt"].to_numpy()
            y = np.concatenate([y1, y2])
            ce = np.concatenate([l2sub["ce_key"].to_numpy(), s12sub["ce_key"].to_numpy()])
            mu, lo, hi, p, n = cluster_bootstrap_mean(y, ce)
            print(f"  {name} {h} COMBO: n={n}, net mean={mu:.6f} "
                  f"CI=[{lo:.6f},{hi:.6f}] p={p:.3f}")

    # ========= 时段（hour-of-day）稳定性 · L_seg2 =========
    print("\n=== [6] L_seg2_low_flat · hour-of-day 8h net ===")
    hod_rows = []
    for hour, sub in l2.groupby("hour"):
        if len(sub) < 20:
            continue
        y = sub["ret_8h"].to_numpy() - sub["cost_rt"].to_numpy()
        mu, lo, hi, p, n = cluster_bootstrap_mean(y, sub["ce_key"].to_numpy())
        hod_rows.append({
            "hour": int(hour), "n": n, "mean_net": mu,
            "ci_lo": lo, "ci_hi": hi, "p_two": p,
        })
    hod_df = pd.DataFrame(hod_rows)
    hod_df.to_csv(OUT_DIR / "c2_l2_hour.csv", index=False)
    print(hod_df.to_string(index=False))

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
