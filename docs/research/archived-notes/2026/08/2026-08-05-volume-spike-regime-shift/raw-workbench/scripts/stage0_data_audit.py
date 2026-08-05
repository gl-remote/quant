"""
文件级元信息：
- 创建背景：volume-spike-regime-shift 主题立题后的 Stage 0 数据审计。
- 用途：枚举 1h CSV → 过滤可纳入合约 → 计算 trailing-N 成交量 z-score
  （N=20，不含当根）→ 报告 Z 分布、各阈值实际命中率与 cluster 数。
- 注意事项：
  * 研究脚本，临时放 docs/workbench/；结论稳定后再归档。
  * 不依赖正态假设，阈值命中率以实测为准。
  * 每合约独立计算 rolling，不跨合约池化（KF-22）。
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.common.contract_specs import CONTRACT_SPECS  # noqa: E402
from workspace.common.symbol_utils import extract_contract_prefix  # noqa: E402
from workspace.data.output_paths import market_csv_dir  # noqa: E402

# ───────────────────── 常量 ─────────────────────

LOOKBACK_N = 20
MIN_BARS = 420
Z_THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
N_QUANTILES = (0.01, 0.05, 0.50, 0.95, 0.99, 0.999)


@dataclass
class ContractAudit:
    symbol: str
    prefix: str
    n_bars: int
    n_sessions: int
    first_dt: str
    last_dt: str
    z_mean: float
    z_std: float
    z_skew: float
    z_kurt: float
    z_quantiles: dict[str, float]
    hit_pos: dict[str, int]   # P(Z >= z0) 计数
    hit_neg: dict[str, int]   # P(Z <= -z0) 计数
    n_eligible: int           # rolling 成型后的 bar 数
    has_contract_spec: bool
    accepted: bool
    reject_reason: str


def _safe_float(x: float) -> float:
    if x is None or not math.isfinite(float(x)):
        return float("nan")
    return float(x)


def compute_z(volume: pd.Series, n: int = LOOKBACK_N) -> pd.Series:
    """Trailing 成交量 z-score，不含当根。

    对 t 行，用 [t-n, t-1] 的 mean/std 标准化 V_t。
    """
    hist_mean = volume.shift(1).rolling(n, min_periods=n).mean()
    hist_std = volume.shift(1).rolling(n, min_periods=n).std(ddof=1)
    z = (volume - hist_mean) / hist_std
    return z


def session_date_from_datetime(dt: pd.Series) -> pd.Series:
    """1h bar 的交易日切分：A 股期货夜盘算次日。

    简化规则（与 structural-shaping gatekeeper 对齐）：直接用 datetime.dt.date；
    夜盘 21:00–次日 02:30 的 bar 本身 datetime 就是次日凌晨，自然落到次日 date。
    1h 周期没有 15:00 收盘后的跨日处理需求。
    """
    return dt.dt.date


def audit_contract(csv_path: Path) -> ContractAudit | None:
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] read fail {csv_path.name}: {exc}", file=sys.stderr)
        return None

    required = {"datetime", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        return None

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    n_bars = len(df)

    symbol = csv_path.name.split(".tqsdk.1h.csv")[0]
    prefix = extract_contract_prefix(symbol) or ""

    has_spec = CONTRACT_SPECS.get_symbol(symbol) is not None

    reject_reason = ""
    accepted = True
    if n_bars < MIN_BARS:
        accepted = False
        reject_reason = f"n_bars={n_bars}<{MIN_BARS}"
    if not has_spec:
        accepted = False
        reject_reason = (reject_reason + ";" if reject_reason else "") + "no_contract_spec"

    df["z"] = compute_z(df["volume"], LOOKBACK_N)
    df["session_date"] = session_date_from_datetime(df["datetime"])
    df_eligible = df.dropna(subset=["z"]).copy()
    n_eligible = len(df_eligible)

    z = df_eligible["z"].to_numpy()
    if n_eligible < 50:
        accepted = False
        reject_reason = (reject_reason + ";" if reject_reason else "") + "n_eligible<50"

    if n_eligible > 0:
        z_mean = float(np.mean(z))
        z_std = float(np.std(z, ddof=1))
        z_skew = float(pd.Series(z).skew())
        z_kurt = float(pd.Series(z).kurt())  # excess kurtosis
        z_q = {f"p{int(q*1000)/10:g}": float(np.quantile(z, q)) for q in N_QUANTILES}
        hit_pos = {f"{z0:g}": int(np.sum(z >= z0)) for z0 in Z_THRESHOLDS}
        hit_neg = {f"{z0:g}": int(np.sum(z <= -z0)) for z0 in Z_THRESHOLDS}
    else:
        z_mean = z_std = z_skew = z_kurt = float("nan")
        z_q = {f"p{int(q*1000)/10:g}": float("nan") for q in N_QUANTILES}
        hit_pos = {f"{z0:g}": 0 for z0 in Z_THRESHOLDS}
        hit_neg = {f"{z0:g}": 0 for z0 in Z_THRESHOLDS}

    return ContractAudit(
        symbol=symbol,
        prefix=prefix,
        n_bars=int(n_bars),
        n_sessions=int(df_eligible["session_date"].nunique()),
        first_dt=str(df["datetime"].iloc[0]),
        last_dt=str(df["datetime"].iloc[-1]),
        z_mean=_safe_float(z_mean),
        z_std=_safe_float(z_std),
        z_skew=_safe_float(z_skew),
        z_kurt=_safe_float(z_kurt),
        z_quantiles=z_q,
        hit_pos=hit_pos,
        hit_neg=hit_neg,
        n_eligible=int(n_eligible),
        has_contract_spec=has_spec,
        accepted=accepted,
        reject_reason=reject_reason,
    )


def cluster_count(df: pd.DataFrame, z0: float) -> int:
    """统计 Z>=z0 事件覆盖的 (symbol, session_date) 簇数。"""
    hit = df[df["z"] >= z0]
    return int(hit.groupby(["symbol", "session_date"]).ngroups)


def main() -> int:
    csv_dir = market_csv_dir()
    files = sorted(csv_dir.glob("*.1h.csv"))
    print(f"[INFO] found {len(files)} 1h csv files under {csv_dir}")

    audits: list[ContractAudit] = []
    for p in files:
        a = audit_contract(p)
        if a is not None:
            audits.append(a)

    accepted = [a for a in audits if a.accepted]
    rejected = [a for a in audits if not a.accepted]

    print(f"[INFO] parsed={len(audits)} accepted={len(accepted)} rejected={len(rejected)}")

    # 聚合 Z 分布：把所有纳入合约的 z 拼起来（描述统计用，不用于推断）
    all_z: list[np.ndarray] = []
    event_frames: list[pd.DataFrame] = []
    for a in accepted:
        csv_path = csv_dir / f"{a.symbol}.tqsdk.1h.csv"
        df = pd.read_csv(csv_path)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df["z"] = compute_z(df["volume"], LOOKBACK_N)
        df["session_date"] = df["datetime"].dt.date
        df["symbol"] = a.symbol
        df["prefix"] = a.prefix
        all_z.append(df["z"].dropna().to_numpy())
        event_frames.append(df[["symbol", "prefix", "session_date", "datetime", "z"]].dropna())

    z_all = np.concatenate(all_z) if all_z else np.array([])

    # 命中率与 cluster
    threshold_table = []
    for z0 in Z_THRESHOLDS:
        n_hit_pos = int(np.sum(z_all >= z0))
        n_hit_neg = int(np.sum(z_all <= -z0))
        n_total = len(z_all)
        # cluster
        if event_frames:
            ev = pd.concat(event_frames, ignore_index=True)
            n_clusters_pos = int(ev[ev["z"] >= z0].groupby(["symbol", "session_date"]).ngroups)
            n_clusters_neg = int(ev[ev["z"] <= -z0].groupby(["symbol", "session_date"]).ngroups)
        else:
            n_clusters_pos = n_clusters_neg = 0
        # 正态参考
        from scipy.stats import norm  # type: ignore

        p_norm_pos = float(1 - norm.cdf(z0))
        empirical_pos = n_hit_pos / n_total if n_total else float("nan")
        ratio = empirical_pos / p_norm_pos if p_norm_pos > 0 else float("inf")
        threshold_table.append(
            {
                "z0": z0,
                "n_hit_pos": n_hit_pos,
                "n_hit_neg": n_hit_neg,
                "n_total": n_total,
                "p_pos_empirical": empirical_pos,
                "p_neg_empirical": n_hit_neg / n_total if n_total else float("nan"),
                "p_pos_normal": p_norm_pos,
                "heavy_tail_ratio_pos": ratio,
                "n_clusters_pos": n_clusters_pos,
                "n_clusters_neg": n_clusters_neg,
            }
        )

    # 全局 Z 描述
    z_desc = {
        "n_total": int(len(z_all)),
        "mean": float(np.mean(z_all)) if len(z_all) else float("nan"),
        "std": float(np.std(z_all, ddof=1)) if len(z_all) else float("nan"),
        "skew": float(pd.Series(z_all).skew()) if len(z_all) else float("nan"),
        "kurt_excess": float(pd.Series(z_all).kurt()) if len(z_all) else float("nan"),
        "quantiles": {f"p{int(q*1000)/10:g}": float(np.quantile(z_all, q)) for q in N_QUANTILES}
        if len(z_all)
        else {},
    }

    # 按前缀汇总
    by_prefix: dict[str, dict[str, float]] = {}
    for a in accepted:
        d = by_prefix.setdefault(
            a.prefix,
            {"contracts": 0, "n_eligible": 0, "sessions": 0},
        )
        d["contracts"] += 1
        d["n_eligible"] += a.n_eligible
        d["sessions"] += a.n_sessions

    report = {
        "lookback_n": LOOKBACK_N,
        "min_bars": MIN_BARS,
        "csv_dir": str(csv_dir),
        "files_found": len(files),
        "parsed": len(audits),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "z_description": z_desc,
        "thresholds": threshold_table,
        "by_prefix": by_prefix,
        "contracts": [asdict(a) for a in audits],
    }

    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "stage0_audit.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print(f"[OK] wrote {out_path}")

    # 控制台简报
    print("\n=== Z description (pooled, eligible bars) ===")
    print(
        f"n={z_desc['n_total']} mean={z_desc['mean']:.3f} std={z_desc['std']:.3f} "
        f"skew={z_desc['skew']:.3f} kurt_excess={z_desc['kurt_excess']:.3f}"
    )
    print("quantiles:", {k: round(v, 3) for k, v in z_desc["quantiles"].items()})
    print("\n=== Threshold hits ===")
    print(
        f"{'z0':>5} {'P(Z>=z0)':>12} {'P(Z<=-z0)':>12} "
        f"{'normal+':>10} {'ratio':>10} {'n_evt+':>10} {'n_clu+':>10} {'tier':>14}"
    )
    for row in threshold_table:
        if row["n_clusters_pos"] >= 200:
            tier = "full"
        elif row["n_clusters_pos"] >= 30:
            tier = "medium"
        else:
            tier = "descriptive-only"
        print(
            f"{row['z0']:>5.1f} {row['p_pos_empirical']:>12.4%} {row['p_neg_empirical']:>12.4%} "
            f"{row['p_pos_normal']:>10.2e} {row['heavy_tail_ratio_pos']:>10.2f} "
            f"{row['n_hit_pos']:>10d} {row['n_clusters_pos']:>10d} {tier:>14}"
        )

    print("\n=== By prefix (accepted) ===")
    for pfx, d in sorted(by_prefix.items()):
        print(f"  {pfx:>6}: contracts={d['contracts']} n_eligible={d['n_eligible']} sessions={d['sessions']}")

    if rejected:
        print("\n=== Rejected ===")
        for a in rejected:
            print(f"  {a.symbol}: {a.reject_reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
