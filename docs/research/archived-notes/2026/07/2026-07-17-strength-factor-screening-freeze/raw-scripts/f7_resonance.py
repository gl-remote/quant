"""
F7 · 横截面共振（农产品板块）· 强度识别因子候选

文件级元信息：
- 创建背景：experiment-plan.md · Wave 2 优先候选 · shaping-theory §2.22.7
  假设：同板块 ≥3 品种同向且强漂移 → 板块共振 → 强段候选
- 因子定义：对每个 t · 计算板块内 N 品种在过去 W_STAT bar 的对数收益方向一致性 +
  平均强度 · x_hat = |mean_sign| * mean_|nu|/σ
- 板块选择：农产品（c / m / p / cs · 4 品种齐全 · 玉米淀粉、豆粕、棕榈油、玉米）
- 目标品种：玉米 c 系（作为主题基准 · 保持与 Wave 1 可对比）
- 因果性：t 时刻只用 t-W..t-1 · OK
- 数据对齐：4 品种按 datetime inner join · 只在四品种都有数据的 bar 上算板块信号
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

SLUG = "f7-cross-sectional-resonance-4syms"
HYPOTHESIS = "同板块 4 品种（c/m/p/cs）过去 W=20 bar 的方向一致性 × 平均漂移强度 → 板块共振信号"
W_STAT = 20  # 板块统计窗口
SECTOR = ["DCE.c2601", "DCE.m2601", "DCE.p2601", "DCE.cs2601"]
TARGET = "DCE.c2601"  # 目标品种（与 Wave 1 保持可比 · 但只用 1 合约 · 424 bars）


def load_sector() -> pd.DataFrame:
    """加载板块内 4 品种 · 按 datetime inner join · 每 bar 一行 · 每品种一列 log_ret。"""
    frames = {}
    for sym in SECTOR:
        df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.{PERIOD}.csv", parse_dates=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df["log_ret"] = np.log(df["close"]).diff()
        df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
        frames[sym] = df.set_index("datetime")[["log_ret", "close", "high", "low"]]
    # inner join
    combined = pd.concat(frames, axis=1, join="inner")
    combined.columns = [f"{sym}__{col}" for sym, col in combined.columns]
    return combined.reset_index()


def build_target_df(sector_df: pd.DataFrame) -> pd.DataFrame:
    """把 sector inner-joined df 转成 driver 兼容格式（假装成 3 合约的 concat · 这里只有 1 品种目标）。"""
    # 目标品种的 OHLC + log_ret
    df = pd.DataFrame({
        "datetime": sector_df["datetime"],
        "close": sector_df[f"{TARGET}__close"],
        "high": sector_df[f"{TARGET}__high"],
        "low": sector_df[f"{TARGET}__low"],
        "log_ret": sector_df[f"{TARGET}__log_ret"],
    })
    df["symbol"] = "DCE.c"
    df["contract"] = TARGET.split(".")[-1]  # 单合约 cluster
    return df.reset_index(drop=True)


def factor_resonance(df: pd.DataFrame, sector_df: pd.DataFrame) -> list[float]:
    """因子输出：过去 W_STAT bar 板块 4 品种的 |方向一致性| × 平均强度。

    对每个 t（在 df 中的行 · datetime 与 sector_df 对齐）：
        1. 提取过去 W_STAT bar · 4 品种每个的 log_ret 序列
        2. 每品种算 sign(mean_return) · 得到 4 个 ±1
        3. mean_sign = mean(4 个 sign) · 绝对值即"方向一致性" ∈ [0, 1]
        4. 每品种算 |mean| / std · 得到 4 个强度
        5. mean_intensity = mean(4 个强度)
        6. x_hat = mean_sign_abs × mean_intensity
    """
    out = [float("nan")] * len(df)
    # sector_df 已按 datetime 排序 · 用位置索引直接对齐
    n = len(df)
    assert len(sector_df) == n, f"length mismatch {len(sector_df)} vs {n}"

    for i in range(W_STAT, n):
        signs = []
        intensities = []
        for sym in SECTOR:
            seg = sector_df[f"{sym}__log_ret"].iloc[i - W_STAT : i].to_numpy()
            if len(seg) < 5:
                continue
            mu = float(np.mean(seg))
            sd = float(np.std(seg, ddof=1))
            if sd <= 0:
                continue
            signs.append(1.0 if mu > 0 else (-1.0 if mu < 0 else 0.0))
            intensities.append(abs(mu) / sd)
        if len(signs) < len(SECTOR):
            continue
        mean_sign_abs = abs(float(np.mean(signs)))
        mean_intensity = float(np.mean(intensities))
        out[i] = mean_sign_abs * mean_intensity
    return out


def main() -> None:
    print(f"[F7] 加载板块 · {SECTOR}")
    sector_df = load_sector()
    print(f"  inner joined bars: {len(sector_df)}")

    df = build_target_df(sector_df)
    print(f"  target (single contract): {len(df)} bars")

    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    print(f"[F7] 分布 (target c2601): (mu_D, sd_D) = ({mu_D:.4f}, {sd_D:.4f})")

    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F7] KF-27: K_S*={kf27['k_s']:.2f} K_T*={kf27['k_t']:.2f} "
          f"tau*={kf27['tau']:.3f} x*={kf27['x_star']:.4f} "
          f"se_target={kf27['se_target']:.4f}")

    def factor_fn(target_df: pd.DataFrame) -> list[float]:
        # sector_df 从闭包捕获
        return factor_resonance(target_df, sector_df)

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
