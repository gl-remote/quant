"""
文件级元信息：
- 创建背景：poc-value-area-asymmetry 阶段 4 · 需要一个独立、可复用的分类器组件·
  把 signed_skew_rank / atr_rank / trend_rank / transition_flag 映射到 144 个互斥
  tier · 供下游策略 (含 vnpy 集成) 引用。
- 用途：实现 classifier-math-spec.md v3.1 的中间标签与 tier 结构·包含 dataclass
  配置、单事件分类 API 与批量 evaluate_dataset 接口。
- 注意事项：本模块零 I/O、零框架依赖 (无 vnpy)；A3_skew / 原始 rank 由上游脚本
  预先算好并作为 DataFrame / 参数传入·本文件只负责 rank → label → tier 的确定性
  映射。若数学契约或参数版本改动·spec / parameter-selection-spec 必须先升版。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

# ---------------------------------------------------------------------------
# 常量：tier ID 命名映射 (spec §7.2)
# ---------------------------------------------------------------------------

# skew_label -> tier ID 前缀 (DN_1 -> DN1, UP_4 -> UP4, ...)
_SKEW_TIER_SEGMENT: Final[dict[str, str]] = {
    "DN_1": "DN1",
    "DN_2": "DN2",
    "DN_3": "DN3",
    "DN_4": "DN4",
    "UP_1": "UP1",
    "UP_2": "UP2",
    "UP_3": "UP3",
    "UP_4": "UP4",
}

_ATR_TIER_SEGMENT: Final[dict[str, str]] = {
    "low": "atrLow",
    "mid": "atrMid",
    "high": "atrHigh",
}

# trend_regime label 与 tier ID 中的 trend 段一致 (down / flat / up)
_TREND_TIER_SEGMENT: Final[dict[str, str]] = {
    "down": "down",
    "flat": "flat",
    "up": "up",
}


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ClassifierConfig:
    """POC-VA 分类器参数配置 · 阶段 4 · v3.1 冻结值."""

    # bar 周期 (元数据 · 组件不消费 · 供上游报告标注)
    bar_profile: str = "5m"
    bar_trade: str = "1h"
    bar_daily: str = "1d"

    # rolling 窗口
    n_rolling_events: int = 100
    n_rolling_days: int = 20
    n_atr_lookback: int = 10
    n_trend_lookback: int = 10
    n_warmup_days: int = 20
    n_transition_window_days: int = 3

    # skew 分档 (阶段 4 · 9 段：4 段 DN + NEUTRAL + 4 段 UP)
    skew_thresholds: tuple[float, ...] = (0.09, 0.19, 0.25, 0.30, 0.70, 0.75, 0.81, 0.91)

    # atr 分档 (3-way · 用于 atr_regime 和 atr_bucket_session)
    atr_thresholds_regime: tuple[float, float] = (0.33, 0.67)

    # trend 分档 (阶段 4 新增 flat 档 · 3-way)
    trend_thresholds_regime: tuple[float, float] = (0.20, 0.75)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ClassifierOutput:
    """单事件分类结果 · 结构对齐 spec §9.1."""

    # 元数据
    contract: str
    event_time: datetime
    event_hour: int
    trading_date: date

    # 原始数值
    A3_skew: float | None
    signed_skew_rank: float | None
    daily_atr_10_bps: float | None
    atr_rank: float | None
    trend_ret_10d: float | None
    trend_rank: float | None

    # 中间标签
    skew_label: str | None
    atr_regime: str | None
    trend_regime: str | None
    transition_flag: bool | None

    # 分类结果
    tier: str | None

    # Warmup 状态
    warmup_ok: bool
    event_count_at_entry: int = 0


# ---------------------------------------------------------------------------
# 分类器主体
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class POCVAClassifier:
    """POC-VA 分类器 · 实现 classifier-math-spec.md v3.1."""

    config: ClassifierConfig = field(default_factory=ClassifierConfig)

    # ---------- 中间标签辅助 ----------

    def _skew_label(self, rank: float) -> str | None:
        """阶段 4 · 9 档 skew 分类 (spec §6.1 + task spec)."""
        if rank is None or not np.isfinite(rank):
            return None
        t = self.config.skew_thresholds
        # (0.09, 0.19, 0.25, 0.30, 0.70, 0.75, 0.81, 0.91)
        if rank <= t[0]:
            return "DN_1"
        if rank <= t[1]:
            return "DN_2"
        if rank <= t[2]:
            return "DN_3"
        if rank <= t[3]:
            return "DN_4"
        if rank < t[4]:
            return "NEUTRAL"
        if rank < t[5]:
            return "UP_4"
        if rank < t[6]:
            return "UP_3"
        if rank < t[7]:
            return "UP_2"
        return "UP_1"

    def _atr_regime(self, rank: float) -> str | None:
        if rank is None or not np.isfinite(rank):
            return None
        lo, hi = self.config.atr_thresholds_regime
        if rank <= lo:
            return "low"
        if rank < hi:
            return "mid"
        return "high"

    def _trend_regime(self, rank: float) -> str | None:
        if rank is None or not np.isfinite(rank):
            return None
        lo, hi = self.config.trend_thresholds_regime
        if rank <= lo:
            return "down"
        if rank < hi:
            return "flat"
        return "up"

    def _tier_id(
        self,
        skew_label: str | None,
        atr_regime: str | None,
        trend_regime: str | None,
        transition_flag: bool | None,
    ) -> str | None:
        """按 spec §7.2 生成 tier ID · NEUTRAL / warmup 未过 / 缺任一标签 -> None."""
        if skew_label is None or skew_label == "NEUTRAL":
            return None
        if atr_regime is None or trend_regime is None or transition_flag is None:
            return None
        direction = _SKEW_TIER_SEGMENT.get(skew_label)
        atr_seg = _ATR_TIER_SEGMENT.get(atr_regime)
        trend_seg = _TREND_TIER_SEGMENT.get(trend_regime)
        if direction is None or atr_seg is None or trend_seg is None:
            return None
        regime_seg = "trans" if transition_flag else "stable"
        return f"{direction}_{atr_seg}_{trend_seg}_{regime_seg}"

    # ---------- 单事件 API ----------

    def classify_event(
        self,
        contract: str,
        event_time: datetime,
        signed_skew_rank: float,
        atr_rank: float,
        trend_rank: float,
        transition_flag: bool,
        A3_skew: float | None = None,  # noqa: N803  -- 契约字段名·spec §9.1
        daily_atr_10_bps: float | None = None,
        trend_ret_10d: float | None = None,
        event_count_at_entry: int = 0,
        warmup_ok: bool = True,
    ) -> ClassifierOutput:
        """单事件分类 · 供 vnpy 或其他策略框架调用."""
        trading_date = event_time.date()
        event_hour = event_time.hour

        if not warmup_ok:
            return ClassifierOutput(
                contract=contract,
                event_time=event_time,
                event_hour=event_hour,
                trading_date=trading_date,
                A3_skew=A3_skew,
                signed_skew_rank=signed_skew_rank,
                daily_atr_10_bps=daily_atr_10_bps,
                atr_rank=atr_rank,
                trend_ret_10d=trend_ret_10d,
                trend_rank=trend_rank,
                skew_label=None,
                atr_regime=None,
                trend_regime=None,
                transition_flag=None,
                tier=None,
                warmup_ok=False,
                event_count_at_entry=event_count_at_entry,
            )

        skew_label = self._skew_label(signed_skew_rank)
        atr_regime = self._atr_regime(atr_rank)
        trend_regime = self._trend_regime(trend_rank)
        tier = self._tier_id(skew_label, atr_regime, trend_regime, transition_flag)

        return ClassifierOutput(
            contract=contract,
            event_time=event_time,
            event_hour=event_hour,
            trading_date=trading_date,
            A3_skew=A3_skew,
            signed_skew_rank=signed_skew_rank,
            daily_atr_10_bps=daily_atr_10_bps,
            atr_rank=atr_rank,
            trend_ret_10d=trend_ret_10d,
            trend_rank=trend_rank,
            skew_label=skew_label,
            atr_regime=atr_regime,
            trend_regime=trend_regime,
            transition_flag=bool(transition_flag),
            tier=tier,
            warmup_ok=True,
            event_count_at_entry=event_count_at_entry,
        )

    # ---------- 批量 API ----------

    def evaluate_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        批量分类 stage4 dataset_full.parquet 风格 DataFrame.

        输入必需列:
          - contract, event_time
          - signed_skew_rank_roll, atr_rank_roll, trend_rank_roll
          - transition_flag（可省略：缺省时用 poc §6.4 算法从 atr_rank_roll 派生，
            需能由 date 或 event_time 推出交易日）

        可选列 (若存在则保留并透传):
          - A3_skew, daily_atr_10_bps, trend_ret_10d
          - ret_8h_bps, short_pnl_4h_bps

        输出：在输入基础上追加 skew_label / atr_regime / trend_regime / tier /
        event_hour / trading_date 等列的 DataFrame (不修改原始 df)。
        """
        required = [
            "contract",
            "event_time",
            "signed_skew_rank_roll",
            "atr_rank_roll",
            "trend_rank_roll",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"evaluate_dataset 缺少必需列: {missing}")

        out = df.copy()
        # transition_flag：优先用传入列；缺失则用 poc §6.4 从 atr_rank_roll 派生（去魔列依赖）
        if "transition_flag" not in out.columns:
            tmp = out.copy()
            if "date" not in tmp.columns:
                if "event_time" not in tmp.columns:
                    raise ValueError("evaluate_dataset 缺 transition_flag，且无 date/event_time 可派生 §6.4 转期标记")
                tmp["date"] = pd.to_datetime(tmp["event_time"]).dt.date
            out["transition_flag"] = (
                compute_transition_flag(
                    tmp,
                    atr_col="atr_rank_roll",
                    contract_col="contract",
                    date_col="date",
                    n_window=self.config.n_transition_window_days,
                )
                .reindex(out.index)
                .values
            )
        out["event_time"] = pd.to_datetime(out["event_time"])
        out["event_hour"] = out["event_time"].dt.hour.astype("int64")
        out["trading_date"] = out["event_time"].dt.date

        skew_rank = out["signed_skew_rank_roll"].to_numpy(dtype=float)
        atr_rank = out["atr_rank_roll"].to_numpy(dtype=float)
        trend_rank = out["trend_rank_roll"].to_numpy(dtype=float)

        out["skew_label"] = _vectorized_skew_label(skew_rank, self.config.skew_thresholds)
        out["atr_regime"] = _vectorized_atr_regime(atr_rank, self.config.atr_thresholds_regime)
        out["trend_regime"] = _vectorized_trend_regime(trend_rank, self.config.trend_thresholds_regime)

        # transition_flag 强制转 bool (允许 numpy bool_)
        trans_series = out["transition_flag"].astype(bool)
        regime_seg = np.where(trans_series.to_numpy(), "trans", "stable")

        out["tier"] = _build_tier_ids(
            out["skew_label"].to_numpy(),
            out["atr_regime"].to_numpy(),
            out["trend_regime"].to_numpy(),
            regime_seg,
        )

        return out


