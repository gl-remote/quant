"""简单直接下载 c2609 1h - 同步版本"""

import os
import logging
from pathlib import Path

# 从环境变量读取认证信息
from dotenv import load_dotenv
load_dotenv('/Users/gaolei/Documents/src/quant/.env')

api_key = os.getenv('TQSDK_API_KEY')
api_secret = os.getenv('TQSDK_API_SECRET')

print(f"API key: {api_key[:8]}...")

import pandas as pd
from tqsdk import TqApi, TqAuth

REPO = Path("/Users/gaolei/Documents/src/quant")
OUT_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["DCE.c2609", "DCE.cs2609", "DCE.m2609"]


def download_symbol(symbol: str):
    print(f"\nDownloading {symbol} 1h ...")

    auth = TqAuth(api_key, api_secret)
    api = TqApi(auth=auth)

    try:
        # 同步方式获取k线
        # get_kline_serial 会等待数据返回
        klines = api.get_kline_serial(symbol, 3600, data_length=20000)
        print(f"  Got {len(klines)} klines")

        if len(klines) == 0:
            print(f"  No data for {symbol}")
            return

        df = pd.DataFrame({
            "datetime": pd.to_datetime(klines["datetime"], unit="ns").dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai").dt.strftime("%Y-%m-%d %H:%M:%S"),
            "open": klines["open"],
            "high": klines["high"],
            "low": klines["low"],
            "close": klines["close"],
            "volume": klines["volume"],
            "open_oi": klines["open_oi"],
            "close_oi": klines["close_oi"],
        })

        df = df[df["datetime"] >= "2025-08-01"].reset_index(drop=True)

        out_path = OUT_DIR / f"{symbol}.tqsdk.1h.csv"
        df.to_csv(out_path, index=False)
        print(f"  Saved to {out_path}")
        if len(df) > 0:
            print(f"  Date range: {df['datetime'].min()} → {df['datetime'].max()}")
            print(f"  Total rows: {len(df)}")

    finally:
        api.close()


def main():
    for sym in SYMBOLS:
        download_symbol(sym)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
    main()
