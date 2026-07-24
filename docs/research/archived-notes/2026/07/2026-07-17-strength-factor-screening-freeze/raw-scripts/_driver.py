"""
strength-factor-screening 主题 · 共享数据管道 driver

文件级元信息：
- 创建背景：Wave 1 (F1/F3/F5/F11) 都在玉米 3 合约 1h 数据上跑同一套流程——
  KF-27 参数绑定 + 真值 x^真(W=20) 构造 + Step 4-6 gate + §7 分级判决。
  抽出共享逻辑避免每个因子 driver 重复 200 行样板。
- 用途：给每个因子 driver 提供 (mu_D, sd_D, KF-27 参数, x_hat_series, x_truth_series,
  cluster_key) 就能立即得到 ScreeningResult + 分级判决。
- 注意事项：本 driver 是实验性 workbench 脚本，稳定后可下沉到 research 业务域。
  数据源硬编码到 project_data/market_data/csv/DCE.c260*.tqsdk.1h.csv。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from research import (
    FoldedNormal,
    KF27Params,
    ScreeningResult,
    cluster_bootstrap,
    optimize_kf27,
    run_screening,
    se_target,
    x_min_smallx,
)

# 数据路径
REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

# 玉米 1h 主题参数
PERIOD = "1h"
SIGMA_BAR = 1.0
YEAR_HOURS = 1625.0
C_SIDE = 0.077
W_TRUTH = 20  # 真值窗口（bar）
STRIDE = 1  # 评估点滑动步长（保守取 1，每个 bar 都评估）


@dataclass
class CandidateReport:
    """单个候选因子完整报告。"""

    slug: str
    hypothesis: str
    kf27_k_s: float
    kf27_k_t: float
    kf27_tau: float
    kf27_x_star: float
    kf27_n_year: float
    kf27_sharpe_year: float
    x_min: float
    se_target_value: float
    n_bars_eval: int
    n_clusters: int
    x_hat_mean: float
    x_hat_std: float
    x_hat_q90: float
    x_truth_mean: float
    x_truth_std: float
    x_truth_q90: float
    accepted: bool
    reject_reason: str | None
    level: str  # L1 / L2 / L3 / L4
    gate1_se_hat: float
    gate1_passed: bool
    gate1_ci_high: float | None
    gate1_5_passed: bool | None
    gate1_5_reasons: list[str]
    gate1_5_remedy: str | None
    gate2_ratio: float
    gate2_passed: bool
    gate3_r_hat: float
    gate3_passed: bool


def load_1h_data() -> pd.DataFrame:
    """加载 3 合约 1h 数据 · 每 bar 打上 (symbol, contract) cluster 标签。"""
    frames = []
    for sym in SYMBOLS:
        df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.{PERIOD}.csv", parse_dates=["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        df["symbol"] = "DCE.c"  # 品种
        df["contract"] = sym.split(".")[-1]  # c2601 / c2603 / c2605
        df["log_ret"] = np.log(df["close"]).diff()
        df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def compute_x_truth_series(df: pd.DataFrame, w: int = W_TRUTH) -> tuple[list[float], list[int]]:
    """构造真值代理序列 x^真_t(W) = |mean(log_ret[t:t+W])| / std(log_ret[t:t+W])。

    Returns:
        (x_truth 值列表, 对应的原 df index)
    """
    x_truth: list[float] = []
    indices: list[int] = []
    for _contract, sub in df.groupby("contract"):
        arr = sub["log_ret"].to_numpy()
        base_idx = sub.index.to_numpy()
        for i in range(0, len(arr) - w, STRIDE):
            seg = arr[i : i + w]
            if len(seg) < 5:
                continue
            mu = float(np.mean(seg))
            sd = float(np.std(seg, ddof=1))
            if sd <= 0:
                continue
            x_truth.append(abs(mu) / sd)
            indices.append(int(base_idx[i]))
    return x_truth, indices


def compute_distribution_params(x_truth: list[float]) -> tuple[float, float]:
    """从真值序列拟合 (mu_D, sd_D)。"""
    arr = np.array(x_truth)
    return float(np.mean(arr)), float(np.std(arr, ddof=1))


def bind_kf27_params(mu_D: float, sd_D: float) -> dict[str, float]:
    """KF-27 反解最优 (K_S*, K_T*, τ*, x*)。"""
    D = FoldedNormal(mu_D=mu_D, sd_D=sd_D).fit()
    params = KF27Params(
        distribution=D,
        c_side=C_SIDE,
        sigma_bar=SIGMA_BAR,
        year_hours=YEAR_HOURS,
    )
    kf27 = optimize_kf27(params, objective="sharpe_year")
    x_min = x_min_smallx(c_side=C_SIDE, k_s=kf27.k_s, k_t=kf27.k_t)
    se_tgt = se_target(x_star=kf27.x_star, x_min=x_min)
    return {
        "k_s": kf27.k_s,
        "k_t": kf27.k_t,
        "rr": kf27.rr,
        "tau": kf27.tau,
        "x_star": kf27.x_star,
        "n_year": kf27.n_year,
        "sharpe_year": kf27.sharpe_year,
        "x_min": x_min,
        "se_target": se_tgt,
    }


def _grade_level(result: ScreeningResult, se_target_value: float) -> str:
    """按 screening-methodology §7.1 分级。"""
    if result.accepted:
        return "L1"
    reason = result.reject_reason
    if reason == "Gate1":
        se_hat = result.gate1.se_hat
        ratio = se_hat / se_target_value
        if ratio <= 1.2:
            return "L2"
        if ratio <= 3.0:
            return "L3"
        return "L4"
    if reason == "Gate1_5":
        g15 = result.gate1_5
        if g15 is None:
            return "L4"
        if g15.remedy_hint == "degenerate":
            return "L4"
        if g15.remedy_hint in ("rescale", "reweight_tail"):
            return "L3"  # 可修 · 但当前样本仍 fail
        return "L3"
    if reason == "Gate2":
        return "L2"  # 覆盖率不足可融合稀释
    if reason == "Gate3":
        r = result.gate3.r_hat
        return "L3" if r >= 0.20 else "L4"
    return "L4"


def evaluate_factor(
    slug: str,
    hypothesis: str,
    factor_fn: Callable[[pd.DataFrame], list[float]],
    df: pd.DataFrame,
    x_truth_all: list[float],
    truth_indices: list[int],
    kf27: dict[str, float],
    bootstrap_seed: int = 42,
) -> CandidateReport:
    """跑一个因子的完整筛选流程 · 输出 CandidateReport。

    Args:
        slug: 候选因子 slug
        hypothesis: 因子假设一句话
        factor_fn: 输入 df (含 log_ret + 每合约起点)，输出 x_hat 序列 · 长度与 df 相同
        df: load_1h_data() 输出
        x_truth_all: compute_x_truth_series 的值
        truth_indices: compute_x_truth_series 对应的 df index
        kf27: bind_kf27_params 输出
    """
    # 因子先在整个 df 上算 x_hat（每 bar 一个）· 然后按 truth_indices 对齐
    x_hat_full = factor_fn(df)
    assert len(x_hat_full) == len(df), f"factor_fn 输出长度必须与 df 一致，got {len(x_hat_full)} vs {len(df)}"

    # 对齐到评估集
    x_hat = [x_hat_full[i] for i in truth_indices]
    x_truth = x_truth_all
    # 只保留有限 non-negative 值
    filtered = [(h, t, idx) for h, t, idx in zip(x_hat, x_truth, truth_indices, strict=True)
                if np.isfinite(h) and np.isfinite(t) and h >= 0]
    x_hat = [h for h, _, _ in filtered]
    x_truth = [t for _, t, _ in filtered]
    used_indices = [idx for _, _, idx in filtered]

    n = len(x_hat)
    clusters = df.loc[used_indices, "contract"].tolist()
    n_clusters = len(set(clusters))

    # 主 gate 判决
    result = run_screening(
        x_hat=x_hat,
        x_truth=x_truth,
        x_min=kf27["x_min"],
        x_star=kf27["x_star"],
        n_bars_total=n,
        year_bars=YEAR_HOURS,
        n_year_star=kf27["n_year"],
    )

    # Gate 1 严格版 · cluster bootstrap CI（可能耗时，采样 1000 次即可）
    if result.gate1.passed:
        events = [
            {"x_hat": h, "x_truth": t, "contract": c}
            for h, t, c in zip(x_hat, x_truth, clusters, strict=True)
        ]
        def _rms(evts):
            if not evts:
                return float("nan")
            return float(np.sqrt(np.mean([(e["x_hat"] - e["x_truth"]) ** 2 for e in evts])))
        boot = cluster_bootstrap(
            events=events,
            cluster_key=lambda e: e["contract"],
            statistic=_rms,
            n_boot=1000,
            seed=bootstrap_seed,
        )
        gate1_ci_high = boot.ci_high
    else:
        gate1_ci_high = None

    level = _grade_level(result, kf27["se_target"])

    def _q90(arr: list[float]) -> float:
        return float(np.quantile(arr, 0.90)) if arr else float("nan")

    return CandidateReport(
        slug=slug,
        hypothesis=hypothesis,
        kf27_k_s=kf27["k_s"],
        kf27_k_t=kf27["k_t"],
        kf27_tau=kf27["tau"],
        kf27_x_star=kf27["x_star"],
        kf27_n_year=kf27["n_year"],
        kf27_sharpe_year=kf27["sharpe_year"],
        x_min=kf27["x_min"],
        se_target_value=kf27["se_target"],
        n_bars_eval=n,
        n_clusters=n_clusters,
        x_hat_mean=float(np.mean(x_hat)),
        x_hat_std=float(np.std(x_hat, ddof=1)),
        x_hat_q90=_q90(x_hat),
        x_truth_mean=float(np.mean(x_truth)),
        x_truth_std=float(np.std(x_truth, ddof=1)),
        x_truth_q90=_q90(x_truth),
        accepted=result.accepted,
        reject_reason=result.reject_reason,
        level=level,
        gate1_se_hat=result.gate1.se_hat,
        gate1_passed=result.gate1.passed,
        gate1_ci_high=gate1_ci_high,
        gate1_5_passed=result.gate1_5.passed if result.gate1_5 else None,
        gate1_5_reasons=list(result.gate1_5.reasons) if result.gate1_5 else [],
        gate1_5_remedy=result.gate1_5.remedy_hint if result.gate1_5 else None,
        gate2_ratio=result.gate2.ratio,
        gate2_passed=result.gate2.passed,
        gate3_r_hat=result.gate3.r_hat,
        gate3_passed=result.gate3.passed,
    )


def dump_report(report: CandidateReport, out_dir: Path) -> Path:
    """把 CandidateReport 序列化为 JSON。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{report.slug}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    return out


