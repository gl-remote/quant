"""
F3 · Realized vol 突破 · 强度识别因子候选

文件级元信息：
- 创建背景：experiment-plan.md · Wave 1 第 2 优先级
- 因子定义：过去 20 bar 的 realized vol · 归一化到长窗 60 · 突破阈值触发
  x_hat = max(0, RV_20 / RV_60 - 1) · 与 F1 结构类似但用对数收益 std 而非 TR
- 因果性：只用 t-60..t-1 · OK
- 预期结论：Gate 3 大概率失败（同 F1 · 波动率与漂移独立）
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORKBENCH = Path(__file__).parent.parent
sys.path.insert(0, str(WORKBENCH / "scripts"))

from _driver import (  # noqa: E402
    W_TRUTH,
    bind_kf27_params,
    compute_distribution_params,
    compute_x_truth_series,
    dump_report,
    evaluate_factor,
    format_report_md,
    load_1h_data,
    summary_row,
)

SLUG = "f3-realized-vol-breakout-20-60"
HYPOTHESIS = "Realized vol 短窗突破长窗 · x_hat = max(0, RV_20 / RV_60 - 1)"
W_SHORT = 20
W_LONG = 60


def factor_rv_breakout(df: pd.DataFrame) -> list[float]:
    """因子输出：max(0, RV_20 / RV_60 - 1)。"""
    out = [float("nan")] * len(df)
    for _, sub in df.groupby("contract"):
        arr = sub["log_ret"].to_numpy()
        base_idx = sub.index.to_numpy()
        for i in range(W_LONG, len(arr)):
            seg_short = arr[i - W_SHORT : i]
            seg_long = arr[i - W_LONG : i]
            rv_short = float(np.std(seg_short, ddof=1)) if len(seg_short) > 1 else 0.0
            rv_long = float(np.std(seg_long, ddof=1)) if len(seg_long) > 1 else 0.0
            if rv_long <= 0:
                continue
            out[int(base_idx[i])] = max(0.0, rv_short / rv_long - 1.0)
    return out


def main() -> None:
    print("[F3] 加载数据 · 3 合约 1h")
    df = load_1h_data()
    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F3] se_target={kf27['se_target']:.4f}")

    report = evaluate_factor(
        slug=SLUG, hypothesis=HYPOTHESIS,
        factor_fn=factor_rv_breakout,
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
