"""
F1 · ATR 拐点 · 强度识别因子候选

文件级元信息：
- 创建背景：experiment-plan.md · Wave 1 第 3 优先级
- 因子定义：过去 20 bar 的 ATR 变化率 · ATR 快速上升 → 波动率制度切换 → 强段候选
  x_hat = max(0, ATR_20 / ATR_60 - 1)  · 归一到非负强度
- 因果性：只用 t-60..t-1 的 TR · 结构 OK
- 预期结论：Gate 1.5 大概率过（因子输出接近 [0, 0.5] 与真值同量级）· Gate 1 待观察
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

SLUG = "f1-atr-turning-20-60"
HYPOTHESIS = "ATR(20)/ATR(60) 拐点 · 短窗 ATR 快速上升表明波动率制度切换 · 强段候选"
W_SHORT = 20
W_LONG = 60


def _tr(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """True Range · 长度与 close 相同 · 首行 NaN。"""
    tr = np.zeros(len(close))
    tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return tr


def factor_atr_turning(df: pd.DataFrame) -> list[float]:
    """因子输出：max(0, ATR_20 / ATR_60 - 1)。"""
    out = [float("nan")] * len(df)
    for _, sub in df.groupby("contract"):
        high = sub["high"].to_numpy()
        low = sub["low"].to_numpy()
        close = sub["close"].to_numpy()
        base_idx = sub.index.to_numpy()
        tr = _tr(high, low, close)
        for i in range(W_LONG, len(tr)):
            atr_short = float(np.mean(tr[i - W_SHORT : i]))
            atr_long = float(np.mean(tr[i - W_LONG : i]))
            if atr_long <= 0:
                continue
            out[int(base_idx[i])] = max(0.0, atr_short / atr_long - 1.0)
    return out


def main() -> None:
    print("[F1] 加载数据 · 3 合约 1h")
    df = load_1h_data()
    print(f"  bars total: {len(df)}")

    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    mu_D, sd_D = compute_distribution_params(x_truth)
    print(f"[F1] 分布：(mu_D, sd_D) = ({mu_D:.4f}, {sd_D:.4f})")

    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"[F1] KF-27: K_S*={kf27['k_s']:.2f} K_T*={kf27['k_t']:.2f} "
          f"tau*={kf27['tau']:.3f} x*={kf27['x_star']:.4f} "
          f"se_target={kf27['se_target']:.4f}")

    report = evaluate_factor(
        slug=SLUG,
        hypothesis=HYPOTHESIS,
        factor_fn=factor_atr_turning,
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
    print(f"\n[F1] JSON dumped: {out}")
    print("\n=== Markdown 报告片段 ===\n")
    print(format_report_md(report))
    print(f"\n=== 一行汇总 ===\n{summary_row(report)}")


if __name__ == "__main__":
    main()
