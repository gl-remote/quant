"""
日线 OOS + 成本现实化。
- 时间 OOS：每个品种按日期前 70%/后 30% 切，IS 定规格、OOS 冻结验证；
- LOPO：留一品种；
- 成本：用 CONTRACT_SPECS 算 commission + slippage，换算成 return bps；
  spike 后做空入场（次日开盘），持有 20 交易日或反向信号，算净收益。
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from daily_volume_spike import build_continuous_by_prefix, build_events, boot_diff  # noqa
from workspace.common.contract_specs import CONTRACT_SPECS  # noqa


N_MAIN = 20
Z0_MAIN = 2.0
H = 20
N_BOOT = 3000


def cost_bps(prefix: str) -> float:
    """粗略估算每品种每边成本（bps）。用 CONTRACT_SPECS.get_prefix。"""
    try:
        spec = CONTRACT_SPECS.get_prefix(prefix)
        if spec is None:
            return 5.0
        c = spec.total_commission(price=5000) if hasattr(spec, "total_commission") else 0
        slip = spec.slippage(lots=1) if hasattr(spec, "slippage") else 0
        return float((c + slip) / 5000 * 1e4)
    except Exception:
        return 5.0


def oos_time(frames: dict[str, pd.DataFrame]) -> dict:
    """每品种前 70% / 后 30% 切，spike vs baseline r20 在 OOS 的差。"""
    out = {"per_prefix": {}, "pooled_is": [], "pooled_oos": []}
    for pfx, df in frames.items():
        n = len(df)
        cut = df.session_date.iloc[int(n * 0.7)]
        is_df = df[df.session_date < cut]
        oos_df = df[df.session_date >= cut]
        if len(is_df) < 60 or len(oos_df) < 40:
            continue
        # 简化：直接在子区间上算 z 和事件（不用 build_events 全量）
        def sub_events(d):
            v = d.volume
            mu = v.shift(1).rolling(N_MAIN, min_periods=N_MAIN).mean()
            sd = v.shift(1).rolling(N_MAIN, min_periods=N_MAIN).std(ddof=1)
            d = d.assign(z=(v - mu) / sd)
            r = d.lr.to_numpy()
            z = d.z.to_numpy()
            recs = []
            for t in range(N_MAIN + H, len(d) - H):
                zv = z[t]
                if not np.isfinite(zv):
                    continue
                if zv >= Z0_MAIN:
                    grp = "spike"
                elif abs(zv) < 0.5:
                    grp = "baseline"
                else:
                    continue
                post = r[t + 1:t + 1 + H]
                if not np.all(np.isfinite(post)):
                    continue
                recs.append({"group": grp, "r20": float(post.sum()), "date": d.session_date.iloc[t]})
            return pd.DataFrame(recs)
        is_ev = sub_events(is_df)
        oos_ev = sub_events(oos_df)
        if is_ev.empty or oos_ev.empty:
            continue
        for tag, ev in [("is", is_ev), ("oos", oos_ev)]:
            sp = ev[ev.group == "spike"]
            bs = ev[ev.group == "baseline"]
            if len(sp) < 3 or len(bs) < 5:
                continue
            d = sp.r20.mean() - bs.r20.mean()
            out["per_prefix"].setdefault(pfx, {})[tag] = {
                "n_spike": int(len(sp)), "n_base": int(len(bs)),
                "r20_spike": float(sp.r20.mean()),
                "r20_base": float(bs.r20.mean()),
                "delta": float(d),
            }
            if tag == "is":
                out["pooled_is"].extend(sp.r20.tolist())
            else:
                out["pooled_oos"].extend(sp.r20.tolist())
    return out


def lopo(frames: dict[str, pd.DataFrame]) -> dict:
    """留一品种：IS 用其余、OOS 在留出品种。"""
    ev_all = build_events(frames, lookback_n=N_MAIN, z0=Z0_MAIN)
    prefixes = sorted(ev_all.prefix.unique())
    out = {}
    for hold in prefixes:
        is_ev = ev_all[ev_all.prefix != hold]
        oos_ev = ev_all[ev_all.prefix == hold]
        is_sp = is_ev[is_ev.group == "spike"]
        is_bs = is_ev[is_ev.group == "baseline"]
        oos_sp = oos_ev[oos_ev.group == "spike"]
        oos_bs = oos_ev[oos_ev.group == "baseline"]
        if len(oos_sp) < 3:
            continue
        out[hold] = {
            "is_delta": float(is_sp.r20.mean() - is_bs.r20.mean()),
            "oos_spike_mean": float(oos_sp.r20.mean()),
            "oos_base_mean": float(oos_bs.r20.mean()),
            "oos_delta": float(oos_sp.r20.mean() - oos_bs.r20.mean()),
            "n_spike_oos": int(len(oos_sp)),
        }
    return out


def cost_realization(frames: dict[str, pd.DataFrame]) -> dict:
    """模拟 spike 次日开盘做空，持有 20 日，算净收益（扣双边成本）。
    收益用 close-to-close（r20 已定义），成本用每品种 bps。
    """
    ev = build_events(frames, lookback_n=N_MAIN, z0=Z0_MAIN)
    sp = ev[ev.group == "spike"].copy()
    sp["cost_bps"] = sp.prefix.map(cost_bps)
    # 做空：gross = -r20（spike 后 r20 为负 → 做空盈利）
    sp["gross_short"] = -sp["r20"]
    sp["net_short_bps"] = sp["gross_short"] * 1e4 - 2 * sp["cost_bps"]  # 开+平双边

    out = {"per_prefix": {}}
    for pfx, sub in sp.groupby("prefix"):
        out["per_prefix"][pfx] = {
            "n": int(len(sub)),
            "cost_bps_one_side": float(sub.cost_bps.iloc[0]),
            "gross_short_mean_pct": float(sub.gross_short.mean() * 100),
            "net_short_bps_mean": float(sub.net_short_bps.mean()),
            "win_rate": float((sub.net_short_bps > 0).mean()),
        }
    # pooled
    out["pooled"] = {
        "n": int(len(sp)),
        "gross_short_mean_pct": float(sp.gross_short.mean() * 100),
        "net_short_bps_mean": float(sp.net_short_bps.mean()),
        "win_rate": float((sp.net_short_bps > 0).mean()),
    }
    # 分 horizon
    for h in (5, 10, 20):
        col = f"r{h}"
        if col in sp.columns:
            gross = -sp[col] * 1e4 - 2 * sp.cost_bps
            out["pooled"][f"net_short_bps_h{h}"] = float(gross.mean())
            out["pooled"][f"win_h{h}"] = float((gross > 0).mean())
    return out


def main():
    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    frames = build_continuous_by_prefix()

    print("=== 时间 OOS (N=20, z0=2, h=20) ===")
    o = oos_time(frames)
    is_deltas, oos_deltas = [], []
    for pfx, d in sorted(o["per_prefix"].items()):
        if "is" in d and "oos" in d:
            is_d = d["is"]["delta"]
            oos_d = d["oos"]["delta"]
            is_deltas.append(is_d)
            oos_deltas.append(oos_d)
            print(f"  {pfx:>4}: IS Δ={is_d:+.4f} (n_s={d['is']['n_spike']:>2})  "
                  f"OOS Δ={oos_d:+.4f} (n_s={d['oos']['n_spike']:>2})  "
                  f"{'sign_ok' if np.sign(is_d)==np.sign(oos_d) else 'FLIP'}")
    print(f"  sign 一致: {sum(1 for a,b in zip(is_deltas,oos_deltas) if np.sign(a)==np.sign(b))}/{len(is_deltas)}")
    print(f"  IS  pooled Δ: {np.mean(is_deltas):+.4f}")
    print(f"  OOS pooled Δ: {np.mean(oos_deltas):+.4f}")

    print("\n=== LOPO ===")
    lp = lopo(frames)
    same = 0
    tot = 0
    for pfx, d in sorted(lp.items(), key=lambda x: x[1]["oos_delta"]):
        is_sign = np.sign(d["is_delta"])
        oos_sign = np.sign(d["oos_delta"])
        ok = is_sign == oos_sign
        if is_sign != 0:
            tot += 1
            same += int(ok)
        print(f"  {pfx:>4}: n_s={d['n_spike_oos']:>2} IS Δ={d['is_delta']:+.4f} "
              f"OOS Δ={d['oos_delta']:+.4f} {'OK' if ok else 'FLIP'}")
    print(f"  LOPO sign 保留率: {same}/{tot} = {same/max(tot,1):.0%}")

    print("\n=== 成本现实化（做空 spike, h=20）===")
    cr = cost_realization(frames)
    for pfx, d in sorted(cr["per_prefix"].items(), key=lambda x: -x[1]["net_short_bps_mean"]):
        print(f"  {pfx:>4}: n={d['n']:>2} cost={d['cost_bps_one_side']:.1f}bps  "
              f"gross={d['gross_short_mean_pct']:+.2f}%  "
              f"net={d['net_short_bps_mean']:+.0f}bps  win={d['win_rate']:.0%}")
    p = cr["pooled"]
    print(f"\n  POOLED: n={p['n']}  gross_short={p['gross_short_mean_pct']:+.2f}%  "
          f"net={p['net_short_bps_mean']:+.0f}bps  win={p['win_rate']:.0%}")
    for h in (5, 10, 20):
        if f"net_short_bps_h{h}" in p:
            print(f"    h={h:>2}: net={p[f'net_short_bps_h{h}']:+.0f}bps  win={p[f'win_h{h}']:.0%}")

    summary = {"time_oos": o, "lopo": lp, "cost": cr}
    (out_dir / "daily_oos_cost.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    print(f"\n[OK] {out_dir / 'daily_oos_cost.json'}")


if __name__ == "__main__":
    main()
