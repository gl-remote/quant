"""
低 s 层放量反弹验证框架（对应 conditioner §10.6 后续方向）。

假设来源：
  - CGW (1993)：高成交量+跌后应反弹（流动性买入压力）；
  - conditioner §6：低 s（下跌趋势）中放量后部分因子翻正，但
    pre_cum 绝对收益在同 regime baseline 下 p>0.12（r1 撤回）；
  - PATEFF 例外：平滑下跌+放量续跌（IC +0.43）。

本框架系统检验以下命题：
  H1  低 s + 放量后，未来 H bar 是否正收益（反弹）？
  H2  反弹强度是否依赖 MADEV（价格偏离均线向下的程度）？
  H3  PATEFF（路径效率）是否区分"恐慌续跌"与"出清反弹"？
  H4  Volume Profile Skew 是否在低 s 中区分好/坏放量
      （正偏=低位承接=看涨，负偏=高位派发=看跌）？
  H5  反弹的时间路径（第 20/40/60/80/100 bar）和半衰期？

方法：
  - 与 r1/r2 完全一致的数据口径（同时段 z、s_pre=mean/std、cluster bootstrap）；
  - 必须用同 regime baseline（低 s + |z|<0.5），不能与全样本比；
  - 报告 n、mean、%pos、IC、cluster bootstrap CI；
  - FDR 控制 q<0.1。

输出：
  project_data/research/volume-spike-regime-shift/low_s_rebound.parquet
  控制台打印各假设结果。
"""
from __future__ import annotations
import sys, math, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

# ============ 参数 ============
N_Z = 20              # 同时段 z 的 lookback
HORIZONS = [20, 40, 60, 80, 100]
S_THRESH = -0.10      # 低 s 阈值（与 conditioner §6 一致）
Z_SPIKE = 1.5
Z_EXTREME = 2.5
Z_BASE = 0.5
MIN_BARS = 300
N_BOOT = 1000
RNG = np.random.default_rng(42)

OUT = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
OUT.mkdir(parents=True, exist_ok=True)


# ============ 数据加载 ============
def load_contract(p: Path):
    """加载单个 1h 合约，计算 z、s_pre、MADEV、PATEFF、未来收益。"""
    try:
        d = pd.read_csv(p)
    except Exception:
        return None
    need = {"datetime", "open", "high", "low", "close", "volume"}
    if not need.issubset(d.columns):
        return None
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    if len(d) < MIN_BARS:
        return None

    sym = p.name.split(".tqsdk.1h.csv")[0] if ".tqsdk" in p.name else p.stem
    prefix = extract_contract_prefix(sym) or ""

    d["lr"] = np.log(d.close).diff()
    d["session_date"] = d.datetime.dt.date

    # 同时段 z
    v, hour = d.volume, d.datetime.dt.hour
    mu = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).mean())
    sd = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(N_Z, min_periods=N_Z).std(ddof=1))
    d["z"] = (v - mu) / sd

    # MADEV 120
    d["ma120"] = d.close.rolling(120, min_periods=120).mean()
    d["madev120"] = np.log(d.close / d.ma120)

    # 未来 H 收益和 MADEV 路径
    for H in HORIZONS:
        d[f"fwd_ret_{H}"] = d.lr.shift(-1).rolling(H).sum().shift(-(H-1))
        d[f"fwd_madev_{H}"] = d.madev120.shift(-H)

    r = d.lr.to_numpy()
    n = len(d)
    recs = []
    for t in range(201, n - max(HORIZONS) - 5):
        zv = d.z.iloc[t]
        if not math.isfinite(zv):
            continue
        pre = r[t-100:t]
        if len(pre) < 100 or not np.all(np.isfinite(pre)):
            continue
        nu = pre.mean()
        sigma = pre.std(ddof=1)
        if sigma <= 0 or not math.isfinite(sigma):
            continue
        s_pre = nu / sigma
        madev = d.madev120.iloc[t]
        if not math.isfinite(madev):
            continue

        # PATEFF100: |净位移| / 总路径长度
        net = abs(pre.sum())
        path = np.abs(pre).sum()
        pateff = net / path if path > 0 else np.nan

        # 分组
        if zv >= Z_EXTREME:
            grp = "extreme"
        elif zv >= Z_SPIKE:
            grp = "spike"
        elif abs(zv) < Z_BASE:
            grp = "base"
        elif zv <= -Z_BASE:
            grp = "low_vol"
        else:
            continue

        rec = {
            "symbol": sym, "prefix": prefix,
            "ts": d.datetime.iloc[t],
            "session_date": str(d.session_date.iloc[t]),
            "z": float(zv), "s_pre": float(s_pre),
            "madev120": float(madev),
            "pateff100": float(pateff) if math.isfinite(pateff) else np.nan,
            "pre_cum100": float(pre.sum()),
            "group": grp,
        }
        for H in HORIZONS:
            rec[f"r{H}"] = float(d[f"fwd_ret_{H}"].iloc[t]) if math.isfinite(d[f"fwd_ret_{H}"].iloc[t]) else np.nan
            rec[f"madev_post_{H}"] = float(d[f"fwd_madev_{H}"].iloc[t]) if math.isfinite(d[f"fwd_madev_{H}"].iloc[t]) else np.nan
        recs.append(rec)
    return pd.DataFrame(recs)


