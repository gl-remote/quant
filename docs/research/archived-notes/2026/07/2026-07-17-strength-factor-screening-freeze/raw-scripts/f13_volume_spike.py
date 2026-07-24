"""
F13 · 成交量突增 · 强度识别因子候选

文件级元信息：
- 创建背景：Wave 3 · shaping-theory §5.5 候选清单中的"成交量放大"
  经典 MDH（Mixture of Distributions Hypothesis）：信息到达 → volume 突增 → 强漂移
- 因子定义：x_hat = max(0, V_20 / V_60 - 1) · 短窗成交量突破长窗
- 因果性：只用 t-60..t-1 · OK
- 与 F1/F3 的区别：波动率变化 vs 成交量变化 · 成交量是更直接的"信息到达"proxy
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

SLUG = "f13-volume-spike-20-60"
HYPOTHESIS = "V_20 / V_60 突破 · 短窗成交量放大表明信息到达 · MDH 假设"
W_SHORT = 20
W_LONG = 60


def factor_volume_spike(df: pd.DataFrame) -> list[float]:
    """因子输出：max(0, V_20 / V_60 - 1)。"""
    out = [float("nan")] * len(df)
    for _, sub in df.groupby("contract"):
        vol = sub["volume"].to_numpy().astype(float)
        base_idx = sub.index.to_numpy()
        for i in range(W_LONG, len(vol)):
            v_short = float(np.mean(vol[i - W_SHORT : i]))
            v_long = float(np.mean(vol[i - W_LONG : i]))
            if v_long <= 0:
                continue
            out[int(base_idx[i])] = max(0.0, v_short / v_long - 1.0)
    return out


def main() -> None:
    print("[F13] 加载数据 · 3 合约 1h")
    df = load_1h_data()
    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F13] se_target={kf27['se_target']:.4f}")

    report = evaluate_factor(
        slug=SLUG, hypothesis=HYPOTHESIS,
        factor_fn=factor_volume_spike,
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
