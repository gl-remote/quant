"""数据加载与划分模块 - 从CSV加载历史数据并按科学比例划分训练/验证/测试集"""

import logging
import re
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_symbol_exchange(symbol: str):
    try:
        from vnpy.trader.constant import Exchange
    except ImportError:
        Exchange = None

    if '.' in symbol:
        parts = symbol.split('.')
        pure_symbol = parts[-1]
        exchange_code = parts[0]
        if Exchange:
            try:
                exchange = Exchange(exchange_code)
            except (ValueError, TypeError):
                exchange = Exchange.CFFEX
        else:
            exchange = 'CFFEX'
    else:
        pure_symbol = symbol
        exchange = Exchange.CFFEX if Exchange else 'CFFEX'

    return pure_symbol, exchange


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
        symbol = name.replace("_qlib", "")

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


def split_datasets(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    random_seed: int = 42,
    shuffle: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """将完整数据集按科学比例随机划分为训练集、验证集和测试集

    划分策略:
      - 默认按时间顺序划分 (shuffle=False): 前60%训练, 中间20%验证, 后20%测试
        适合时间序列数据，避免未来信息泄露
      - 随机打乱划分 (shuffle=True): 适合跨品种/跨时间段的稳健性验证
        注意：随机打乱可能引入前视偏差，仅在特定场景下使用

    Args:
        df: 完整历史数据集
        train_ratio: 训练集比例 (默认0.6)
        val_ratio: 验证集比例 (默认0.2)
        test_ratio: 测试集比例 (默认0.2)
        random_seed: 随机种子，保证可复现
        shuffle: 是否随机打乱（True=随机采样, False=时间顺序划分）

    Returns:
        (train_df, val_df, test_df) 三个子数据集
    """
    total = train_ratio + val_ratio + test_ratio
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"划分比例之和必须为1.0，当前: {total}")

    n = len(df)
    if n < 10:
        raise ValueError(f"数据量不足 ({n}条)，至少需要10条数据")

    if shuffle:
        df = df.sample(frac=1, random_state=random_seed).reset_index(drop=True)

    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train_df = df.iloc[:train_end].reset_index(drop=True)
    val_df = df.iloc[train_end:val_end].reset_index(drop=True)
    test_df = df.iloc[val_end:].reset_index(drop=True)

    logger.info(
        f"数据集划分 (shuffle={shuffle}, seed={random_seed}): "
        f"训练集 {len(train_df)}条 ({train_ratio:.0%}), "
        f"验证集 {len(val_df)}条 ({val_ratio:.0%}), "
        f"测试集 {len(test_df)}条 ({test_ratio:.0%})"
    )

    return train_df, val_df, test_df


def df_to_vnpy_datalines(df: pd.DataFrame, symbol: str) -> list:
    """将DataFrame转换为vn.py回测引擎可用的 BarData 列表

    将Qlib格式CSV (datetime, open, high, low, close, volume) 转换为
    vnpy BarData 对象列表，可直接注入 BacktestingEngine.history_data

    Args:
        df: Qlib格式的K线数据
        symbol: 合约代码 (vnpy格式: 品种.交易所, e.g. m2509.DCE)

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

    pure_symbol, exchange = parse_symbol_exchange(symbol)

    bars = []
    for _, row in df.iterrows():
        dt = row['datetime']
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        bar = BarData(
            symbol=pure_symbol,
            exchange=exchange,
            datetime=dt,
            interval=Interval.DAILY,
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


def get_dataset_info(df: pd.DataFrame, name: str = "") -> Dict:
    """获取数据集的基本统计信息

    Args:
        df: K线数据DataFrame
        name: 数据集名称 (train/val/test)

    Returns:
        包含统计信息的字典
    """
    if df is None or df.empty:
        return {'name': name, 'count': 0}

    return {
        'name': name,
        'count': len(df),
        'start_date': df['datetime'].min().strftime('%Y-%m-%d %H:%M:%S'),
        'end_date': df['datetime'].max().strftime('%Y-%m-%d %H:%M:%S'),
        'days': (df['datetime'].max() - df['datetime'].min()).days,
        'price_min': float(df['close'].min()),
        'price_max': float(df['close'].max()),
        'price_mean': float(df['close'].mean()),
        'price_std': float(df['close'].std()),
        'volume_mean': float(df['volume'].mean()),
    }


# ============================================================
# Walk-Forward 时间序列交叉验证
# ============================================================

def walk_forward_split(
    df: pd.DataFrame,
    train_size: int = 200,
    val_size: int = 40,
    test_size: int = 40,
    step: int = 40,
) -> List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Walk-Forward 时间序列交叉验证 — 生成多个滚动窗口

    按时间顺序滚动生成 (训练集, 验证集, 测试集) 三元组。
    每个窗口在前一个窗口基础上向前滑动 step 行。

    与单次划分 (split_datasets) 相比:
      - 单次划分: 一次 6:2:2，结果偶然性大
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
    test_size = int(window_total * test_ratio)
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