"""
F11 · 20h 窗口回归（预期失败对照）· 强度识别因子候选

文件级元信息：
- 创建背景：experiment-plan.md · Wave 1 第 4 优先级 · shaping-theory §2.23.5.5
  已理论证明"窗口回归天然 se ≈ 1/√N ≈ 0.224，远超 se_target ≈ 0.047"。
  跑一次归档为反例登记（"证伪已完成"）。
- 因子定义：x_hat_t = |mean(log_ret[t-W..t])| / std(log_ret[t-W..t])，
  W = 20（1h）· 因果性 OK（只用历史窗口）。
- 预期结论：Gate 1 SE 失败 · se_hat ≈ 0.22 · 4.8× 超阈 · 归 L4 反例
- 用途：验证 driver 正确性 + 归档 shaping-theory §2.23.5.5 的证伪
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

SLUG = "f11-window-regression-20h"
HYPOTHESIS = "20h 窗口对数收益 (mean/std) 直接估计 |ν|/σ · shaping-theory §2.23.5.5 预期失败"
W_FACTOR = 20  # 因子窗口 · 与真值窗口同长（1h 主题标准）


def factor_window_regression(df: pd.DataFrame) -> list[float]:
    """因子输出：每 bar 输出过去 W_FACTOR bar 的 |mean|/std。

    因果性 OK · 只用 t-W..t-1 的对数收益。
    """
    out = [float("nan")] * len(df)
    for _, sub in df.groupby("contract"):
        arr = sub["log_ret"].to_numpy()
        base_idx = sub.index.to_numpy()
        for i in range(W_FACTOR, len(arr)):
            seg = arr[i - W_FACTOR : i]
            if len(seg) < 5:
                continue
            mu = float(np.mean(seg))
            sd = float(np.std(seg, ddof=1))
            if sd <= 0:
                continue
            out[int(base_idx[i])] = abs(mu) / sd
    return out


def main() -> None:
    print("[F11] 加载数据 · 3 合约 1h")
    df = load_1h_data()
    print(f"  bars total: {len(df)}")

    print(f"[F11] 构造真值 x^真(W={W_TRUTH})")
    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    print(f"  x_truth points: {len(x_truth)}")

    print("[F11] KF-27 参数绑定")
    mu_D, sd_D = compute_distribution_params(x_truth)
    print(f"  (mu_D, sd_D) = ({mu_D:.4f}, {sd_D:.4f})")
    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"  K_S*={kf27['k_s']:.2f} K_T*={kf27['k_t']:.2f} tau*={kf27['tau']:.3f} "
          f"x*={kf27['x_star']:.4f}")
    print(f"  x_min={kf27['x_min']:.4f} se_target={kf27['se_target']:.4f}")

    print("[F11] 计算因子输出 x_hat")
    report = evaluate_factor(
        slug=SLUG,
        hypothesis=HYPOTHESIS,
        factor_fn=factor_window_regression,
        df=df,
        x_truth_all=x_truth,
        truth_indices=truth_indices,
        kf27=kf27,
    )

    print("\n=== 判决 ===")
    print(f"  accepted={report.accepted} reject={report.reject_reason} level={report.level}")
    print(f"  se_hat={report.gate1_se_hat:.4f} vs se_target={kf27['se_target']:.4f} "
          f"(ratio={report.gate1_se_hat / kf27['se_target']:.2f}x)")

    out_dir = WORKBENCH / "outputs"
    out = dump_report(report, out_dir)
    print(f"\n[F11] JSON dumped: {out}")

    print("\n=== Markdown 报告片段 ===\n")
    print(format_report_md(report))

    print(f"\n=== 一行汇总 ===\n{summary_row(report)}")


if __name__ == "__main__":
    main()
