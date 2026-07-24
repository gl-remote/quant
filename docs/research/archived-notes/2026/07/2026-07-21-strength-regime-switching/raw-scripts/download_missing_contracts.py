"""下载缺失的合约 1h 数据：DCE.c2609, DCE.cs2609, DCE.m2609"""

import asyncio
from pathlib import Path

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
    # 绕过tqsdk日志权限问题：禁用日志
    import logging
    logging.basicConfig(level=logging.CRITICAL)

    asyncio.run(main())
