"""
F14 · 交易时段效应 · 强度识别因子候选

文件级元信息：
- 创建背景：Wave 3 · 内生因子穷尽后，测试"日内时段"这种可观测的制度切换
- 因子定义：按时段（早盘 / 午盘 / 夜盘）分组的历史平均 x^真 作为因子
  · 因果性：用截至 t-1 的滚动历史均值，不使用未来数据
  · 直觉：中国期货不同时段参与者结构不同 → 系统性强度差异
- 与其他因子的区别：不是"过去统计量预测未来"，而是"制度标签"
  · 时段本身就是未来窗口的一部分 → 有预测力是正常的（制度效应）
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

SLUG = "f14-time-of-day-session"
HYPOTHESIS = "交易时段效应 · 早盘/午盘/夜盘 制度切换 → 系统性强度差异"


def get_session(hour: int) -> str:
    """按时段分组：早盘(09-11) / 午盘(13-14) / 夜盘(21-23)。"""
    if 9 <= hour < 12:
        return "morning"
    elif 13 <= hour < 15:
        return "afternoon"
    elif 21 <= hour < 24:
        return "night"
    else:
        return "other"


def factor_time_of_day(df: pd.DataFrame) -> list[float]:
    """因子输出：截至 t-1 的各时段滚动平均 x^真（因果实现）。

    由于 x^真 本身是未来窗口，我们不能直接用。
    这里采用代理：用过去 W_TRUTH bar 的已实现 |ν|/σ 按时段分组，
    对每个 bar 输出其所属时段的历史均值。

    更简单的实现：先在全量数据上算每个 bar 的"过去 x 代理"，
    然后按时段分组做滚动平均。
    """
    n = len(df)
    out = [float("nan")] * n

    for _, sub in df.groupby("contract"):
        sub = sub.sort_values("datetime").reset_index()
        log_ret = sub["log_ret"].to_numpy().astype(float)
        hours = sub["datetime"].dt.hour.to_numpy()
        orig_idx = sub["index_0"].to_numpy() if "index_0" in sub.columns else sub.index.to_numpy()

        # 构造"过去 |ν|/σ 代理"：对每个 t，用 t-W_TRUTH..t-1 的窗口
        past_x = np.full(len(sub), np.nan)
        for i in range(W_TRUTH, len(sub)):
            seg = log_ret[i - W_TRUTH : i]
            mu = float(np.mean(seg))
            sd = float(np.std(seg, ddof=1))
            if sd > 0:
                past_x[i] = abs(mu) / sd

        # 按时段分组，计算滚动均值（因果：只用到 i-1）
        session_stats: dict[str, list[float]] = {"morning": [], "afternoon": [], "night": [], "other": []}

        for i in range(len(sub)):
            sess = get_session(int(hours[i]))
            # 当前 bar 的因子 = 该时段历史平均（不含当前 bar）
            history = session_stats[sess]
            if len(history) >= 3:
                out[int(orig_idx[i])] = float(np.mean(history))
            # 将当前 bar 的 past_x 加入该时段历史（供未来 bar 使用）
            if np.isfinite(past_x[i]):
                session_stats[sess].append(float(past_x[i]))

    return out


def main() -> None:
    print("[F14] 加载数据 · 3 合约 1h")
    df = load_1h_data()

    # 额外分析：各时段的 x^真 分布差异
    x_truth, truth_indices = compute_x_truth_series(df, w=W_TRUTH)
    truth_hours = df.loc[truth_indices, "datetime"].dt.hour.tolist()
    truth_sessions = [get_session(h) for h in truth_hours]

    print("\n[F14] 各时段真值 x^真 分布：")
    for sess in ["morning", "afternoon", "night"]:
        vals = [x for x, s in zip(x_truth, truth_sessions, strict=True) if s == sess]
        if vals:
            print(f"  {sess:12s}: n={len(vals):3d}  mean={np.mean(vals):.4f}  "
                  f"std={np.std(vals, ddof=1):.4f}  q90={np.quantile(vals, 0.90):.4f}")

    mu_D, sd_D = compute_distribution_params(x_truth)
    kf27 = bind_kf27_params(mu_D, sd_D)
    print(f"\n[F14] se_target={kf27['se_target']:.4f}")

    report = evaluate_factor(
        slug=SLUG, hypothesis=HYPOTHESIS,
        factor_fn=factor_time_of_day,
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