# ---------------------------------------------------------------------------
# 向量化辅助 (仅内部使用 · 保持与单值方法完全一致)
# ---------------------------------------------------------------------------


def _vectorized_skew_label(rank: np.ndarray, thresholds: tuple[float, ...]) -> np.ndarray:
    """9 档 skew · 与 POCVAClassifier._skew_label 数学等价."""
    t = thresholds
    out = np.full(rank.shape, None, dtype=object)
    valid = np.isfinite(rank)
    r = rank

    out[valid & (r <= t[0])] = "DN_1"
    out[valid & (r > t[0]) & (r <= t[1])] = "DN_2"
    out[valid & (r > t[1]) & (r <= t[2])] = "DN_3"
    out[valid & (r > t[2]) & (r <= t[3])] = "DN_4"
    out[valid & (r > t[3]) & (r < t[4])] = "NEUTRAL"
    out[valid & (r >= t[4]) & (r < t[5])] = "UP_4"
    out[valid & (r >= t[5]) & (r < t[6])] = "UP_3"
    out[valid & (r >= t[6]) & (r < t[7])] = "UP_2"
    out[valid & (r >= t[7])] = "UP_1"
    return out


def _vectorized_atr_regime(rank: np.ndarray, thresholds: tuple[float, float]) -> np.ndarray:
    lo, hi = thresholds
    out = np.full(rank.shape, None, dtype=object)
    valid = np.isfinite(rank)
    out[valid & (rank <= lo)] = "low"
    out[valid & (rank > lo) & (rank < hi)] = "mid"
    out[valid & (rank >= hi)] = "high"
    return out


