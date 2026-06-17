"""DataFeed 序列化 / 反序列化

职责：
- 将 DataFeed 完整状态写入磁盘（parquet 格式）
- 从磁盘 parquet 文件恢复完整 DataFeed 实例
- 恢复内容包括：周期数据（OHLCV + 指标）、events 表、指标注册配置

设计原则：
- 序列化格式与存储介质解耦 — 只要能读写文件，就能序列化/反序列化
- 当前实现落地到本地磁盘文件，未来可扩展到其它存储
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from .data_feed import DataFeed

# parquet 序列化时区分 OHLCV 列和指标列
_OHLCV_COLUMNS = frozenset({"open", "high", "low", "close", "volume"})

# 检查 pyarrow 是否可用（parquet 必需）
try:
    import pyarrow  # noqa: F401

    _PARQUET_OK = True
except ImportError:
    _PARQUET_OK = False


def dump_feed(feed: "DataFeed", feeds_dir: str) -> None:
    """将 DataFeed 完整状态写入目录

    文件布局：
    - {feeds_dir}/_meta.json — 元数据（symbol/source/periods/indicators）
    - {feeds_dir}/{period}.parquet — 每个周期数据（含 OHLCV 和指标列）
    - {feeds_dir}/events.parquet — events 表

    如果 pyarrow 不可用，静默跳过写入。

    :param feed: DataFeed 实例
    :param feeds_dir: 目标目录路径（自动创建父目录）
    """
    if not _PARQUET_OK:
        return

    Path(feeds_dir).mkdir(parents=True, exist_ok=True)

    # 构建 _meta.json
    indicators_serializable: dict[str, list[dict[str, Any]]] = {}
    for pn, ind_list in feed._registered_indicators.items():
        indicators_serializable[pn] = [{"name": n, "params": p} for n, p in ind_list]
    meta = {
        "symbol": feed.symbol,
        "source": feed.source,
        "base_period": feed._base_period,  # pyright: ignore[reportPrivateUsage]
        "periods": list(feed._periods.keys()),
        "indicators": indicators_serializable,
    }
    meta_path = os.path.join(feeds_dir, "_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # 各周期 parquet
    for period_name, period_data in feed._periods.items():
        fp = os.path.join(feeds_dir, f"{period_name}.parquet")
        period_data._df.to_parquet(fp, index=True)  # pyright: ignore[reportPrivateUsage]

    # events
    if not feed._events.empty:
        events_fp = os.path.join(feeds_dir, "events.parquet")
        feed._events.to_parquet(events_fp, index=False)


def load_feed(feeds_dir: str) -> "DataFeed":
    """从目录恢复 DataFeed 完整实例

    恢复后指标已经在 DataFrame 中，不需要重新计算，可直接使用。

    :param feeds_dir: 源目录路径
    :return: 恢复的 DataFeed 实例
    :raises FileNotFoundError: 目录或 _meta.json 不存在
    :raises ImportError: pyarrow 不可用
    """
    if not _PARQUET_OK:
        raise ImportError("pyarrow is required to load cached feeds")

    meta_path = os.path.join(feeds_dir, "_meta.json")
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(f"元数据文件不存在: {meta_path}")

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    feed = DataFeed(symbol=meta["symbol"])
    if meta.get("source"):
        feed.source = meta["source"]
    if meta.get("base_period"):
        feed._base_period = meta["base_period"]  # pyright: ignore[reportPrivateUsage]

    # 恢复每个周期
    for period_name in meta["periods"]:
        fp = os.path.join(feeds_dir, f"{period_name}.parquet")
        if not os.path.isfile(fp):
            continue
        df = pd.read_parquet(fp)
        # 识别指标列（非 OHLCV 的列）
        indicator_cols = [c for c in df.columns if c not in _OHLCV_COLUMNS]
        feed.register_period(period_name)
        feed._periods[period_name].load_df_parquet(df, indicator_cols)

    # 恢复指标注册配置
    for pn, ind_list in meta.get("indicators", {}).items():
        for ind in ind_list:
            feed.register_indicator(pn, ind["name"], **ind["params"])

    # events
    events_fp = os.path.join(feeds_dir, "events.parquet")
    if os.path.isfile(events_fp):
        feed._events = pd.read_parquet(events_fp)

    return feed