def collect_all():
    files = sorted(market_csv_dir().glob("*.1h.csv"))
    print(f"扫描 {len(files)} 个 1h 合约...")
    dfs = []
    for p in files:
        df = load_contract(p)
        if df is not None and len(df) > 0:
            dfs.append(df)
    ev = pd.concat(dfs, ignore_index=True)
    print(f"事件总数: {len(ev):,}")
    return ev


# ============ 统计工具 ============
def boot_cluster_ci(s: pd.Series, clusters: pd.Series, n_boot=N_BOOT):
    """按 cluster（symbol×session_date）bootstrap 95% CI。"""
    s = s.to_numpy()
    cl = clusters.to_numpy()
    uc = np.unique(cl)
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = RNG.choice(uc, size=len(uc), replace=True)
        sample = np.concatenate([np.where(cl == c)[0] for c in idx if c in cl]) if len(idx) else np.array([], dtype=int)
        if len(sample) < 2:
            vals[b] = np.nan
        else:
            vals[b] = np.nanmean(s[sample])
    return np.nanpercentile(vals, 2.5), np.nanpercentile(vals, 97.5)


def report(df, label, h=100):
    """打印单个切片的统计量。"""
    if len(df) < 20:
        print(f"  {label:<40} n={len(df):>4}  (样本不足)")
        return None
    r = df[f"r{h}"]
    lo, hi = boot_cluster_ci(r, df.symbol + "|" + df.session_date.astype(str))
    m = r.mean() * 100
    pct_pos = (r > 0).mean() * 100
    sig = "***" if (lo > 0 or hi < 0) else ""
    print(f"  {label:<40} n={len(df):>4}  mean={m:+7.3f}%  "
          f"CI=[{lo*100:+.2f},{hi*100:+.2f}]  %pos={pct_pos:>4.0f}%  {sig}")
    return {"n": len(df), "mean": m, "ci_lo": lo*100, "ci_hi": hi*100, "pct_pos": pct_pos}


# ============ 假设检验 ============
def h1_basic_rebound(low_s):
    """H1: 低 s + 放量 vs baseline。"""
    print("\n" + "="*80)
    print("H1: 低 s + 放量后是否反弹？（CGW 预测正收益）")
    print("="*80)
    base = low_s[low_s.group == "base"]
    for g in ["spike", "extreme", "low_vol"]:
        sub = low_s[low_s.group == g]
        print(f"\n[{g}] vs base:")
        report(sub, g)
        report(base, "baseline")
        if len(sub) >= 20 and len(base) >= 20:
            diff = sub.r100.mean() - base.r100.mean()
            # bootstrap diff
            d_vals = []
            cs = sub.symbol + "|" + sub.session_date.astype(str)
            cb = base.symbol + "|" + base.session_date.astype(str)
            uc_s, uc_b = np.unique(cs), np.unique(cb)
            for _ in range(N_BOOT):
                is_ = np.concatenate([np.where(cs == c)[0] for c in RNG.choice(uc_s, len(uc_s), replace=True)])
                ib = np.concatenate([np.where(cb == c)[0] for c in RNG.choice(uc_b, len(uc_b), replace=True)])
                if len(is_) and len(ib):
                    d_vals.append(sub.r100.iloc[is_].mean() - base.r100.iloc[ib].mean())
            lo, hi = np.nanpercentile(d_vals, [2.5, 97.5])
            sig = "***" if (lo > 0 or hi < 0) else ""
            print(f"  {'Δ (spike-base)':<40}    diff={diff*100:+7.3f}%  CI=[{lo*100:+.2f},{hi*100:+.2f}]  {sig}")


