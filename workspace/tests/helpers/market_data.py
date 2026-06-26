"""测试用行情数据构造。"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def make_sample_closes() -> list[float]:
    base = 100.0
    return [base + i * 0.5 + np.random.normal(0, 0.2) for i in range(50)]


def make_sample_kline_df() -> pd.DataFrame:
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]
    close = 3000.0 + np.cumsum(np.random.normal(0, 10, 100))
    return pd.DataFrame(
        {
            "datetime": dates,
            "open": close - np.random.uniform(0, 5, 100),
            "high": close + np.random.uniform(0, 10, 100),
            "low": close - np.random.uniform(0, 10, 100),
            "close": close,
            "volume": np.random.randint(1000, 50000, 100),
        }
    )
