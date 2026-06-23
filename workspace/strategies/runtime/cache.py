"""DataFeed 内存缓存

避免同进程内多条回测重复做 parquet 反序列化和指标计算。
缓存键 = symbol + 源数据日期范围，日期不匹配时自动失效。

使用方式:
    from .cache import get_cached_feed, set_cached_feed

    meta = store.get_metadata(symbol, interval=main_period)
    if meta:
        feed = get_cached_feed(symbol, meta['min_dt'], meta['max_dt'])
        if feed is not None:
            return feed  # 跳过 parquet I/O

    feed = DataFeed.from_feeds(feeds_dir)
    set_cached_feed(symbol, feed, meta['min_dt'], meta['max_dt'])
"""

from .data_feed import DataFeed

# 模块级缓存: symbol -> (DataFeed, min_dt, max_dt)
_cache: dict[str, tuple[DataFeed, str, str]] = {}


def get_cached_feed(symbol: str, min_dt: str, max_dt: str) -> DataFeed | None:
    """从内存缓存获取 DataFeed

    只有 symbol 和源数据日期范围完全匹配时才命中。
    日期不匹配时自动清除失效条目，避免返回过期数据。

    :param symbol: 品种标识
    :param min_dt: 源数据最早日期 (yyyy-mm-dd)
    :param max_dt: 源数据最晚日期 (yyyy-mm-dd)
    :return: 缓存的 DataFeed 实例，未命中返回 None
    """
    entry = _cache.get(symbol)
    if entry is None:
        return None
    feed, cached_min, cached_max = entry
    if cached_min == min_dt and cached_max == max_dt:
        return feed
    # 数据范围变了，缓存失效
    del _cache[symbol]
    return None


def get_cached_feed_by_symbol(symbol: str) -> DataFeed | None:
    """按品种获取缓存的 DataFeed，用于无源数据元信息时的进程内回退"""
    entry = _cache.get(symbol)
    return entry[0] if entry is not None else None


def set_cached_feed(symbol: str, feed: DataFeed, min_dt: str, max_dt: str) -> None:
    """将 DataFeed 存入内存缓存

    后续同 symbol 的回测可直接命中，跳过 parquet 反序列化。

    :param symbol: 品种标识
    :param feed: DataFeed 实例
    :param min_dt: 源数据最早日期 (yyyy-mm-dd)
    :param max_dt: 源数据最晚日期 (yyyy-mm-dd)
    """
    _cache[symbol] = (feed, min_dt, max_dt)


def clear_cache() -> None:
    """清空所有缓存"""
    _cache.clear()