def format_report_md(report: CandidateReport) -> str:
    """把 CandidateReport 格式化为 markdown 表格 · 用于候选卡追加。"""
    lines = [
        "### 参数绑定（KF-27 反解）",
        "",
        "| 参数 | 值 |",
        "|---|---|",
        f"| K_S* | {report.kf27_k_s:.3f} |",
        f"| K_T* | {report.kf27_k_t:.3f} |",
        f"| τ* | {report.kf27_tau:.3f} |",
        f"| x* | {report.kf27_x_star:.4f} |",
        f"| N_year* | {report.kf27_n_year:.1f} |",
        f"| Sharpe/年 | {report.kf27_sharpe_year:.3f} |",
        f"| x_min | {report.x_min:.4f} |",
        f"| **se_target** | **{report.se_target_value:.4f}** |",
        "",
        "### 分布对齐概览",
        "",
        "| 统计量 | x_hat | x_truth |",
        "|---|---|---|",
        f"| mean | {report.x_hat_mean:.4f} | {report.x_truth_mean:.4f} |",
        f"| std | {report.x_hat_std:.4f} | {report.x_truth_std:.4f} |",
        f"| Q_90 | {report.x_hat_q90:.4f} | {report.x_truth_q90:.4f} |",
        f"| 样本数 | {report.n_bars_eval} · {report.n_clusters} 合约 |",
        "",
        "### Gate 判决",
        "",
        "| Gate | 数值 | 阈值 | 通过 |",
        "|---|---|---|---|",
        f"| **Gate 1** SE | {report.gate1_se_hat:.4f}"
        f"{'（CI_high=' + f'{report.gate1_ci_high:.4f}' + '）' if report.gate1_ci_high else ''} "
        f"| ≤ {report.se_target_value:.4f} | {'✅' if report.gate1_passed else '❌'} |",
        f"| **Gate 1.5** 分布 | passed={report.gate1_5_passed} |"
        f" C1-C4 | {'✅' if report.gate1_5_passed else '❌'} |",
        f"| **Gate 2** 覆盖 | ratio={report.gate2_ratio:.3f} | ≥ 0.70 | "
        f"{'✅' if report.gate2_passed else '❌'} |",
        f"| **Gate 3** r | {report.gate3_r_hat:.3f} | ≥ 0.40 | "
        f"{'✅' if report.gate3_passed else '❌'} |",
        "",
    ]
    if report.gate1_5_reasons:
        lines.append(f"**Gate 1.5 失败项**：{'; '.join(report.gate1_5_reasons)}")
        lines.append("")
    if report.gate1_5_remedy:
        lines.append(f"**Gate 1.5 修正提示**：`{report.gate1_5_remedy}`")
        lines.append("")
    lines.extend(
        [
            "### 终审 · §7 分级判决",
            "",
            f"- **accepted**：`{report.accepted}`",
            f"- **reject_reason**：`{report.reject_reason}`",
            f"- **level**：**{report.level}**",
        ]
    )
    return "\n".join(lines)


def summary_row(report: CandidateReport) -> dict[str, Any]:
    """一行汇总（供 rejected_factors / research-status 汇总用）。"""
    return {
        "slug": report.slug,
        "level": report.level,
        "se_hat": round(report.gate1_se_hat, 4),
        "se_ratio": round(report.gate1_se_hat / report.se_target_value, 3),
        "gate2_ratio": round(report.gate2_ratio, 3),
        "gate3_r": round(report.gate3_r_hat, 3),
        "reject_reason": report.reject_reason,
    }
