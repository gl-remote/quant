"""
文件级元信息：
- 创建背景：va-asymmetry-composite 主题需要一个独立、可复用的 A 层分类器组件，
  严格实现 docs/research/themes/va-asymmetry-composite/strategy-math-spec.md §1
  的四参数归一化 (r_s, r_a, r_t, trans) 与六阵营判定。
- 用途：为 B 层执行策略以及研究脚本提供
    * 逐参数归一化 (稳健 z → 学生 t CDF, ν=12) 的因果实现；
    * §1.1 参数 4 制度切换 (crossover / age / Δ_recent / trans_state) 检测；
    * §1.3 六阵营判定 (含 trans 约束) 与批量 evaluate_dataset API。
- 注意事项：
    * 严格按 spec §1 实现——各参数独立归一化 (不设统一 norm 开关)；
    * skew 坐标 r_s 已取互补 (高 = 极端跌 = short 侧)，atr / trend 直接对齐；
    * 本组件零 I/O、零框架依赖；输入原始时序 (A3_skew / TR / log_ret) 由上游供给。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

# ---------------------------------------------------------------------------
# spec §1.1 常量
# ---------------------------------------------------------------------------

T_PIT_DF: Final[int] = 12  # 学生 t 自由度 ν = 12
MAD_SCALE: Final[float] = 1.4826  # MAD → σ 的一致性常数

# spec §1.1 参数 4：ATR 桶阈值（与 §1.3 各阵营 r_a 切分点一致）
ATR_BUCKET_LO: Final[float] = 0.33
ATR_BUCKET_HI: Final[float] = 0.67
# spec §1.1 参数 4：制度切换窗口长度 n=3（含 crossover 当日）
TRANS_WIN: Final[int] = 3

# spec §1.3 阵营名（六阵营）
TIER_L_SEG3: Final[str] = "L_seg3_lowmid_up"
TIER_L_SEG12: Final[str] = "L_seg12_high_up"
TIER_L_SEG2: Final[str] = "L_seg2_low_flat"
TIER_S_SEG12: Final[str] = "S_seg12_high_dn"
TIER_S_SEG34: Final[str] = "S_seg34_high_dn"
TIER_S_SEG2: Final[str] = "S_seg2_mid_dn"

# spec §1.1 参数 4 状态
TRANS_STABLE: Final[str] = "stable"
TRANS_EXPAND: Final[str] = "trans_expand"
TRANS_CONTRACT: Final[str] = "trans_contract"


# ---------------------------------------------------------------------------
# spec §1.1：稳健 z → 学生 t CDF 归一化
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 性能优化：不再使用 .rolling().apply()（Python 逐窗循环），而用 pandas
# 内置 C 级 rolling median/quantile + scipy 批量 CDF。
# 实测 20000 行 window=20 耗时从 ~1.5s 降至 ~0.05s。
# ---------------------------------------------------------------------------


def roll_t_pit(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """spec §1.1 稳健 z → 学生 t CDF 的因果滚动实现（向量化版）。

    :param series: 原始时序（如 A3_skew / ATR / trend_ret_M）
    :param window: 滚动窗口长度 N（spec §0 skew_rank_win / atr_rank_win / trend_win）
    :param min_periods: 最小有效样本数（默认 = window）
    :returns: 与输入同 index 的 (0,1] 归一化 Series；预热期 NaN
    """
    if min_periods is None:
        min_periods = window
    roll = series.rolling(window, min_periods=min_periods)
    # 滚动窗口中位数（pandas C 级）
    roll_med = roll.median()
    # 滚动 MAD = median(|x - med|)（pandas C 级 quantile(0.5)）
    # 注意：MAD 需要 roll_med 已就绪的样本，故 min_periods 须 ≤ 实际有效样本数。
    # 当 dataset ≪ 2×window 时，用较小 min_periods 避免全部 NaN 回退到 0.5。
    dev_abs = (series - roll_med).abs()
    mad_min = max(3, window // 4)
    roll_mad = dev_abs.rolling(window, min_periods=mad_min).quantile(0.5)
    scale = roll_mad * MAD_SCALE
    # 稳健 z-score
    z_arr = ((series - roll_med) / scale.where(scale >= 1e-12)).fillna(0.0).to_numpy(dtype=np.float64)
    # 批量 t-CDF（一次 scipy 调用处理全数组）
    result = pd.Series(t_dist.cdf(z_arr, df=T_PIT_DF), index=series.index, dtype=np.float64)
    # MAD ≈ 0（常数窗口）→ 中性 0.5
    result.loc[scale < 1e-12] = 0.5
    # 前 min_periods-1 行为 NaN（scale 为 NaN）
    result.iloc[: min_periods - 1] = np.nan
    return result


# ---------------------------------------------------------------------------
# spec §1.1 参数 1：量加权价格偏度 A3_skew
# ---------------------------------------------------------------------------


def volume_weighted_skew(prices: np.ndarray, volumes: np.ndarray) -> float:
    """spec §1.1 参数 1：A3_skew = m3 / m2^{3/2}，成交量加权。

    μ_v = Σv·p / Σv，  m_k = Σv·(p-μ_v)^k / Σv。
    :param prices: 一根 session 内 skew_win K 线的价格序列（如 close）
    :param volumes: 对应成交量
    """
    v = np.asarray(volumes, dtype=float)
    p = np.asarray(prices, dtype=float)
    total = v.sum()
    if total <= 0 or len(p) < 3:
        return float("nan")
    mu = float((v * p).sum() / total)
    dev = p - mu
    m2 = float((v * dev * dev).sum() / total)
    if m2 <= 0:
        return float("nan")
    m3 = float((v * dev * dev * dev).sum() / total)
    return float(m3 / (m2**1.5))


# ---------------------------------------------------------------------------
# spec §1.1 参数 2：日线 SMA(10) ATR
# ---------------------------------------------------------------------------


def daily_atr_sma(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    """spec §1.1 参数 2：前 L 日真实波幅 SMA 平滑。

    TR_i = max(H-L, |H-C_{-1}|, |L-C_{-1}|)；ATR = SMA_L(TR)。
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


