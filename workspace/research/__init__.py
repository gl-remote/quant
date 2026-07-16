"""
research — 稳定下来的研究工具业务域

文件级元信息：
- 创建背景：docs/research/themes/structural-shaping-alpha 与 strength-factor-screening
  两个主题产出的一整套数学工具（FPT / Fourier / 通道 B 混合期望 / KF-27 参数优化器 /
  cluster bootstrap / 截断法 / Hurst）已经在多个 raw-scripts 里被重复实现。
  抽出稳定接口沉淀在此业务域，供后续策略研究、因子筛选、参数优化直接调用。
- 用途：研究工具的长期库。零 I/O、零副作用、只做数学计算与统计验证。
- 注意事项：本域不承载"策略行为"（那是 workspace/strategies/ 的活）。
  任何进入本域的函数必须：(1) 有 docstring 说明公式与出处；(2) 有单元测试；
  (3) 无实验性质代码——那些应留在 docs/workbench/ 或 raw-scripts/。
  与 workspace/common/ 的边界：common 是全项目通用纯函数（成本、绩效、格式化），
  research 是研究方法专用（首达定理、混合期望、bootstrap 统计检验）。

子模块:
  - fpt:         首达定理（First Passage Theorem）· P_win / E[τ] / T*
  - fourier:     Fourier 有限时间精确解 · P_win(T) / P(τ>T)
  - channel_b:   通道 B 混合期望 · x_min / KF-26 闭式公式
  - distribution: |ν|/σ 分布对象（FoldedNormal + 分位数反函数）
  - optimizer:   KF-27 参数优化器 · (K_S*, K_T*, τ*) 反解
  - screening:   三层 gate 筛选流程 · se / coverage / rank corr
  - bootstrap:   Cluster bootstrap（事件非独立性处理）
  - hurst:       Hurst 指数 R/S 分析
  - causality:   截断法泄漏检测

出处：
  - shaping-theory §1.3.1 · §1.5 · §2.13.2 · §2.22.2 · §2.23（KF-17/KF-26/KF-27）
  - screening-methodology §一 证明块 · §二 数学工具箱
"""

from research.bootstrap import cluster_bootstrap
from research.causality import verify_causality_by_truncation
from research.channel_b import e_gross_mix, e_gross_mix_smallx, x_min_smallx
from research.derived import (
    KTFeasibleRange,
    MuSensitivity,
    e_gross_at_mu,
    k_t_feasible_range,
    kelly_position,
    mu_sensitivity,
    t_dagger_empirical,
)
from research.distribution import FoldedNormal
from research.driftlab import DriftDetection, dual_channel_drift_test
from research.fourier import p_tau_gt_T_fourier, p_win_finiteT_fourier
from research.fpt import e_gross_infty, e_net_infty, e_tau_infty, p_win_infty, t_star
from research.hurst import hurst_rs
from research.optimizer import KF27Params, KF27Result, optimize_kf27
from research.screening import (
    Gate1_5Result,
    Gate1Result,
    Gate2Result,
    Gate3Result,
    ScreeningResult,
    gate1_5_distribution_alignment,
    gate1_se_precision,
    gate2_coverage,
    gate3_rank_correlation,
    run_screening,
    se_target,
)

__all__ = [
    # FPT
    "p_win_infty",
    "e_gross_infty",
    "e_net_infty",
    "e_tau_infty",
    "t_star",
    # Fourier
    "p_win_finiteT_fourier",
    "p_tau_gt_T_fourier",
    # Channel B
    "e_gross_mix",
    "e_gross_mix_smallx",
    "x_min_smallx",
    # Distribution
    "FoldedNormal",
    # KF-27 Optimizer
    "KF27Params",
    "KF27Result",
    "optimize_kf27",
    # Screening
    "se_target",
    "gate1_se_precision",
    "gate1_5_distribution_alignment",
    "gate2_coverage",
    "gate3_rank_correlation",
    "run_screening",
    "Gate1Result",
    "Gate1_5Result",
    "Gate2Result",
    "Gate3Result",
    "ScreeningResult",
    # Validation
    "cluster_bootstrap",
    "hurst_rs",
    "verify_causality_by_truncation",
    # Drift diagnostics
    "dual_channel_drift_test",
    "DriftDetection",
    # Derived tools
    "mu_sensitivity",
    "MuSensitivity",
    "k_t_feasible_range",
    "KTFeasibleRange",
    "kelly_position",
    "t_dagger_empirical",
    "e_gross_at_mu",
]