def _vectorized_trend_regime(rank: np.ndarray, thresholds: tuple[float, float]) -> np.ndarray:
    lo, hi = thresholds
    out = np.full(rank.shape, None, dtype=object)
    valid = np.isfinite(rank)
    out[valid & (rank <= lo)] = "down"
    out[valid & (rank > lo) & (rank < hi)] = "flat"
    out[valid & (rank >= hi)] = "up"
    return out


def _build_tier_ids(
    skew_labels: np.ndarray,
    atr_regimes: np.ndarray,
    trend_regimes: np.ndarray,
    regime_seg: np.ndarray,
) -> np.ndarray:
    """按 spec §7.2 构造 144 tier ID · NEUTRAL / 任一 None -> None."""
    out = np.full(skew_labels.shape, None, dtype=object)
    for i in range(len(skew_labels)):
        sk = skew_labels[i]
        atr = atr_regimes[i]
        tr = trend_regimes[i]
        if sk is None or sk == "NEUTRAL":
            continue
        if atr is None or tr is None:
            continue
        direction = _SKEW_TIER_SEGMENT.get(sk)
        atr_seg = _ATR_TIER_SEGMENT.get(atr)
        trend_seg = _TREND_TIER_SEGMENT.get(tr)
        if direction is None or atr_seg is None or trend_seg is None:
            continue
        out[i] = f"{direction}_{atr_seg}_{trend_seg}_{regime_seg[i]}"
    return out


