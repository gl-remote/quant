"""
F5 · Hurst 窗口 · 强度识别因子候选

文件级元信息：
- 创建背景：experiment-plan.md · Wave 1 第 1 优先级 · shaping-theory §2.12.4 KF-16
  实测 1h 上 Hurst 均值 0.603 · 强趋势凝聚
- 因子定义：60 bar 窗口 R/S 分析得 Hurst H · 线性映射 x_hat = max(0, 2·(H - 0.5))
  · H 越高（趋势凝聚强）→ x_hat 越大
- 因果性：只用 t - K .. t - 1 的对数收益 · 结构 OK
- 预期结论：Gate 1 边缘（依赖映射斜率对齐）· 若 se_hat ≈ se_target → L1 或 L2
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
from research import hurst_rs  # noqa: E402

SLUG = "f5-hurst-60"
HYPOTHESIS = "60 bar Hurst R/S 指数 · 线性映射 max(0, 2·(H - 0.5)) → x_hat · H>0.5 → 趋势凝聚 → 强度高"
W_HURST = 60


def factor_hurst(df: pd.DataFrame) -> list[float]:
    """因子输出：过去 60 bar 的 Hurst 指数线性映射到 x_hat。"""
    out = [float("nan")] * len(df)
    for _, sub in df.groupby("contract"):
        arr = sub["log_ret"].to_numpy()
        base_idx = sub.index.to_numpy()
        for i in range(W_HURST, len(arr)):
            seg = arr[i - W_HURST : i]
            if len(seg) < W_HURST:
                continue
            try:
                # Hurst R/S · 允许窗口 8, 16, 32
                h = hurst_rs(seg.tolist(), min_window=8, max_window=32)
            except (ValueError, RuntimeError):
                continue
            if not np.isfinite(h):
                continue
            # 线性映射 · H=0.5 → 0 · H=1.0 → 1.0
            out[int(base_idx[i])] = max(0.0, 2.0 * (h - 0.5))
    return out


def main() -> None:
    print("[F5] 加载数据 · 3 合约 1h")
    df = load_1h_data()
    print(f"  bars total: {len(df)}")

    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    print(f"[F5] 分布：(mu_D, sd_D) = ({mu_D:.4f}, {sd_D:.4f})")

    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F5] KF-27: K_S*={kf27['k_s']:.2f} K_T*={kf27['k_t']:.2f} "
          f"tau*={kf27['tau']:.3f} x*={kf27['x_star']:.4f} "
          f"se_target={kf27['se_target']:.4f}")

    report = evaluate_factor(
        slug=SLUG,
        hypothesis=HYPOTHESIS,
        factor_fn=factor_hurst,
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
    print(f"\n[F5] JSON dumped: {out}")

    print("\n=== Markdown 报告片段 ===\n")
    print(format_report_md(report))

    print(f"\n=== 一行汇总 ===\n{summary_row(report)}")


if __name__ == "__main__":
    main()
