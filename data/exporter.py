"""数据导出模块 — 从可切换的数据源获取 K 线并导出为 Qlib 格式 CSV

支持的数据源通过 data/datasource/ 统一抽象，默认读取配置文件中的 provider。
统一默认 interval=1m，各数据源内部自行处理兼容性。
未指定日期时，自动从合约代码推算：交割月前 4 个月 ~ 交割月。
"""

from __future__ import annotations

from loguru import logger
import pandas as pd
from pathlib import Path
from typing import TYPE_CHECKING

from common.symbol_utils import resolve_date_range
from .manager import DataManager
from .datasource import get_data_source

if TYPE_CHECKING:
    from config.app_config import ConfigManager

def _build_output_path(
    symbol: str,
    provider: str,
    interval: str,
    export_dir: str,
    filename_template: str,
) -> str:
    """根据 symbol + provider + interval 构建标准输出路径"""
    filename = filename_template.format(symbol=symbol, provider=provider, interval=interval)
    return str(Path(export_dir) / filename)


def _should_merge(meta: dict[str, object] | None, output_path: str) -> bool:
    """检查已有数据是否应合并：仅当文件路径一致时合并"""
    if meta is None:
        return False
    existing_path = str(meta.get("filepath", ""))
    if not existing_path or not Path(existing_path).exists():
        return False
    if Path(existing_path).resolve() != Path(output_path).resolve():
        logger.info(
            f"已有数据文件路径不匹配 ({Path(existing_path).name} ≠ "
            f"{Path(output_path).name})，跳过合并"
        )
        return False
    return True


def export_csv(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
    dm: DataManager | None = None,
    config_manager: ConfigManager | None = None,
    output_path: str | None = None,
    force: bool = False,
    interval: str = "1m",
    source: str | None = None,
) -> bool:
    """导出 Qlib 格式 CSV

    所有数据源统一默认 interval=1m。日期未指定时由合约代码自动推算。

    Args:
        symbol: 品种代码 (e.g. DCE.m2509)
        start_date: 开始日期 YYYY-MM-DD，None 时自动推算
        end_date: 结束日期 YYYY-MM-DD，None 时自动推算
        dm: DataManager 实例，None 时自动创建
        config_manager: ConfigManager 实例，None 时自动创建
        output_path: 自定义输出路径
        force: 强制覆盖模式
        interval: K线周期 (默认 '1m')
        source: 数据源名称，None 时从配置读取
    """
    if config_manager is None:
        from config import ConfigManager
        config_manager = ConfigManager()

    if dm is None:
        dm = DataManager(config_manager)

    try:
        dc = config_manager.get_data_config()
        Path(dc.export_dir).mkdir(parents=True, exist_ok=True)

        # 日期范围：用户指定 > 合约自动推算
        resolved_start, resolved_end = resolve_date_range(
            symbol, start_date, end_date
        )

        # 获取数据源（需在 output_path 之前，因为文件名含 provider）
        ds = get_data_source(provider=source, config_manager=config_manager)

        # 确定输出路径
        if not output_path:
            output_path = _build_output_path(
                symbol, ds.name, interval, dc.export_dir, dc.filename_template
            )

        logger.info(
            f"导出 {symbol}: {resolved_start} ~ {resolved_end} "
            f"[数据源: {ds.name}, interval: {interval}]"
        )

        # 构建额外参数
        fetch_kwargs: dict[str, object] = {}
        if ds.name == "tqsdk":
            fetch_kwargs["account"] = config_manager.get_account_info()

        new_df = ds.fetch_kline(
            symbol=symbol,
            start_date=resolved_start,
            end_date=resolved_end,
            interval=interval,
            **fetch_kwargs,
        )
        if new_df.empty:
            msg = f"未获取到任何数据 [{ds.name}]"
            logger.warning(msg)
            dm.store.log("export", msg, symbol=symbol, status="WARNING")
            return False

        logger.debug(f"从 {ds.name} 获取 {len(new_df)} 条K线")

        # 合并已有数据
        meta = dm.store.get_metadata(symbol)
        merged_rows = len(new_df)
        if force:
            logger.info("强制覆盖模式：跳过已有数据合并")
        elif _should_merge(meta, output_path):
            assert meta is not None  # pyright 类型收窄
            filepath = str(meta["filepath"])
            logger.debug(
                f"发现已有数据: {filepath} ({meta['total_rows']}条, "
                f"{meta['min_dt']}~{meta['max_dt']})"
            )
            try:
                old_df = pd.read_csv(filepath)
                before = len(old_df)
                combined = pd.concat([old_df, new_df], ignore_index=True)
                combined = combined.drop_duplicates(subset="datetime", keep="last")
                combined = combined.sort_values("datetime").reset_index(drop=True)
                after = len(combined)
                logger.debug(
                    f"合并: 已有{before}条 + 新增{len(new_df)}条 → 去重后{after}条 "
                    f"(删除{before + len(new_df) - after}条重复)"
                )
                new_df = combined
                merged_rows = after
            except Exception as e:
                logger.error(f"读取已有CSV失败: {e}，将覆盖写入")
        else:
            logger.info("未发现已有数据或文件不匹配，新建导出")

        new_df.to_csv(output_path, index=False)
        logger.debug(f"已写入: {output_path} ({len(new_df)}行)")

        min_dt = str(new_df["datetime"].min())
        max_dt = str(new_df["datetime"].max())
        dm.store.upsert_metadata(
            symbol=symbol,
            provider=ds.name,
            interval=interval,
            filepath=output_path,
            start_date=resolved_start,
            end_date=resolved_end,
            min_dt=min_dt,
            max_dt=max_dt,
            total_rows=merged_rows,
        )
        dm.store.log(
            "export",
            f"完成: {symbol} {resolved_start}~{resolved_end} [{ds.name}] → "
            f"{output_path} ({merged_rows}行, {min_dt}~{max_dt})",
            symbol=symbol,
            status="SUCCESS",
        )
        logger.info(f"导出完成: {merged_rows}行, 时间区间 {min_dt} ~ {max_dt}")
        return True
    finally:
        dm.close()
