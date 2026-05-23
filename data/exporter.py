"""数据导出模块 - 从天勤获取K线数据导出为 Qlib 格式 CSV，支持智能去重合并"""

import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from .database import Database

logger = logging.getLogger(__name__)

Qlib_COLUMNS = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'money']


def _fetch_from_tqsdk(symbol: str, start_date: str, end_date: str,
                      kline_period: int = 1,
                      account: Optional[Dict] = None) -> pd.DataFrame:
    """从天勤 SDK 拉取 K 线数据"""
    from tqsdk import TqApi, TqAuth, TqBacktest
    from tqsdk.exceptions import BacktestFinished

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    auth = TqAuth(account['api_key'], account['api_secret']) if account else None

    api = TqApi(backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=auth)
    klines = api.get_kline_serial(symbol, duration_seconds=kline_period * 60)

    rows = []
    try:
        while True:
            api.wait_update()
            if api.is_changing(klines):
                idx = -1
                ts = datetime.fromtimestamp(klines['datetime'].iloc[idx] / 10 ** 9)
                row = {
                    'datetime': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(klines['open'].iloc[idx]),
                    'high': float(klines['high'].iloc[idx]),
                    'low': float(klines['low'].iloc[idx]),
                    'close': float(klines['close'].iloc[idx]),
                    'volume': int(klines['volume'].iloc[idx]),
                    'money': float(klines['close'].iloc[idx]) * int(klines['volume'].iloc[idx]),
                }
                rows.append(row)
    except BacktestFinished:
        pass
    finally:
        api.close()

    df = pd.DataFrame(rows, columns=Qlib_COLUMNS)
    if not df.empty:
        df = df.sort_values('datetime').drop_duplicates(subset='datetime', keep='last')
    return df


def export_csv(symbol: str, start_date: str, end_date: str, db: Database,
               config_manager, output_path: Optional[str] = None):
    """导出 Qlib 格式 CSV，自动检测冲突并智能合并

    Args:
        symbol: 品种代码 (e.g. DCE.m2509)
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        db: Database 实例
        config_manager: ConfigManager 实例
        output_path: 自定义输出路径，优先级最高
    """
    dc = config_manager.get_data_config()
    ec = config_manager.get_export_config()
    Path(dc['export_dir']).mkdir(parents=True, exist_ok=True)

    if not output_path:
        filename = ec['filename_template'].format(symbol=symbol)
        output_path = str(Path(dc['export_dir']) / filename)

    account = config_manager.get_account_info()
    logger.info(f"开始导出 {symbol}: {start_date} ~ {end_date}")

    # 1. 拉取新数据
    new_df = _fetch_from_tqsdk(symbol, start_date, end_date, account=account)
    if new_df.empty:
        msg = "未获取到任何数据"
        logger.warning(msg)
        db.log('export', msg, symbol=symbol, status='WARNING')
        return False

    logger.info(f"从天勤获取 {len(new_df)} 条K线")

    # 2. 检查已有数据
    meta = db.get_metadata(symbol)
    merged_rows = len(new_df)
    if meta and Path(meta['filepath']).exists():
        logger.info(f"发现已有数据: {meta['filepath']} ({meta['total_rows']}条, "
                    f"{meta['min_dt']}~{meta['max_dt']})")
        try:
            old_df = pd.read_csv(meta['filepath'])
            before = len(old_df)
            combined = pd.concat([old_df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset='datetime', keep='last')
            combined = combined.sort_values('datetime').reset_index(drop=True)
            after = len(combined)
            logger.info(f"合并: 已有{before}条 + 新增{len(new_df)}条 -> 去重后{after}条 "
                        f"(删除{before + len(new_df) - after}条重复)")
            new_df = combined
            merged_rows = after
        except Exception as e:
            logger.error(f"读取已有CSV失败: {e}，将覆盖写入")
    else:
        logger.info("未发现已有数据，新建导出")

    # 3. 写入 CSV
    new_df.to_csv(output_path, index=False)
    logger.info(f"已写入: {output_path} ({len(new_df)}行)")

    # 4. 更新元数据
    min_dt = new_df['datetime'].min()
    max_dt = new_df['datetime'].max()
    db.upsert_metadata(
        symbol=symbol, filepath=output_path,
        start_date=start_date, end_date=end_date,
        min_dt=min_dt, max_dt=max_dt, total_rows=merged_rows)
    db.log('export',
           f"完成: {symbol} {start_date}~{end_date} -> {output_path} "
           f"({merged_rows}行, {min_dt}~{max_dt})",
           symbol=symbol, status='SUCCESS')
    logger.info(f"导出完成: {merged_rows}行, 时间区间 {min_dt} ~ {max_dt}")
    return True