def h2_madev_conditioning(low_s):
    """H2: 反弹强度是否依赖 MADEV（跌得离均线越远反弹越强）。"""
    print("\n" + "="*80)
    print("H2: MADEV 对低 s 反弹的调节作用")
    print("="*80)
    for g in ["spike", "extreme", "base"]:
        sub = low_s[low_s.group == g].copy()
        if len(sub) < 50:
            continue
        q33 = sub.madev120.quantile(0.33)
        q67 = sub.madev120.quantile(0.67)
        print(f"\n[{g}] 按 MADEV120 三分位:")
        for label, mask in [
            ("MADEV 低（远低于均线）", sub.madev120 <= q33),
            ("MADEV 中", (sub.madev120 > q33) & (sub.madev120 < q67)),
            ("MADEV 高（接近/高于均线）", sub.madev120 >= q67),
        ]:
            report(sub[mask], f"  {label}")
        if len(sub) >= 50:
            ic, _ = spearmanr(sub.madev120, sub.r100, nan_policy="omit")
            print(f"  IC(MADEV→r100) = {ic:+.3f}")


def h3_pateff(low_s):
    """H3: PATEFF 区分恐慌续跌 vs 出清反弹。"""
    print("\n" + "="*80)
    print("H3: PATEFF（路径效率）——平滑下跌+放量续跌？")
    print("="*80)
    for g in ["spike", "extreme", "base"]:
        sub = low_s[(low_s.group == g) & low_s.pateff100.notna()].copy()
        if len(sub) < 50:
            continue
        med = sub.pateff100.median()
        print(f"\n[{g}] 按 PATEFF 中位数 ({med:.3f}):")
        report(sub[sub.pateff100 <= med], "  PATEFF 低（震荡下跌）")
        report(sub[sub.pateff100 > med], "  PATEFF 高（平滑下跌）")


def h4_skew_interaction(low_s):
    """H4: 如果有 skew 数据，检验 skew 对低 s 反弹的区分。"""
    if "vp_skew" not in low_s.columns:
        print("\n[H4] 无 vp_skew 列，跳过。先运行 volume_profile_skew.py 生成。")
        return
    print("\n" + "="*80)
    print("H4: Volume Skew 在低 s 中区分好/坏放量")
    print("="*80)
    for g in ["spike", "extreme"]:
        sub = low_s[(low_s.group == g) & low_s.vp_skew.notna()].copy()
        if len(sub) < 40:
            print(f"  [{g}] n={len(sub)} 不足，跳过")
            continue
        sub["skew_z"] = (sub.vp_skew - sub.vp_skew.mean()) / sub.vp_skew.std()
        print(f"\n[{g}] 按 Skew ±1σ:")
        report(sub[sub.skew_z <= -1], "  Skew ≤ -1σ（高位派发）")
        report(sub[(sub.skew_z > -1) & (sub.skew_z < 1)], "  Skew 中间")
        report(sub[sub.skew_z >= 1], "  Skew ≥ +1σ（低位承接）")


def h5_rebound_path(low_s):
    """H5: 反弹的时间路径——半衰期、是否过度穿越。"""
    print("\n" + "="*80)
    print("H5: 反弹路径（20/40/60/80/100 bar）")
    print("="*80)
    for g in ["spike", "extreme", "base"]:
        sub = low_s[low_s.group == g]
        if len(sub) < 30:
            continue
        print(f"\n[{g}] n={len(sub)}")
        for H in HORIZONS:
            r = sub[f"r{H}"].dropna()
            mp = sub[f"madev_post_{H}"].dropna()
            if len(r) < 20:
                continue
            print(f"  H={H:>3}: mean r={r.mean()*100:+7.3f}%  "
                  f"MADEV_post={mp.mean()*100:+6.3f}%  "
                  f"%pos={(r>0).mean()*100:>4.0f}%")


# ============ 主入口 ============
def main():
    cache = OUT / "low_s_events.parquet"
    if cache.exists() and "--reuse" in sys.argv:
        ev = pd.read_parquet(cache)
        print(f"加载缓存: {len(ev):,} 事件")
    else:
        ev = collect_all()
        ev.to_parquet(cache, index=False)
        print(f"已保存: {cache}")

    low_s = ev[ev.s_pre <= S_THRESH].copy()
    print(f"\n低 s 层 (s_pre ≤ {S_THRESH}): {len(low_s):,} 事件")
    for g in ["base", "spike", "extreme", "low_vol"]:
        print(f"  {g:<10}: {(low_s.group==g).sum():>5}")

    h1_basic_rebound(low_s)
    h2_madev_conditioning(low_s)
    h3_pateff(low_s)
    h4_skew_interaction(low_s)
    h5_rebound_path(low_s)

    print("\n[OK]")


if __name__ == "__main__":
    main()
