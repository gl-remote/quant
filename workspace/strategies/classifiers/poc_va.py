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
          - transition_flag

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
            "transition_flag",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"evaluate_dataset 缺少必需列: {missing}")

        out = df.copy()
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
]
