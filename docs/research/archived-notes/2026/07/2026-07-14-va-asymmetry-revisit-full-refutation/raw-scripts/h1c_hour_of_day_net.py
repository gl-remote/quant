"""
文件级元信息：
- 创建背景：H-1 已判死；但 h1b 副产品显示 hour-of-day ∈ {9,10,11,14} 的
  4h mean_ret 显著为正（cluster CI 排 0）。本脚本对该"偶然信号"做净收益
  验证，判断是真信号还是选样偏差 / 高估。
- 用途：对 hour-of-day 白盘做 signed=+1（全多）与 signed=-1（全空）净收益
  cluster bootstrap；顺带做 per-symbol retention。
- 注意事项：临时研究脚本，产物在
  docs/workbench/va-asymmetry-revisit/outputs/h1c/。若 net mean CI 依然
  排 0 → 可能是真 alpha，进入 OOS；否则判为选样偏差。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/workspace")
sys.path.insert(0, "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts")

from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from h1b_regime_stratified import cluster_bootstrap_mean, enrich_events_with_intraday_ctx  # noqa: E402

OUT_DIR = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1c"
)
OUT_DIR.mkdir(parents=True, exist_ok=True)

LONG_PATH = Path(
    "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/outputs/h1/h1_long_events.csv"
)


def one_side_cost_frac(row) -> float:
    spec = CONTRACT_SPECS.get_symbol(row["symbol"])
    if spec is None:
        return np.nan
    price = float(row["close_t"])
    slip_frac = (spec.tick * spec.slip_tick) / price
    try:
        comm_yuan = spec.total_commission(price, 1)
        comm_frac = comm_yuan / (spec.size * price) if spec.size > 0 else 0.0
    except Exception:
        comm_frac = 0.0
    return slip_frac + comm_frac


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = enrich_events_with_intraday_ctx(df)
    df["ce_key"] = df["contract"].astype(str) + "|" + df["event_date"].astype(str)
    df["cost_rt"] = 2.0 * df.apply(one_side_cost_frac, axis=1)

    # 时间切分：前 80% train / 后 20% test（walk-forward 单折）
    df = df.sort_values("event_time").reset_index(drop=True)
    n = len(df)
    split_idx = int(n * 0.8)
    df_tr = df.iloc[:split_idx].copy()
    df_te = df.iloc[split_idx:].copy()
    print(f"Train events: {len(df_tr)} ({df_tr['event_time'].min()} → "
          f"{df_tr['event_time'].max()})")
    print(f"Test  events: {len(df_te)} ({df_te['event_time'].min()} → "
          f"{df_te['event_time'].max()})")

    hours_long = [9, 10, 11, 14]
    horizons = [1, 2, 4, 6, 8, 12]

    def summarize(subset_df: pd.DataFrame, name: str) -> pd.DataFrame:
        rows = []
        for h in horizons:
            for hour_group in [hours_long]:
                sub = subset_df[subset_df["hour"].isin(hour_group)]
                y_gross = sub[f"ret_{h}h"].to_numpy()  # bet=+1
                y_net = y_gross - sub["cost_rt"].to_numpy()
                for lbl, y in [("gross", y_gross), ("net", y_net)]:
                    obs, lo, hi, p, n_use = cluster_bootstrap_mean(
                        y, sub["ce_key"].to_numpy()
                    )
                    rows.append({
                        "split": name, "hours": "9-11+14", "cost": lbl,
                        "horizon": f"ret_{h}h",
                        "n": n_use, "mean": obs, "ci_lo": lo, "ci_hi": hi, "p_two": p,
                    })
        return pd.DataFrame(rows)

    tr_df = summarize(df_tr, "train")
    te_df = summarize(df_te, "test")
    all_df = pd.concat([tr_df, te_df], ignore_index=True)
    all_df.to_csv(OUT_DIR / "h1c_hour_net.csv", index=False)
    print("\n=== Hour-of-day (9-11+14) long bet, gross/net, train/test ===")
    print(all_df.to_string(index=False))

    # per-symbol retention on TRAIN, net, h=4
    print("\n=== TRAIN Per-symbol retention: hour∈{9,10,11,14}, ret_4h, NET ===")
    sub = df_tr[df_tr["hour"].isin(hours_long)]
    rows = []
    for sym, s2 in sub.groupby("symbol"):
        if len(s2) < 30:
            continue
        y = s2["ret_4h"].to_numpy() - s2["cost_rt"].to_numpy()
        rows.append({
            "symbol": sym, "n": len(s2), "mean_net_4h": float(np.nanmean(y)),
            "hit": float(np.nanmean(y > 0)),
        })
    ret_df = pd.DataFrame(rows).sort_values("mean_net_4h", ascending=False)
    ret_df.to_csv(OUT_DIR / "h1c_train_symbol_net_4h.csv", index=False)
    print(ret_df.to_string(index=False))
    print(f"\nSymbols with positive net mean 4h: "
          f"{(ret_df['mean_net_4h']>0).sum()}/{len(ret_df)}")

    # 另做：TRAIN 上"只挑 net>0 品种子集"→ TEST 复现率检验
    positive_syms = ret_df.loc[ret_df["mean_net_4h"] > 0, "symbol"].tolist()
    print(f"\nSelecting positive symbols from TRAIN: {positive_syms}")
    if positive_syms:
        te_sub = df_te[
            (df_te["hour"].isin(hours_long)) & (df_te["symbol"].isin(positive_syms))
        ]
        rows_te = []
        for h in horizons:
            y = te_sub[f"ret_{h}h"].to_numpy() - te_sub["cost_rt"].to_numpy()
            obs, lo, hi, p, n_use = cluster_bootstrap_mean(
                y, te_sub["ce_key"].to_numpy()
            )
            rows_te.append({
                "horizon": f"ret_{h}h", "n": n_use, "mean_net": obs,
                "ci_lo": lo, "ci_hi": hi, "p_two": p,
            })
        te_pos_df = pd.DataFrame(rows_te)
        te_pos_df.to_csv(OUT_DIR / "h1c_test_selected_syms.csv", index=False)
        print("\n=== TEST (only train-positive symbols, hour∈{9,10,11,14}) ===")
        print(te_pos_df.to_string(index=False))

    print(f"\nAll outputs in: {OUT_DIR}")


if __name__ == "__main__":
    main()