__all__ = [
    "ClassifierConfig",
    "ClassifierOutput",
    "POCVAClassifier",
    "T_PIT_DF",
    "t_pit_window",
    "roll_t_pit",
    "V40_BOUNDS",
    "classify_v40",
    "evaluate_v40",
]


# ---------------------------------------------------------------------------
# spec v4.0 六阵营判定 + norm=B(t-PIT) 归一化
# ---------------------------------------------------------------------------

T_PIT_DF = 12  # spec §1.2: 学生 t 自由度 ν=12


def t_pit_window(w: np.ndarray) -> float:
    """窗口内稳健 z-score → 学生 t CDF(ν=12) → 0~1。

    仅用窗口内观测（含末端当前点）的 median / MAD 作 loc/scale，
    属因果变换、无未来泄漏。scale≈0（常数窗口）时返回 0.5（中性）。
    """
    x = w[-1]
    med = np.median(w)
    mad = np.median(np.abs(w - med))
    scale = 1.4826 * mad
    if scale < 1e-12:
        return 0.5
    z = (x - med) / scale
    return float(t_dist.cdf(z, df=T_PIT_DF))


def roll_t_pit(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    """逐合约因果滚动 t-PIT（单一变量隔离归一化方式）。"""
    return series.rolling(window, min_periods=min_periods).apply(t_pit_window, raw=True)


def _in(x: float, lo: float, hi: float, loinc: bool, hiinc: bool) -> bool:
    if loinc and x < lo:
        return False
    if (not loinc) and x <= lo:
        return False
    if hiinc and x > hi:
        return False
    return not (not hiinc and x >= hi)


# spec §1.3 六阵营边界（与 strategy-math-spec.md §1.3 完全一致）。
# 每项为 (skew 段, atr 段, trend 段)，段 = (lo, hi, loinc, hiinc)。
# 输入坐标须为 spec 坐标：r_s∈(0,1] 高=极端跌=short，r_a/r_t 高=高波动/强趋势。
V40_BOUNDS: Final[dict[str, tuple]] = {
    "L_seg3_lowmid_up": ((0.09, 0.30, False, True), (0.00, 0.67, True, True), (0.75, 1.00, True, True)),
    "L_seg12_high_up": ((0.00, 0.19, True, True), (0.67, 1.00, False, True), (0.75, 1.00, True, True)),
    "L_seg2_low_flat": ((0.09, 0.19, False, True), (0.00, 0.33, True, True), (0.20, 0.75, False, False)),
    "S_seg12_high_dn": ((0.81, 1.00, True, True), (0.67, 1.00, False, True), (0.00, 0.20, True, True)),
    "S_seg34_high_dn": ((0.60, 0.81, True, True), (0.67, 1.00, False, True), (0.00, 0.20, True, True)),
    "S_seg2_mid_dn": ((0.81, 0.91, False, True), (0.33, 0.67, False, True), (0.00, 0.20, True, True)),
}


# ---------------------------------------------------------------------------
# transition_flag · poc §6.4 权威定义（生产 B0 采用的转期标记）
# ---------------------------------------------------------------------------
# 算法（与 scripts/ai_tmp/transition_flag_impact.py 完全一致，引用 poc §6.4）：
#   1. 每个 (contract, session=date) 取 atr_rank_roll 当日均值
#   2. ATR 桶：≤0.33→0(low) / (0.33,0.67)→1(mid) / ≥0.67→2(high)
#   3. crossover = 当日桶 ≠ 前一日桶
#   4. transition_flag = crossover 当天 + 其后 n_window(=3) 个 session 全标 1
# 该算法在冻结数据集上产出 ≈46–49% 转期覆盖（= 生产 transition_flag 列的权威口径）。
# 注意：本 §6.4 窗口即 spec §1.4 τ_signed（W=3 衰减）的二值化版本 —— 二者同一 crossover
# 检测、同一窗口（age<W=3 ⇔ crossover 后 3 天 ⇔ flag[ci:ci+3]），全样本一致率 100%。
# 所谓"spec W=3 重算仅 21.2%"是 va_p05_tau_signed.py 的实现 bug（sign 仅在 crossover 当天
# 赋值、未向 decay 日传递），并非 spec 公式缺陷。compute_transition_flag 即为 spec §1.4 的
# 生产级实现，可放心作为权威转期标记。


def _atr_bucket_poc64(x: float) -> int:
    if x <= 0.33:
        return 0
    if x >= 0.67:
        return 2
    return 1


def compute_transition_flag(
    df: pd.DataFrame,
    atr_col: str = "atr_rank_roll",
    contract_col: str = "contract",
    date_col: str = "date",
    n_window: int = 3,
) -> pd.Series:
    """poc §6.4 权威 transition_flag（生产 B0 口径，≈44.6% 覆盖）。

    从 atr_rank_roll 完全派生，无需预计算列。返回与 df 同 index 的 bool Series。
    同日多 bar 取 atr_rank_roll 均值再分桶（session 级近似）；crossover 当天及
    其后 n_window 个 session 标 1。
    """
    sess = (
        df.dropna(subset=[atr_col])
        .groupby([contract_col, date_col])[atr_col]
        .mean()
        .reset_index()
        .sort_values([contract_col, date_col])
    )
    sess["_bkt"] = sess[atr_col].apply(_atr_bucket_poc64)
    sess["_prev"] = sess.groupby(contract_col)["_bkt"].shift(1)
    sess["_cross"] = sess["_prev"].notna() & (sess["_bkt"] != sess["_prev"])
    parts = []
    for _, g in sess.groupby(contract_col):
        g = g.sort_values(date_col).reset_index(drop=True)
        cross_idx = np.where(g["_cross"].to_numpy())[0]
        flag = np.zeros(len(g), dtype=int)
        for ci in cross_idx:
            flag[ci : ci + n_window] = 1  # crossover 影响 [ci, ci+n_window-1]
        g = g.copy()
        g["transition_flag"] = flag.astype(bool)
        parts.append(g[[contract_col, date_col, "transition_flag"]])
    out = pd.concat(parts, ignore_index=True)
    return df.merge(out, on=[contract_col, date_col], how="left")["transition_flag"]


def compute_tau_signed(
    df: pd.DataFrame,
    atr_col: str = "atr_rank_roll",
    contract_col: str = "contract",
    date_col: str = "date",
    w_window: int = 3,
) -> pd.Series:
    """spec §1.4 带符号转期强度 τ_signed（transition_flag 的方向+衰减版）。

    与 ``compute_transition_flag`` 同一 crossover 检测、同一窗口（``age<W`` ⇔
    crossover 后 W 天），全样本 ``|τ|≠0`` 与 ``transition_flag=True`` 逐日一致；
    差别仅在本函数携带方向符号与线性衰减权重：

        τ_signed = sign(Δbucket) · max(0, 1 − age/W)

    其中 ``sign`` 为最近一次 crossover 的桶变化方向（+1 波动扩张 low→high，
    −1 波动收缩 high→low），``age`` 为距该 crossover 的 session 数，会向 decay
    日（age=1,2）正确传递（这正是 va_p05_tau_signed.py 漏掉、导致误报 21.2% 的点）。

    用途：S 阵营"转期内仅取扩张 τ>0、弃收缩 τ<0"的细分（spec §1.4 表格），
    生产二值 transition_flag 无法表达，须用本函数。返回与 df 同 index 的 float Series。
    """
    sess = (
        df.dropna(subset=[atr_col])
        .groupby([contract_col, date_col])[atr_col]
        .mean()
        .reset_index()
        .sort_values([contract_col, date_col])
    )
    sess["_bkt"] = sess[atr_col].apply(_atr_bucket_poc64)
    parts = []
    for _, g in sess.groupby(contract_col):
        g = g.sort_values(date_col).reset_index(drop=True)
        bkt = g["_bkt"].to_numpy()
        prev = np.concatenate([[np.nan], bkt[:-1].astype(float)])
        tau = np.zeros(len(bkt))
        last = -(10**9)
        last_sign = 0.0
        for i in range(len(bkt)):
            if i >= 1 and not np.isnan(prev[i]) and bkt[i] != prev[i]:
                last = i
                last_sign = float(np.sign(bkt[i] - prev[i]))  # crossover 方向
            age = i - last
            if last >= 0 and age < w_window:
                tau[i] = last_sign * (1.0 - age / w_window)  # sign 向 decay 日传递
        g = g.copy()
        g["tau_signed"] = tau
        parts.append(g[[contract_col, date_col, "tau_signed"]])
    out = pd.concat(parts, ignore_index=True)
    return df.merge(out, on=[contract_col, date_col], how="left")["tau_signed"]


# τ_signed 未提供的哨兵：classify_v40 据此退回 full 口径（不细分扩张/收缩）
_TAU_SIGN_UNSET: Final[float] = float("nan")


def classify_v40(
    r_s: float,
    r_a: float,
    r_t: float,
    transition_flag: bool,
    tau_signed: float = _TAU_SIGN_UNSET,
) -> str | None:
    """spec §1.3 六阵营判定 + §1.4 transition 过滤（输入为 spec 坐标 r_s/r_a/r_t）。

    坐标取向：调用方负责把生产列喂成 spec 坐标——尤其 skew 须互补
    ``r_s = 1 - signed_skew_rank_roll``（生产列高=涨=long，spec r_s 高=跌=short）；
    atr/trend 两列语义直接对齐，无需互补。

    transition 过滤（spec §1.4，T1，权威口径 = ``transition_flag`` + ``τ_signed``）：

    =============  ============================  ================================
    阵营            适用范围（spec §1.4 表格）
    -------------  ----------------------------  --------------------------------
    L_seg3         全期（stable ∪ trans）        恒参与
    L_seg12        仅转期                         transition_flag=True
    L_seg2         仅转期                         transition_flag=True
    S_seg12        稳定期优先；转期仅扩张          ¬flag → 参与；flag∧τ>0 → 参与；
    S_seg34        稳定期优先；转期仅扩张          flag∧τ<0 → 弃（收缩）
    S_seg2         仅转期                         transition_flag=True
    =============  ============================  ================================

    ``tau_signed`` 为 spec §1.4 带符号转期强度（``compute_tau_signed`` 产出）。
    若未提供（``nan``，即调用方未算符号），S_seg12/S_seg34 在转期内退回 full 口径
    参与（不细分扩张/收缩）——避免无符号信息时误弃；严格 spec 须由 ``evaluate_v40``
    传入 ``tau_signed``。
    """
    if not (np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t)):
        return None
    for name, (s, a, t) in V40_BOUNDS.items():
        if _in(r_s, *s) and _in(r_a, *a) and _in(r_t, *t):
            if name == "L_seg3_lowmid_up":
                return name  # 全期参与
            if name in ("S_seg12_high_dn", "S_seg34_high_dn"):
                # 稳定期优先：非转期即参与
                if not transition_flag:
                    return name
                # 转期内仅扩张（τ>0）；收缩（τ<0）弃
                if np.isnan(tau_signed):
                    return name  # 无符号信息 → 退回 full（严格路径不应触发）
                return name if tau_signed > 0 else None
            # L_seg12 / L_seg2 / S_seg2：仅转期参与
            return name if transition_flag else None
    return None


