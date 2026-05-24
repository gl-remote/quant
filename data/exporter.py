"""数据导出模块 - 从天勤获取K线数据导出为 Qlib 格式 CSV，支持智能去重合并"""

import logging
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from .database import Database

logger = logging.getLogger(__name__)

Qlib_COLUMNS = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'money']

# 重试配置
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # 指数退避基数 (秒)


def _fetch_from_tqsdk(symbol: str, start_date: str, end_date: str,
                      kline_period: int = 1,
                      account: Optional[Dict] = None) -> pd.DataFrame:
    """从天勤 SDK 拉取 K 线数据，带自动重试

    Args:
        symbol: 品种代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        kline_period: K 线周期 (分钟)
        account: 天勤认证信息

    Returns:
        DataFrame，拉取失败时返回空 DataFrame

    Raises:
        RuntimeError: 重试耗尽后仍失败时抛出
    """
    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return _do_fetch(symbol, start_date, end_date, kline_period, account)
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                backoff = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    f"天勤数据拉取失败 (第 {attempt}/{_MAX_RETRIES} 次): {e}，"
                    f"{backoff:.0f}s 后重试..."
                )
                time.sleep(backoff)
            else:
                logger.error(f"天勤数据拉取失败，已重试 {_MAX_RETRIES} 次: {e}")

    logger.error(f"拉取 {symbol} 数据失败，已耗尽 {_MAX_RETRIES} 次重试")
    return pd.DataFrame(columns=Qlib_COLUMNS)


def _do_fetch(symbol: str, start_date: str, end_date: str,
              kline_period: int, account: Optional[Dict]) -> pd.DataFrame:
    """执行单次天勤 API 拉取（由 _fetch_from_tqsdk 的重试逻辑包裹）"""
    from tqsdk import TqApi, TqAuth, TqBacktest
    from tqsdk.exceptions import BacktestFinished

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    auth = TqAuth(account['api_key'], account['api_secret']) if account else None

    api = TqApi(backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt), auth=auth)
    klines = api.get_kline_serial(symbol, duration_seconds=kline_period * 60)

    rows = []
    prev_len = 0
    try:
        while True:
            api.wait_update()
            if api.is_changing(klines):
                current_len = len(klines)
                for i in range(prev_len, current_len):
                    ts = datetime.fromtimestamp(klines['datetime'].iloc[i] / 10 ** 9)
                    row = {
                        'datetime': ts.strftime('%Y-%m-%d %H:%M:%S'),
                        'open': float(klines['open'].iloc[i]),
                        'high': float(klines['high'].iloc[i]),
                        'low': float(klines['low'].iloc[i]),
                        'close': float(klines['close'].iloc[i]),
                        'volume': int(klines['volume'].iloc[i]),
                        'money': float(klines['close'].iloc[i]) * int(klines['volume'].iloc[i]),
                    }
                    rows.append(row)
                prev_len = current_len
    except BacktestFinished:
        pass
    except Exception:
        api.close()
        raise
    finally:
        api.close()

    df = pd.DataFrame(rows, columns=Qlib_COLUMNS)
    if not df.empty:
        df = df.sort_values('datetime').drop_duplicates(subset='datetime', keep='last')
    return df


def export_csv(symbol: str, start_date: str, end_date: str, db: Database,
               config_manager, output_path: Optional[str] = None,
               force: bool = False):
    """导出 Qlib 格式 CSV

    Args:
        symbol: 品种代码 (e.g. DCE.m2509)
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        db: Database 实例
        config_manager: ConfigManager 实例
        output_path: 自定义输出路径，优先级最高
        force: 强制覆盖模式，跳过已有数据合并，直接覆盖 CSV 和元数据
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
    if force:
        logger.info("强制覆盖模式：跳过已有数据合并")
    elif meta and Path(meta['filepath']).exists():
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