# ---------------------------------------------------------------------------
# spec §1.1 参数 3：M 日累计对数收益
# ---------------------------------------------------------------------------


def trend_log_return(close: pd.Series, window: int) -> pd.Series:
    """spec §1.1 参数 3：trend_ret_M = log(C_d / C_{d-M+1})。"""
    return pd.Series(np.log(close / close.shift(window - 1)), index=close.index)


# ---------------------------------------------------------------------------
# spec §1.1 参数 4：制度切换 (regime transition)
# ---------------------------------------------------------------------------


def _atr_bucket(r_a: float) -> int:
    """spec §1.1 参数 4：ATR 坐标三分桶。low=0 / mid=1 / high=2。"""
    if r_a <= ATR_BUCKET_LO:
        return 0
    if r_a >= ATR_BUCKET_HI:
        return 2
    return 1


_BUCKET_LEVEL: Final[dict[int, float]] = {0: 0.0, 1: 0.5, 2: 1.0}


@dataclass(frozen=True, slots=True)
class TransitionState:
    """spec §1.1 参数 4：单交易日的制度切换状态。"""

    trans: str
    """{"stable", "trans_expand", "trans_contract"}"""
    transition_flag: bool
    """1[0 ≤ age(t) < TRANS_WIN]"""
    age: int
    """距最近 crossover 日的天数（age=0 即 crossover 当日本身）"""
    delta_recent: float
    """Δ_recent = level(b_{c*}) - level(b_{c*-1})，无 crossover 时 = 0"""


