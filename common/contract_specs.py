# -*- coding: utf-8 -*-
"""
期货品种合约规格表

交易所标准参数 + 期货公司加收，按 symbol 前缀查询。

期货公司加收说明:
  东方财富期货标准: "交易所+0.01元/手"
  broker_addon=0.01 表示每手在交易所基础上加收 1 分钱。
  其他公司通常加收 0.1~1 元/手不等，可在 config 中按需调整。
  对于费率品种(如螺纹钢)，同样加收固定金额（非比例）。

使用方法::

    from common.contract_specs import CONTRACT_SPECS, BROKER_ADDON_DFCF

    spec = CONTRACT_SPECS.get_symbol('DCE.m2505')
    total_comm = spec.total_commission(price=2910, lots=2, broker_addon=BROKER_ADDON_DFCF)
    slip = spec.slippage(lots=2)  # 滑点成本（单边）
"""

from dataclasses import dataclass, field
from typing import ClassVar


# 常见期货公司加收标准（元/手，单边）
BROKER_ADDON_DFCF = 1.3     # 东方财富: 玉米开平共5元→单边2.5, 交易所1.2, 加收=2.5-1.2=1.3
BROKER_ADDON_MEDIUM = 0.5   # 中等加收
BROKER_ADDON_HIGH = 1.0     # 较高加收（默认开户）
BROKER_ADDON_EXCHANGE = 0.0  # 仅交易所标准


@dataclass
class ContractSpec:
    """合约规格

    Attributes:
        size:       合约乘数（交易单位，吨/手 或 克/手 等）
        tick:       最小变动价位 (price_tick)
        commission: 交易所手续费基准（固定元/手，或费率如 0.0003）
        is_rate:    commission 是否为成交额费率
        margin:     交易所最低保证金比例
        slip_tick:  滑点（按 tick 倍数，默认 0.5）
    """
    size: int
    tick: float
    commission: float
    is_rate: bool = False
    margin: float = 0.07
    slip_tick: float = 0.5

    def exchange_commission(self, price: float, lots: int = 1) -> float:
        """交易所手续费（单边）

        Args:
            price: 成交价
            lots:  手数

        Returns:
            单边交易所手续费金额（元）
        """
        if self.is_rate:
            return price * lots * max(self.size, 1) * self.commission
        return self.commission * lots

    def total_commission(self, price: float, lots: int = 1,
                         broker_addon: float = BROKER_ADDON_DFCF) -> float:
        """总手续费（含期货公司加收），单边

        总手续费 = 交易所手续费 + broker_addon × 手数
        """
        return self.exchange_commission(price, lots) + broker_addon * lots

    def slippage(self, lots: int = 1) -> float:
        """滑点成本（单边）

        滑点成本 = lots × size × tick × slip_tick
        """
        return lots * max(self.size, 1) * self.tick * self.slip_tick


