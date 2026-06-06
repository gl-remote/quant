"""合约代码解析工具 — 从品种代码提取交易所/合约月份/默认导出日期范围

品种代码格式: {交易所}.{合约代码}
  合约代码格式: {产品}{YY}{MM}
  例如:
    DCE.m2509  → 大商所 豆粕 2025年9月交割
    SHFE.rb2410 → 上期所 螺纹钢 2024年10月交割
    CZCE.SR309  → 郑商所 白糖 2023年9月交割

默认导出时间范围:
  交割月前 4 个月到交割月（含 3 个完整交易月）
  例如 m2509: 2025-05-01 ~ 2025-09-01
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from dateutil.relativedelta import relativedelta


@dataclass
class ContractInfo:
    """合约信息"""

    symbol: str  # 原始品种代码，如 DCE.m2509
    exchange: str  # 交易所，如 DCE
    product: str  # 产品代码，如 m
    year: int  # 交割年份，如 2025
    month: int  # 交割月份，如 9
    delivery_date: str  # 交割月首日，如 2025-09-01

    @property
    def contract_code(self) -> str:
        """纯合约代码（不含交易所前缀），如 m2509"""
        return f"{self.product}{self.year % 100:02d}{self.month:02d}"

    @property
    def default_start(self) -> str:
        """默认导出开始日期: 交割月 - 4 个月"""
        result: str = (datetime(self.year, self.month, 1) - relativedelta(months=4)).strftime("%Y-%m-%d")
        return result

    @property
    def default_end(self) -> str:
        """默认导出结束日期: 交割月首日"""
        return f"{self.year:04d}-{self.month:02d}-01"


def parse_contract(symbol: str) -> ContractInfo | None:
    """解析期货品种代码，提取合约信息

    支持两种格式:
      - 标准 YYMM:  m2509  → product=m,   year=2025, month=09
      - 简写 YMM:   SR309  → product=SR,  year=2023, month=09

    Args:
        symbol: 品种代码，如 DCE.m2509

    Returns:
        ContractInfo，解析失败返回 None
    """
    # 提取交易所和合约代码
    if "." in symbol:
        exchange, contract = symbol.split(".", 1)
    else:
        exchange, contract = "", symbol

    # 先尝试标准 YYMM 格式 (4位数字后缀)
    m_std = re.match(r"^(.+?)(\d{2})(\d{2})$", contract)
    if m_std:
        product = m_std.group(1)
        yy = int(m_std.group(2))
        mm = int(m_std.group(3))
        if 1 <= mm <= 12:
            return _build_contract(symbol, exchange, product, 2000 + yy, mm)

    # 再尝试简写 YMM 格式 (3位数字后缀，如 SR309)
    m_short = re.match(r"^(\D+)(\d)(\d{2})$", contract)
    if m_short:
        product = m_short.group(1)
        y = int(m_short.group(2))
        mm = int(m_short.group(3))
        if 1 <= mm <= 12:
            # 年份推断: 当前年 - 当前年%10 + y，处理跨年代
            current_year = datetime.now().year
            year = (current_year // 10 * 10) + y
            if year > current_year + 1:  # 不会超过明年
                year -= 10
            return _build_contract(symbol, exchange, product, year, mm)

    return None


def _build_contract(symbol: str, exchange: str, product: str, year: int, month: int) -> ContractInfo:
    """构造 ContractInfo 实例"""
    return ContractInfo(
        symbol=symbol,
        exchange=exchange,
        product=product,
        year=year,
        month=month,
        delivery_date=f"{year:04d}-{month:02d}-01",
    )


def resolve_date_range(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[str, str]:
    """解析导出日期范围，未指定时从合约代码自动推算

    Args:
        symbol: 品种代码
        start_date: 用户指定的开始日期，None 则自动推算
        end_date: 用户指定的结束日期，None 则自动推算

    Returns:
        (start_date, end_date) 元组

    Raises:
        ValueError: 无法解析合约代码且未提供日期范围
    """
    if start_date and end_date:
        return start_date, end_date

    contract = parse_contract(symbol)
    if contract is None:
        if not start_date or not end_date:
            raise ValueError(f"无法解析合约代码 {symbol!r}，请显式指定 --start 和 --end")
        return start_date, end_date

    resolved_start = start_date or contract.default_start
    resolved_end = end_date or contract.default_end
    return resolved_start, resolved_end