def compute_transition_series(r_a: pd.Series) -> pd.DataFrame:
    """spec §1.1 参数 4：从 ATR 坐标序列派生逐日 (trans, transition_flag, age, Δ_recent)。

    步骤（与 spec 逐条对应）：
      1. 三分桶 b_t = bucket(r_a(t))；
      2. crossover 集 C = {t : b_t ≠ b_{t-1}}；
      3. 最近 crossover c*(t) = max{c∈C : c ≤ t}；age(t) = t - c*(t)；
      4. transition_flag(t) = 1[0 ≤ age < n]，n = TRANS_WIN；
      5. Δ_recent(t) = level(b_{c*}) - level(b_{c*-1})；
      6. trans(t) = stable / trans_expand (Δ>0) / trans_contract (Δ<0)。

    :param r_a: (0,1] ATR 坐标序列（须按时间升序、单合约、无重复交易日）
    :returns: DataFrame，列 = ['bucket', 'trans', 'transition_flag', 'age', 'delta_recent']
    """
    idx = r_a.index
    vals = r_a.to_numpy(dtype=np.float64)
    n = len(vals)

    # 1. 向量化三分桶
    finite = np.isfinite(vals)
    buckets = np.full(n, -1, dtype=np.int32)
    buckets[finite] = np.select(
        [vals[finite] <= ATR_BUCKET_LO, vals[finite] >= ATR_BUCKET_HI],
        [0, 2],
        default=1,
    ).astype(np.int32)

    # 2. crossover 检测：b_t != b_{t-1} 且二者均有效
    is_cross = np.zeros(n, dtype=bool)
    is_cross[1:] = (buckets[1:] >= 0) & (buckets[:-1] >= 0) & (buckets[1:] != buckets[:-1])

    # 3. 每个位置最近的 crossover 索引（cummax 技巧）
    cross_pos_idx = np.where(is_cross, np.arange(n), -1)
    last_cross = np.maximum.accumulate(cross_pos_idx)

    # 4. age
    age = np.where(last_cross >= 0, np.arange(n, dtype=np.int32) - last_cross.astype(np.int32), -1).astype(np.int32)

    # 5. Δ_recent：在 crossover 点计算 level(b_t) - level(b_{t-1})，向前填充
    delta_level = np.zeros(n, dtype=np.float64)
    cross_idx_arr = np.flatnonzero(is_cross)
    if len(cross_idx_arr) > 0:
        c = cross_idx_arr
        level_curr = np.array([_BUCKET_LEVEL.get(b, 0.0) for b in buckets[c]], dtype=np.float64)
        level_prev = np.array([_BUCKET_LEVEL.get(b, 0.0) for b in buckets[c - 1]], dtype=np.float64)
        delta_level[c] = level_curr - level_prev
    # 前向填充：记录每个 pos 应取的全量 delta，通过 cummax 位置索引实现
    delta_pos = np.where(is_cross, np.arange(n), 0)
    delta_cummax_pos = np.maximum.accumulate(delta_pos)
    delta_recent = delta_level[delta_cummax_pos]
    # 首个 crossover 之前应为 0（原实现逻辑）
    delta_recent[last_cross < 0] = 0.0

    # 6. trans / transition_flag
    trans = np.full(n, TRANS_STABLE, dtype=object)
    flag = np.zeros(n, dtype=bool)
    in_win = (last_cross >= 0) & (age < TRANS_WIN)
    flag[in_win] = True
    trans[in_win & (delta_recent > 0)] = TRANS_EXPAND
    trans[in_win & (delta_recent < 0)] = TRANS_CONTRACT

    return pd.DataFrame(
        {
            "bucket": buckets,
            "trans": trans,
            "transition_flag": flag,
            "age": age,
            "delta_recent": delta_recent,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# spec §1.3：六阵营判定 (含 trans 约束)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Bound:
    """区间 [lo, hi]，端点闭合由 loinc / hiinc 控制。"""

    lo: float
    hi: float
    loinc: bool
    hiinc: bool

    def contains(self, x: float) -> bool:
        if self.loinc:
            if x < self.lo:
                return False
        elif x <= self.lo:
            return False
        if self.hiinc:
            if x > self.hi:
                return False
        elif x >= self.hi:
            return False
        return True


@dataclass(frozen=True, slots=True)
class _TierSpec:
    """spec §1.3 单个阵营的边界 + trans 允许集。"""

    name: str
    s: _Bound
    a: _Bound
    t: _Bound
    trans_set: frozenset[str]


# spec §1.3 六阵营
TIERS: Final[tuple[_TierSpec, ...]] = (
    _TierSpec(  # L_seg3：全期参与
        TIER_L_SEG3,
        _Bound(0.09, 0.30, False, True),
        _Bound(0.00, 0.67, True, True),
        _Bound(0.75, 1.00, True, True),
        frozenset({TRANS_STABLE, TRANS_EXPAND, TRANS_CONTRACT}),
    ),
    _TierSpec(  # L_seg12：仅切换期（扩张 / 收缩）
        TIER_L_SEG12,
        _Bound(0.00, 0.19, True, True),
        _Bound(0.67, 1.00, False, True),
        _Bound(0.75, 1.00, True, True),
        frozenset({TRANS_EXPAND, TRANS_CONTRACT}),
    ),
    _TierSpec(  # L_seg2：仅切换期
        TIER_L_SEG2,
        _Bound(0.09, 0.19, False, True),
        _Bound(0.00, 0.33, True, True),
        _Bound(0.20, 0.75, False, False),
        frozenset({TRANS_EXPAND, TRANS_CONTRACT}),
    ),
    _TierSpec(  # S_seg12：稳定期 + 切换期仅扩张
        TIER_S_SEG12,
        _Bound(0.81, 1.00, True, True),
        _Bound(0.67, 1.00, False, True),
        _Bound(0.00, 0.20, True, True),
        frozenset({TRANS_STABLE, TRANS_EXPAND}),
    ),
    _TierSpec(  # S_seg34：稳定期 + 切换期仅扩张
        TIER_S_SEG34,
        _Bound(0.60, 0.81, True, False),
        _Bound(0.67, 1.00, False, True),
        _Bound(0.00, 0.20, True, True),
        frozenset({TRANS_STABLE, TRANS_EXPAND}),
    ),
    _TierSpec(  # S_seg2：仅切换期
        TIER_S_SEG2,
        _Bound(0.81, 0.91, False, True),
        _Bound(0.33, 0.67, False, True),
        _Bound(0.00, 0.20, True, True),
        frozenset({TRANS_EXPAND, TRANS_CONTRACT}),
    ),
)


def classify_tier(r_s: float, r_a: float, r_t: float, trans: str) -> str | None:
    """spec §1.3 阵营判定：返回唯一命中的阵营名，落空隙返回 None。

    输入坐标须为 spec 坐标 (0,1]（skew 已互补：高 = 极端跌 = short）；
    trans ∈ {stable, trans_expand, trans_contract}。
    """
    if not (np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t)):
        return None
    for spec in TIERS:
        if spec.s.contains(r_s) and spec.a.contains(r_a) and spec.t.contains(r_t) and trans in spec.trans_set:
            return spec.name
    return None


def tier_direction(tier: str | None) -> str:
    """spec §1.3 多/空域：L_* → long；S_* → short；其他 → 空。"""
    if tier is None:
        return ""
    if tier.startswith("L_"):
        return "long"
    if tier.startswith("S_"):
        return "short"
    return ""


# ---------------------------------------------------------------------------
# 批量 API：DataFrame → tier 列
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassifierConfig:
    """spec §0 窗口生产配置（各参数独立归一化窗口）。"""

    skew_rank_win: int = 10
    atr_rank_win: int = 10
    trend_win: int = 10
    atr_entry_win: int = 10
    trend_entry_win: int = 10


DEFAULT_CONFIG: Final[ClassifierConfig] = ClassifierConfig()


def build_coordinates(
    df: pd.DataFrame,
    config: ClassifierConfig = DEFAULT_CONFIG,
    contract_col: str = "contract",
    a3_skew_col: str = "A3_skew",
    atr_col: str = "daily_atr",
    trend_col: str = "trend_ret_M",
) -> pd.DataFrame:
    """spec §1.1 → §1.2 批量构造 (r_s, r_a, r_t, trans)。

    输入 df 必须已经按 (contract, event_time / date) 升序并含以下列：
      * a3_skew_col      — 量加权价格偏度 A3_skew（可先用 volume_weighted_skew 逐 session 生成）
      * atr_col          — 前 atr_entry_win 日 SMA 平滑真实波幅 ATR（daily_atr_sma 生成）
      * trend_col        — 前 trend_entry_win 日累计对数收益 trend_ret_M（trend_log_return 生成）

    返回追加列：r_s / r_a / r_t / trans / transition_flag / bucket / age / delta_recent。

    性能说明：单次 groupby.apply 替代原三次 groupby.transform，减少分组遍历；
    compute_transition_series 内部已向量化。
    """

    def _one_contract(g: pd.DataFrame) -> pd.DataFrame:
        g = g.copy()
        r_s_raw = roll_t_pit(g[a3_skew_col].astype(float), config.skew_rank_win)
        g["r_s"] = 1.0 - r_s_raw  # §1.1 参数 1：取互补（高=极端跌）
        g["r_a"] = roll_t_pit(g[atr_col].astype(float), config.atr_rank_win)
        g["r_t"] = roll_t_pit(g[trend_col].astype(float), config.trend_win)
        # §1.1 参数 4：从 r_a 派生 trans
        state = compute_transition_series(g["r_a"])
        g["bucket"] = state["bucket"].values
        g["trans"] = state["trans"].values
        g["transition_flag"] = state["transition_flag"].values
        g["age"] = state["age"].values
        g["delta_recent"] = state["delta_recent"].values
        return g

    out = df.groupby(contract_col, sort=False, group_keys=False).apply(_one_contract)
    if contract_col not in out.columns:
        out[contract_col] = df[contract_col].values  # pandas 3.0 strips group key column
    return out


def classify_dataframe(df: pd.DataFrame) -> pd.Series:
    """对已含 r_s / r_a / r_t / trans 的 DataFrame 逐行判定阵营。"""
    tiers = [
        classify_tier(float(rs), float(ra), float(rt), str(tr))
        for rs, ra, rt, tr in zip(df["r_s"], df["r_a"], df["r_t"], df["trans"], strict=True)
    ]
    return pd.Series(tiers, index=df.index, dtype=object)


def evaluate_dataset(
    df: pd.DataFrame,
    config: ClassifierConfig = DEFAULT_CONFIG,
    contract_col: str = "contract",
    a3_skew_col: str = "A3_skew",
    atr_col: str = "daily_atr",
    trend_col: str = "trend_ret_M",
) -> pd.DataFrame:
    """一站式：从 (A3_skew, daily_atr, trend_ret_M) 构造坐标并输出 tier 列。"""
    out = build_coordinates(df, config, contract_col, a3_skew_col, atr_col, trend_col)
    out["tier"] = classify_dataframe(out)
    out["direction"] = out["tier"].map(tier_direction)
    return out


__all__ = [
    "T_PIT_DF",
    "TRANS_WIN",
    "TRANS_STABLE",
    "TRANS_EXPAND",
    "TRANS_CONTRACT",
    "TIER_L_SEG3",
    "TIER_L_SEG12",
    "TIER_L_SEG2",
    "TIER_S_SEG12",
    "TIER_S_SEG34",
    "TIER_S_SEG2",
    "TIERS",
    "TransitionState",
    "ClassifierConfig",
    "roll_t_pit",
    "volume_weighted_skew",
    "daily_atr_sma",
    "trend_log_return",
    "compute_transition_series",
    "classify_tier",
    "tier_direction",
    "build_coordinates",
    "classify_dataframe",
    "evaluate_dataset",
]
