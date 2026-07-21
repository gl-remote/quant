"""使用项目已有数据源下载 DCE.c2609 1h 数据"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/Users/gaolei/Documents/src/quant')

import pandas as pd
from dotenv import load_dotenv
from workspace.data.datasource.tqsdk_source import TqSdkDataSource
from workspace.config.manager import ConfigManager

REPO = Path("/Users/gaolei/Documents/src/quant")
OUT_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载环境变量
load_dotenv(REPO / ".env")


def main():
    config = ConfigManager()
    source = TqSdkDataSource()
    account = config.get_tqsdk_account()

    print(f"Downloading DCE.c2609 1h from 2025-08-01 to 2026-07-21 ...")
    df = source.fetch_kline("DCE.c2609", "2025-08-01", "2026-07-21", "1h", account=account)

    print(f"Got {len(df)} rows")
    if len(df) == 0:
        print("No data downloaded")
        return

    print(f"Date range: {df['datetime'].min()} → {df['datetime'].max()}")

    # 保存
    out_path = OUT_DIR / "DCE.c2609.tqsdk.1h.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")

    # 同时下载 cs2609 和 m2609
    for symbol in ["DCE.cs2609", "DCE.m2609"]:
        print(f"\nDownloading {symbol} ...")
        df_sym = source.fetch_kline(symbol, "2025-08-01", "2026-07-21", "1h", account=account)
        if len(df_sym) > 0:
            out_path = OUT_DIR / f"{symbol}.tqsdk.1h.csv"
            df_sym.to_csv(out_path, index=False)
            print(f"Saved {symbol} {len(df_sym)} rows to {out_path}")
        else:
            print(f"No data for {symbol}")


if __name__ == "__main__":
    main()
