"""下载缺失的合约 1h 数据，patch tqsdk 日志绕过权限问题"""

import asyncio
import logging
import sys
from pathlib import Path

# Patch: 禁用 FileHandler
original_file_handler = logging.FileHandler


def null_file_handler(*args, **kwargs):
    # 不创建文件，直接用 StreamHandler
    return logging.StreamHandler(sys.stdout)


logging.FileHandler = null_file_handler

import pandas as pd
from tqsdk import TqApi, TqKq

REPO = Path("/Users/gaolei/Documents/src/quant")
OUT_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["DCE.c2609", "DCE.cs2609", "DCE.m2609"]


async def download_symbol(symbol: str):
    print(f"\nDownloading {symbol} 1h ...")
    api = TqApi(TqKq())
    await api._connect()

    try:
        # 获取K线，从上市到现在
        klines = await api.get_kline_serial(symbol, 3600)  # 3600s = 1h
        print(f"  Got {len(klines)} klines")

        if len(klines) == 0:
            print(f"  No data for {symbol}")
            return

        # 转换为 DataFrame
        df = pd.DataFrame({
            "datetime": pd.to_datetime(klines["datetime"], unit="ns"),
            "open": klines["open"],
            "high": klines["high"],
            "low": klines["low"],
            "close": klines["close"],
            "volume": klines["volume"],
            "open_oi": klines["open_oi"],
            "close_oi": klines["close_oi"],
        })

        # 保存
        out_path = OUT_DIR / f"{symbol}.tqsdk.1h.csv"
        df.to_csv(out_path, index=False)
        print(f"  Saved to {out_path}")
        print(f"  Date range: {df['datetime'].min()} → {df['datetime'].max()}")
        print(f"  Total rows: {len(df)}")

    finally:
        await api.close()


async def main():
    for sym in SYMBOLS:
        await download_symbol(sym)


if __name__ == "__main__":
    print("Patching logging.FileHandler to avoid permission error...")
    asyncio.run(main())