def evaluate_v40(
    df: pd.DataFrame,
    norm: str = "A",
    skew_win: int = 100,
    skew_minp: int = 10,
    nu: int = T_PIT_DF,
    use_tau_sign: bool = True,
) -> pd.Series:
    """批量 spec v4.0 六阵营判定 + §1.4 transition 过滤（解除 P3 借壳，正式落地生产）。

    参数
    ----
    df : 须含 ``signed_skew_rank_roll`` / ``atr_rank_roll`` / ``trend_rank_roll``；
         ``norm="B"`` 还需 ``A3_skew`` 列。transition 标记（``transition_flag`` /
         ``τ_signed``）**内部由 ``atr_rank_roll`` 直接派生**（spec §1.4 权威口径），
         不依赖外部预计算列。
    norm : ``"A"`` 滚动 rank（生产列直接作为坐标，skew 做互补）；
           ``"B"`` t-PIT 对齐版——仅 skew 经稳健 z + t CDF(ν) 重归一化（atr/trend 冻结为 A 轨 rank）。
    skew_win / skew_minp : B 轨 t-PIT 滚动窗口 / 最小观测（对齐冻结管线事件行口径）。
    use_tau_sign : ``True``（默认，严格 spec）对 S_seg12/S_seg34 启用转期扩张/收缩
         细分（``τ_signed>0`` 才在转期参与、``τ<0`` 弃）；``False`` 让 S 阵营退回
         full 口径（stable/trans 均参与），用于与旧口径对照。

    返回
    ----
    pd.Series（index=df.index），元素为 6 阵营名或 None。
    """
    global T_PIT_DF
    T_PIT_DF = nu

    skew_raw = df["signed_skew_rank_roll"].astype(float)
    if norm == "B":
        if "A3_skew" not in df.columns:
            raise ValueError("norm='B' 需要 A3_skew 列以构建 t-PIT 坐标")
        sk = df.groupby("contract")["A3_skew"].transform(lambda s: roll_t_pit(s, skew_win, skew_minp))
    else:
        sk = skew_raw

    r_s = 1.0 - sk.to_numpy(dtype=float)  # 互补：生产列高=long → spec r_s 高=short
    r_a = df["atr_rank_roll"].astype(float).to_numpy(dtype=float)
    r_t = df["trend_rank_roll"].astype(float).to_numpy(dtype=float)

    # spec §1.4 transition（T1，权威）：从 atr_rank_roll 直接派生
    flag = (
        compute_transition_flag(df, atr_col="atr_rank_roll", contract_col="contract", date_col="date", n_window=3)
        .fillna(False)
        .to_numpy(dtype=bool)
    )
    if use_tau_sign:
        tau = (
            compute_tau_signed(df, atr_col="atr_rank_roll", contract_col="contract", date_col="date", w_window=3)
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
    else:
        tau = np.full(len(df), float("nan"))  # 不细分 → classify_v40 退回 full

    out = [
        classify_v40(float(rs), float(ra), float(rt), fl, t)
        for rs, ra, rt, fl, t in zip(r_s, r_a, r_t, flag, tau, strict=True)
    ]
    return pd.Series(out, index=df.index, dtype=object)
