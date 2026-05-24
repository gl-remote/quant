"""数据加载与划分模块 - 从CSV加载历史数据，提供 Walk-Forward 窗口划分"""

import logging
import re
import pandas as pd
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_symbol_exchange(symbol: str) -> tuple[str, str]:
    """解析品种代码中的交易所信息，统一返回字符串类型

    Args:
        symbol: 完整合约代码 (e.g. DCE.m2509)

    Returns:
        (pure_symbol, exchange_code) 均为字符串
    """
    if '.' in symbol:
        parts = symbol.split('.')
        pure_symbol = parts[-1]
        exchange_code = parts[0]
    else:
        pure_symbol = symbol
        exchange_code = 'CFFEX'

    return pure_symbol, exchange_code


def scan_csv_files(data_dir: str, pattern: Optional[str] = None) -> List[Tuple[str, Path]]:
    """扫描数据目录，匹配符合正则表达式的CSV文件并提取品种代码

    文件命名规则:
      - {symbol}.csv
      - {symbol}_qlib.csv
      - {symbol}_*.csv

    Args:
        data_dir: CSV文件存放目录
        pattern: 可选的品种代码正则表达式，匹配从文件名提取的 symbol 部分
                 未提供则匹配所有CSV文件

    Returns:
        [(symbol, filepath), ...] 按 symbol 排序的去重列表
    """
    csv_dir = Path(data_dir)
    if not csv_dir.exists():
        logger.warning(f"数据目录不存在: {data_dir}")
        return []

    files = sorted(csv_dir.glob("*.csv"))
    if not files:
        logger.warning(f"数据目录为空: {data_dir}")
        return []

    seen = set()
    result = []
    regex = re.compile(pattern) if pattern else None

    for fp in files:
        name = fp.stem
        symbol = name[:-5] if name.endswith('_qlib') else name

        if regex and not regex.search(symbol):
            continue

        if symbol not in seen:
            seen.add(symbol)
            result.append((symbol, fp))

    if regex and not result:
        logger.warning(f"没有文件匹配正则表达式: {pattern}")

    logger.info(f"扫描到 {len(result)} 个品种: {[s for s, _ in result]}")
    return result


def load_csv_data(data_dir: str, symbol: str) -> Optional[pd.DataFrame]:
    """从本地CSV目录加载历史K线数据

    支持的文件命名模式:
      - {symbol}.csv
      - {symbol}_qlib.csv
      - {symbol}_*.csv (匹配第一个)

    Args:
        data_dir: CSV文件存放目录
        symbol: 品种代码 (e.g. DCE.m2509)

    Returns:
        DataFrame with columns: datetime, open, high, low, close, volume
    """
    csv_dir = Path(data_dir)
    if not csv_dir.exists():
        logger.error(f"数据目录不存在: {data_dir}")
        return None

    candidates = [
        csv_dir / f"{symbol}.csv",
        csv_dir / f"{symbol}_qlib.csv",
    ] + sorted(csv_dir.glob(f"{symbol}_*.csv"))

    filepath = None
    for fp in candidates:
        if fp.exists():
            filepath = fp
            break

    if filepath is None:
        logger.error(f"未找到 {symbol} 的数据文件于 {data_dir}")
        return None

    logger.info(f"加载数据: {filepath}")
    df = pd.read_csv(filepath)

    if 'datetime' not in df.columns:
        logger.error(f"CSV缺少datetime列，实际列: {list(df.columns)}")
        return None

    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)

    logger.info(f"加载完成: {len(df)} 条K线, 时间范围 {df['datetime'].min().strftime('%Y-%m-%d')} ~ {df['datetime'].max().strftime('%Y-%m-%d')}")
    return df


def df_to_vnpy_datalines(df: pd.DataFrame, symbol: str, interval=None) -> list:
    """将DataFrame转换为vn.py回测引擎可用的 BarData 列表

    将Qlib格式CSV (datetime, open, high, low, close, volume) 转换为
    vnpy BarData 对象列表，可直接注入 BacktestingEngine.history_data

    Args:
        df: Qlib格式的K线数据
        symbol: 合约代码 (vnpy格式: 品种.交易所, e.g. m2509.DCE)
        interval: vnpy Interval 枚举，None 时回退到 Interval.DAILY

    Returns:
        vnpy BarData 对象列表
    """
    required_cols = {'datetime', 'open', 'high', 'low', 'close', 'volume'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"数据缺少必要列: {missing}")

    try:
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange, Interval
    except ImportError:
        logger.warning("vnpy未安装，返回字典格式数据")
        bars = []
        for _, row in df.iterrows():
            dt = row['datetime']
            if isinstance(dt, str):
                dt = pd.to_datetime(dt)
            bars.append({
                'symbol': symbol,
                'datetime': dt,
                'open_price': float(row['open']),
                'high_price': float(row['high']),
                'low_price': float(row['low']),
                'close_price': float(row['close']),
                'volume': float(row['volume']),
            })
        return bars

    pure_symbol, exchange_code = parse_symbol_exchange(symbol)
    exchange = Exchange(exchange_code) if Exchange else exchange_code
    bar_interval = interval if interval is not None else Interval.DAILY

    bars = []
    for _, row in df.iterrows():
        dt = row['datetime']
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        bar = BarData(
            symbol=pure_symbol,
            exchange=exchange,
            datetime=dt,
            interval=bar_interval,
            open_price=float(row['open']),
            high_price=float(row['high']),
            low_price=float(row['low']),
            close_price=float(row['close']),
            volume=float(row['volume']),
            gateway_name="CSV",
        )
        bars.append(bar)

    logger.info(f"转换完成: {len(bars)} 条 BarData")
    return bars


