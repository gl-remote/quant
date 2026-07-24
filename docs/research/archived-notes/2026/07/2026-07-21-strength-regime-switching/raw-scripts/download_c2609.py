"""下载 DCE.c2609 1h 数据"""

import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqsdk import TqApi, TqKq

REPO = Path("/Users/gaolei/Documents/src/quant")
OUT_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL = "DCE.c2609"
INTERVAL = "1h"


async def download():
    print(f"Downloading {SYMBOL} {INTERVAL} ...")
    api = TqApi(TqKq())
    await api._connect()

    try:
        # 获取K线，从上市到现在
        klines = await api.get_kline_serial(SYMBOL, 3600)  # 3600s = 1h
        print(f"Got {len(klines)} klines")

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
        out_path = OUT_DIR / f"{SYMBOL}.tqsdk.1h.csv"
        df.to_csv(out_path, index=False)
        print(f"Saved to {out_path}")
        print(f"Date range: {df['datetime'].min()} → {df['datetime'].max()}")
        print(f"Total rows: {len(df)}")

    finally:
        await api.close()


def main():
    asyncio.run(download())


if __name__ == "__main__":
    main()
