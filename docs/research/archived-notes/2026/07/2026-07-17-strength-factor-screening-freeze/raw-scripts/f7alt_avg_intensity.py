"""
F7-alt · 板块共振（放宽方向要求）· 强度识别因子候选

文件级元信息：
- 相对 F7 的变体：不强制方向一致 · 直接用板块 4 品种的**平均强度 |mean|/std** 作为 x_hat
  · 因子表达式：x_hat = mean_i(|mean(log_ret_i)| / std(log_ret_i))
- 假设：板块横截面平均强度 → 系统性宏观漂移 → 目标品种也可能强
- 目的：判断"共振"效应是否只在"方向一致"下有效 · 还是横截面平均本身就有信息
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORKBENCH = Path(__file__).parent.parent
sys.path.insert(0, str(WORKBENCH / "scripts"))

from _driver import (  # noqa: E402
    CSV_DIR,
    PERIOD,
    W_TRUTH,
    bind_kf27_params,
    compute_distribution_params,
    compute_x_truth_series,
    dump_report,
    evaluate_factor,
    format_report_md,
    summary_row,
)

SLUG = "f7alt-cross-sectional-avg-intensity"
HYPOTHESIS = "板块 4 品种（c/m/p/cs）平均 |ν|/σ 作为共振信号（放宽方向一致要求）"
W_STAT = 20
SECTOR = ["DCE.c2601", "DCE.m2601", "DCE.p2601", "DCE.cs2601"]
TARGET = "DCE.c2601"


def load_sector() -> pd.DataFrame:
    frames = {}
    for sym in SECTOR:
        df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.{PERIOD}.csv", parse_dates=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df["log_ret"] = np.log(df["close"]).diff()
        df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
        frames[sym] = df.set_index("datetime")[["log_ret", "close", "high", "low"]]
    combined = pd.concat(frames, axis=1, join="inner")
    combined.columns = [f"{sym}__{col}" for sym, col in combined.columns]
    return combined.reset_index()


def build_target_df(sector_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "datetime": sector_df["datetime"],
        "close": sector_df[f"{TARGET}__close"],
        "high": sector_df[f"{TARGET}__high"],
        "low": sector_df[f"{TARGET}__low"],
        "log_ret": sector_df[f"{TARGET}__log_ret"],
    })
    df["symbol"] = "DCE.c"
    df["contract"] = TARGET.split(".")[-1]
    return df.reset_index(drop=True)


def factor_avg_intensity(df: pd.DataFrame, sector_df: pd.DataFrame) -> list[float]:
    """因子输出：板块 4 品种过去 W_STAT bar 平均 |mean|/std（不做方向一致要求）。"""
    out = [float("nan")] * len(df)
    n = len(df)
    assert len(sector_df) == n
    for i in range(W_STAT, n):
        vals = []
        for sym in SECTOR:
            seg = sector_df[f"{sym}__log_ret"].iloc[i - W_STAT : i].to_numpy()
            if len(seg) < 5:
                continue
            mu = float(np.mean(seg))
            sd = float(np.std(seg, ddof=1))
            if sd <= 0:
                continue
            vals.append(abs(mu) / sd)
        if len(vals) < len(SECTOR):
            continue
        out[i] = float(np.mean(vals))
    return out


def main() -> None:
    print(f"[F7-alt] 加载板块 · {SECTOR}")
    sector_df = load_sector()
    df = build_target_df(sector_df)
    print(f"  bars: {len(df)}")

    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F7-alt] se_target={kf27['se_target']:.4f}")

    def factor_fn(target_df: pd.DataFrame) -> list[float]:
        return factor_avg_intensity(target_df, sector_df)

    report = evaluate_factor(
        slug=SLUG, hypothesis=HYPOTHESIS,
        factor_fn=factor_fn,
        df=df, x_truth_all=x_truth, truth_indices=truth_indices, kf27=kf27,
    )

    print("\n=== 判决 ===")
    print(f"  accepted={report.accepted} reject={report.reject_reason} level={report.level}")
    print(f"  se_hat={report.gate1_se_hat:.4f} vs se_target={kf27['se_target']:.4f} "
          f"(ratio={report.gate1_se_hat / kf27['se_target']:.2f}x)")

    dump_report(report, WORKBENCH / "outputs")
    print(f"\n{format_report_md(report)}\n")
    print(f"=== 一行汇总 ===\n{summary_row(report)}")


if __name__ == "__main__":
    main()