# ── 日期过滤 ──────────────────────────────────────────────

def filter_dataframe_by_date(
    df: 'pd.DataFrame',
    start_date: str | None = None,
    end_date: str | None = None,
) -> 'pd.DataFrame':
    """按日期范围过滤 DataFrame，重置索引

    纯函数，不修改原 DataFrame。适用于 run_full_pipeline
    和 run_walk_forward 的数据裁剪。

    Args:
        df: 含 'datetime' 列的 K 线 DataFrame
        start_date: 可选起始日期 (闭区间)
        end_date: 可选结束日期 (闭区间)

    Returns:
        过滤后的 DataFrame (copy, reindexed)
    """
    if start_date:
        df = df[df['datetime'] >= start_date]
    if end_date:
        df = df[df['datetime'] <= end_date]
    return df.reset_index(drop=True)


# ============================================================
# Walk-Forward 时间序列交叉验证
# ============================================================

def walk_forward_split(
    df: pd.DataFrame,
    train_size: int = 200,
    val_size: int = 40,
    test_size: int = 40,
    step: int = 40,
) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Walk-Forward 时间序列交叉验证 — 生成多个滚动窗口

    按时间顺序滚动生成 (训练集, 验证集, 测试集) 三元组。
    每个窗口在前一个窗口基础上向前滑动 step 行。

    与单次全量回测相比:
      - 单次全量回测: 结果受所选时间段影响大
      - Walk-Forward: 多窗口滚动验证，模拟策略在实际时间推进中的表现

    示例 (数据 1000 行, train=200, val=40, test=40, step=40):
      Window 0: train[0:200],  val[200:240],  test[240:280]
      Window 1: train[40:240], val[240:280],  test[280:320]
      ...

    Args:
        df: 按时间排序的完整历史数据集
        train_size: 每个窗口的训练集行数
        val_size: 每个窗口的验证集行数
        test_size: 每个窗口的测试集行数
        step: 窗口滑动步长 (行数)，越小窗口越多

    Returns:
        [(train_df, val_df, test_df), ...] 按时间顺序排列的窗口列表
    """
    n = len(df)
    min_required = train_size + val_size + test_size
    if n < min_required:
        raise ValueError(
            f"数据量不足：需要至少 {min_required} 行，当前 {n} 行"
        )

    windows = []
    start = 0
    while start + min_required <= n:
        train_end = start + train_size
        val_end = train_end + val_size
        test_end = val_end + test_size

        train_df = df.iloc[start:train_end].reset_index(drop=True)
        val_df = df.iloc[train_end:val_end].reset_index(drop=True)
        test_df = df.iloc[val_end:test_end].reset_index(drop=True)

        windows.append((train_df, val_df, test_df))
        start += step

    logger.info(
        f"Walk-Forward 划分: {len(windows)} 个窗口 "
        f"(train={train_size}, val={val_size}, test={test_size}, step={step}, "
        f"数据量={n})"
    )
    return windows


def walk_forward_split_by_ratio(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    step_ratio: float = 0.1,
    min_windows: int = 3,
) -> List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Walk-Forward 时间序列交叉验证 — 基于比例参数

    将 walk_forward_split 的行数参数转换为比例参数，
    自动计算合适的窗口大小。

    Args:
        df: 按时间排序的完整历史数据集
        train_ratio: 训练集占窗口总长度的比例 (默认 0.6)
        val_ratio: 验证集占窗口总长度的比例 (默认 0.2)
        test_ratio: 测试集占窗口总长度的比例 (默认 0.2)
        step_ratio: 滑动步长占窗口总长度的比例 (默认 0.1)
        min_windows: 最少需要的窗口数

    Returns:
        [(train_df, val_df, test_df), ...] 按时间顺序排列的窗口列表
    """
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-9:
        raise ValueError(f"比例之和必须为 1.0，当前: {total_ratio}")

    n = len(df)
    # 窗口总行数 = 全量数据 / (1 + (min_windows - 1) * step_ratio)
    # 使得至少有 min_windows 个窗口
    window_total = int(n / (1 + (min_windows - 1) * step_ratio))

    train_size = int(window_total * train_ratio)
    val_size = int(window_total * val_ratio)
    # 用剩余行数兜底，避免多次 int 截断导致每个窗口丢 1~2 行
    test_size = window_total - train_size - val_size
    step = max(1, int(window_total * step_ratio))

    # 修正浮点导致的窗口总大小偏差
    actual_window = train_size + val_size + test_size
    if actual_window + step > n:
        step = max(1, (n - actual_window) // max(min_windows - 1, 1))

    logger.info(
        f"Walk-Forward (按比例): 窗口总行={actual_window} "
        f"(train={train_size}, val={val_size}, test={test_size}), "
        f"step={step}, 数据量={n}"
    )

    return walk_forward_split(df, train_size, val_size, test_size, step)