class _ContractRegistry:
    """合约规格注册表"""

    def __init__(self) -> None:
        self._by_prefix: dict[str, ContractSpec] = {}
        self._register_all()

    def _register(self, prefix: str, spec: ContractSpec) -> None:
        self._by_prefix[prefix.lower()] = spec

    def get_prefix(self, prefix: str) -> ContractSpec | None:
        """通过品种前缀查询（如 'm', 'rb', 'au'）"""
        return self._by_prefix.get(prefix.lower())

    def get_symbol(self, symbol: str) -> ContractSpec | None:
        """通过完整 symbol 查询（如 'DCE.m2505', 'SHFE.rb2505'）"""
        clean = symbol.split('.')[-1] if '.' in symbol else symbol
        # 去掉数字后缀: m2505 → m
        prefix = ''.join(c for c in clean if not c.isdigit())
        return self.get_prefix(prefix)

    def _register_all(self) -> None:
        # ════════════════════════════════════════
        # 大连商品交易所 (DCE)
        # ════════════════════════════════════════
        self._register('m',  ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.07))
        self._register('y',  ContractSpec(size=10, tick=1.0, commission=2.5, margin=0.07))
        self._register('c',  ContractSpec(size=10, tick=1.0, commission=1.2, margin=0.07))
        self._register('i',  ContractSpec(size=100, tick=0.5, commission=0.0003, is_rate=True, margin=0.11))
        self._register('p',  ContractSpec(size=10, tick=1.0, commission=2.5, margin=0.08))
        self._register('pp', ContractSpec(size=5, tick=1.0, commission=1.0, margin=0.07))
        self._register('v',  ContractSpec(size=5, tick=1.0, commission=1.0, margin=0.07))
        self._register('l',  ContractSpec(size=5, tick=1.0, commission=1.0, margin=0.07))  # 聚乙烯
        self._register('jm', ContractSpec(size=60, tick=0.5, commission=0.0003, is_rate=True, margin=0.11))  # 焦煤
        self._register('j',  ContractSpec(size=100, tick=0.5, commission=0.0003, is_rate=True, margin=0.11))  # 焦炭
        self._register('eg', ContractSpec(size=10, tick=1.0, commission=3.0, margin=0.08))  # 乙二醇
        self._register('eb', ContractSpec(size=5, tick=1.0, commission=3.0, margin=0.08))  # 苯乙烯
        self._register('pg', ContractSpec(size=20, tick=1.0, commission=6.0, margin=0.08))  # LPG

        # ════════════════════════════════════════
        # 上海期货交易所 (SHFE)
        # ════════════════════════════════════════
        self._register('rb', ContractSpec(size=10, tick=1.0, commission=0.0002, is_rate=True, margin=0.07))
        self._register('cu', ContractSpec(size=5, tick=10.0, commission=0.00005, is_rate=True, margin=0.05))
        self._register('al', ContractSpec(size=5, tick=5.0, commission=3.0, margin=0.05))
        self._register('zn', ContractSpec(size=5, tick=5.0, commission=3.0, margin=0.05))
        self._register('au', ContractSpec(size=1000, tick=0.02, commission=10.0, margin=0.07))
        self._register('ag', ContractSpec(size=15, tick=1.0, commission=0.00005, is_rate=True, margin=0.07))
        self._register('ru', ContractSpec(size=10, tick=5.0, commission=0.000045, is_rate=True, margin=0.05))
        self._register('hc', ContractSpec(size=10, tick=1.0, commission=0.0002, is_rate=True, margin=0.07))  # 热卷
        self._register('pb', ContractSpec(size=5, tick=5.0, commission=0.00004, is_rate=True, margin=0.05))  # 铅
        self._register('ni', ContractSpec(size=1, tick=10.0, commission=3.0, margin=0.08))  # 镍
        self._register('sn', ContractSpec(size=1, tick=10.0, commission=3.0, margin=0.08))  # 锡
        self._register('sp', ContractSpec(size=10, tick=2.0, commission=0.0001, is_rate=True, margin=0.08))  # 纸浆
        self._register('ss', ContractSpec(size=5, tick=5.0, commission=2.0, margin=0.07))  # 不锈钢
        self._register('fu', ContractSpec(size=10, tick=1.0, commission=0.00005, is_rate=True, margin=0.10))  # 燃油

        # ════════════════════════════════════════
        # 郑州商品交易所 (CZCE)
        # ════════════════════════════════════════
        self._register('sr', ContractSpec(size=10, tick=1.0, commission=3.0, margin=0.05))
        self._register('cf', ContractSpec(size=5, tick=5.0, commission=4.3, margin=0.05))
        self._register('ta', ContractSpec(size=5, tick=2.0, commission=3.0, margin=0.05))
        self._register('ma', ContractSpec(size=10, tick=1.0, commission=2.0, margin=0.05))
        self._register('rm', ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.05))
        self._register('oi', ContractSpec(size=10, tick=1.0, commission=2.0, margin=0.05))  # 菜油
        self._register('fg', ContractSpec(size=20, tick=1.0, commission=6.0, margin=0.07))  # 玻璃
        self._register('zc', ContractSpec(size=100, tick=0.2, commission=0.0003, is_rate=True, margin=0.08))  # 动煤
        self._register('sa', ContractSpec(size=20, tick=1.0, commission=0.0002, is_rate=True, margin=0.07))  # 纯碱
        self._register('ur', ContractSpec(size=20, tick=1.0, commission=0.0001, is_rate=True, margin=0.07))  # 尿素

        # ════════════════════════════════════════
        # 上海国际能源交易中心 (INE)
        # ════════════════════════════════════════
        self._register('sc', ContractSpec(size=1000, tick=0.1, commission=20.0, margin=0.05))
        self._register('nr', ContractSpec(size=10, tick=5.0, commission=0.00002, is_rate=True, margin=0.05))
        self._register('lu', ContractSpec(size=10, tick=1.0, commission=0.00001, is_rate=True, margin=0.10))

        # ════════════════════════════════════════
        # 中国金融期货交易所 (CFFEX)
        # ════════════════════════════════════════
        self._register('if', ContractSpec(size=300, tick=0.2, commission=0.000023, is_rate=True, margin=0.12))
        self._register('ic', ContractSpec(size=200, tick=0.2, commission=0.000023, is_rate=True, margin=0.08))
        self._register('ih', ContractSpec(size=300, tick=0.2, commission=0.000023, is_rate=True, margin=0.12))
        self._register('ts', ContractSpec(size=1000000, tick=0.005, commission=3.0, margin=0.005))
        self._register('tf', ContractSpec(size=1000000, tick=0.005, commission=3.0, margin=0.012))
        self._register('t',  ContractSpec(size=1000000, tick=0.005, commission=3.0, margin=0.02))


# 单例
CONTRACT_SPECS = _ContractRegistry()