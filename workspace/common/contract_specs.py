"""
期货品种合约规格表（期货合约成本）

成本模型（2026-07-10 修订）:
  单边真实成本 = 交易所手续费 × (1 + broker_markup)
  - `commission` 全表统一记录「交易所手续费基准」：固定值=元/手，或成交额费率（is_rate=True）。
  - `broker_markup` 为「期货公司加收比例」，由每个 ContractSpec 自行携带（默认 2.0，即加收 200%、总×3），
    不再使用全局常量；以账户结算单为准逐品种校准。

数据口径与精度（2026-07-10 用 akshare 全量校准）:
  - size / tick / commission / margin 全部品种（仅 `lr` 晚籼稻无活跃合约数据、保留原值）均已由
    akshare `futures_fees_info` + `futures_rule` 校准：
      · size / tick  = 交易所标准合约（合约乘数 / 最小变动价位）；
      · commission   = 交易所手续费基准（akshare 区分固定值 元/手 与 成交额费率 is_rate）；
      · margin       = 当前交易所保证金比例（含调控上浮，非最低基准，随市场调整）。
  - broker_markup（期货公司加收）由每品种携带，默认 2.0（加收200%、总×3，保守高估）；
    其中 ap/cu/lh/j/pm/ic/im/au/wh/ec/zc 等 11 个「交易所基准手续费本就偏高、4 跳难覆盖成本」的品种
    已下调至 0.1（优惠档），避免 ×3 高点在高基准上进一步失真。以上均为占位值，待东财结算单逐品种校准。
  - 以上为 2026-07-10 快照；交易所费率/保证金会调整，实盘前以交易所/东财最新公布为准。

期权品种见文件末尾 OPTION_CONTRACT_SPECS（当前回测引擎不消费，仅作权限口径补全）。

使用方法::

    from common.contract_specs import CONTRACT_SPECS

    spec = CONTRACT_SPECS.get_symbol('DCE.m2505')
    total_comm = spec.total_commission(price=2910, lots=2)  # 含该品种 broker_markup
    slip = spec.slippage(lots=2)  # 滑点成本（单边）
"""

from dataclasses import dataclass

from common.symbol_utils import extract_contract_prefix


@dataclass
class ContractSpec:
    """合约规格

    Attributes:
        size:           合约乘数（交易单位，吨/手 或 克/手 等）
        tick:           最小变动价位 (price_tick)
        commission:     交易所手续费基准（固定元/手，或成交额费率，is_rate=True）
        is_rate:        commission 是否为成交额费率
        broker_markup:  期货公司加收比例（占交易所手续费），每品种携带，默认 2.0(加收 200%，总×3)
        margin:         交易所最低保证金比例
        slip_tick:      滑点（按 tick 倍数，默认 0.5）
    """

    size: int
    tick: float
    commission: float
    is_rate: bool = False
    broker_markup: float = 2.0
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

    def total_commission(self, price: float, lots: int = 1, broker_markup: float | None = None) -> float:
        """总手续费（单边，含期货公司加收）。

        total = 交易所手续费 × (1 + broker_markup)
        broker_markup 默认取本品种 self.broker_markup（东财零售加点，默认加收 200%（总×3）），
        调用时可传参临时覆盖。
        """
        if broker_markup is None:
            broker_markup = self.broker_markup
        return self.exchange_commission(price, lots) * (1.0 + broker_markup)

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
        prefix = extract_contract_prefix(symbol)
        if prefix is None:
            return None
        return self.get_prefix(prefix)

    def _register_all(self) -> None:
        # ════════════════════════════════════════
        # 大连商品交易所 (DCE)
        # （DCE 品种已于 2026-07-10 用 akshare 校准：commission=交易所基准，broker_markup 默认 2.0）
        # ════════════════════════════════════════
        self._register("m", ContractSpec(size=10, tick=1.0, commission=1.51, is_rate=False, margin=0.12))
        self._register("y", ContractSpec(size=10, tick=1.0, commission=2.51, is_rate=False, margin=0.13))
        self._register("c", ContractSpec(size=10, tick=1.0, commission=1.21, is_rate=False, margin=0.11))
        self._register("i", ContractSpec(size=100, tick=0.5, commission=0.000101, is_rate=True, margin=0.23))
        self._register("p", ContractSpec(size=10, tick=1.0, commission=2.51, is_rate=False, margin=0.14))
        self._register("pp", ContractSpec(size=5, tick=1.0, commission=1.01, is_rate=False, margin=0.13))
        self._register("v", ContractSpec(size=5, tick=1.0, commission=1.01, is_rate=False, margin=0.13))
        self._register("l", ContractSpec(size=5, tick=1.0, commission=1.01, is_rate=False, margin=0.13))  # 聚乙烯
        self._register("jm", ContractSpec(size=60, tick=0.5, commission=0.000101, is_rate=True, margin=0.28))  # 焦煤
        self._register(
            "j", ContractSpec(size=100, tick=0.5, commission=0.000141, is_rate=True, margin=0.28, broker_markup=0.1)
        )  # 焦炭
        self._register("eg", ContractSpec(size=10, tick=1.0, commission=3.01, is_rate=False, margin=0.15))  # 乙二醇
        self._register("eb", ContractSpec(size=5, tick=1.0, commission=1.01, is_rate=False, margin=0.17))  # 苯乙烯
        self._register("pg", ContractSpec(size=20, tick=1.0, commission=6.01, is_rate=False, margin=0.15))  # LPG

        # ════════════════════════════════════════
        # 上海期货交易所 (SHFE)
        # ════════════════════════════════════════
        self._register("rb", ContractSpec(size=10, tick=1.0, commission=6.1e-05, is_rate=True, margin=0.13))
        self._register(
            "cu", ContractSpec(size=5, tick=10.0, commission=5.1e-05, is_rate=True, margin=0.13, broker_markup=0.1)
        )
        self._register("al", ContractSpec(size=5, tick=5.0, commission=3.01, is_rate=False, margin=0.13))
        self._register("zn", ContractSpec(size=5, tick=5.0, commission=3.01, is_rate=False, margin=0.13))
        self._register(
            "au", ContractSpec(size=1000, tick=0.02, commission=20.01, is_rate=False, margin=0.14, broker_markup=0.1)
        )
        self._register("ag", ContractSpec(size=15, tick=1.0, commission=1.1e-05, is_rate=True, margin=0.17))
        self._register("ru", ContractSpec(size=10, tick=5.0, commission=3.01, is_rate=False, margin=0.14))
        self._register("hc", ContractSpec(size=10, tick=1.0, commission=6.1e-05, is_rate=True, margin=0.13))  # 热卷
        self._register("pb", ContractSpec(size=5, tick=5.0, commission=4.1e-05, is_rate=True, margin=0.13))  # 铅
        self._register("ni", ContractSpec(size=1, tick=10.0, commission=3.01, is_rate=False, margin=0.18))  # 镍
        self._register("sn", ContractSpec(size=1, tick=10.0, commission=3.01, is_rate=False, margin=0.21))  # 锡
        self._register("sp", ContractSpec(size=10, tick=2.0, commission=2.1e-05, is_rate=True, margin=0.14))  # 纸浆
        self._register("ss", ContractSpec(size=5, tick=5.0, commission=2.01, is_rate=False, margin=0.13))  # 不锈钢
        self._register("fu", ContractSpec(size=10, tick=1.0, commission=1.1e-05, is_rate=True, margin=0.2))  # 燃油

        # ════════════════════════════════════════
        # 郑州商品交易所 (CZCE)
        # ════════════════════════════════════════
        self._register("sr", ContractSpec(size=10, tick=1.0, commission=2.01, is_rate=False, margin=0.13))
        self._register("cf", ContractSpec(size=5, tick=5.0, commission=4.31, is_rate=False, margin=0.15))
        self._register("ta", ContractSpec(size=5, tick=2.0, commission=3.01, is_rate=False, margin=0.15))
        self._register("ma", ContractSpec(size=10, tick=1.0, commission=0.000101, is_rate=True, margin=0.17))
        self._register("rm", ContractSpec(size=10, tick=1.0, commission=1.51, is_rate=False, margin=0.17))
        self._register("oi", ContractSpec(size=10, tick=1.0, commission=2.01, is_rate=False, margin=0.17))  # 菜油
        self._register("fg", ContractSpec(size=20, tick=1.0, commission=2.01, is_rate=False, margin=0.23))  # 玻璃
        self._register(
            "zc", ContractSpec(size=100, tick=0.2, commission=150.01, is_rate=False, margin=0.62, broker_markup=0.1)
        )  # 动煤
        self._register("sa", ContractSpec(size=20, tick=1.0, commission=0.000101, is_rate=True, margin=0.23))  # 纯碱
        self._register("ur", ContractSpec(size=20, tick=1.0, commission=0.000101, is_rate=True, margin=0.17))  # 尿素

        # ════════════════════════════════════════
        # 上海国际能源交易中心 (INE)
        # ════════════════════════════════════════
        self._register("sc", ContractSpec(size=1000, tick=0.1, commission=20.01, is_rate=False, margin=0.24))
        self._register("nr", ContractSpec(size=10, tick=5.0, commission=2.1e-05, is_rate=True, margin=0.14))
        self._register("lu", ContractSpec(size=10, tick=1.0, commission=1.1e-05, is_rate=True, margin=0.18))

        # ════════════════════════════════════════
        # 中国金融期货交易所 (CFFEX)
        # ════════════════════════════════════════
        self._register(
            "if", ContractSpec(size=300, tick=0.2, commission=2.4e-05, is_rate=True, margin=0.14, broker_markup=2.0)
        )
        self._register(
            "ic", ContractSpec(size=200, tick=0.2, commission=2.4e-05, is_rate=True, margin=0.14, broker_markup=0.1)
        )
        self._register(
            "ih", ContractSpec(size=300, tick=0.2, commission=2.4e-05, is_rate=True, margin=0.14, broker_markup=2.0)
        )
        self._register(
            "ts", ContractSpec(size=20000, tick=0.002, commission=3.01, is_rate=False, margin=0.008, broker_markup=2.0)
        )
        self._register(
            "tf", ContractSpec(size=10000, tick=0.005, commission=3.01, is_rate=False, margin=0.017, broker_markup=2.0)
        )
        self._register(
            "t", ContractSpec(size=10000, tick=0.005, commission=3.01, is_rate=False, margin=0.025, broker_markup=2.0)
        )

        # ════════════════════════════════════════
        # 2026-07-10 补全此前缺失的期货品种
        # 口径统一：commission 全表为「交易所手续费基准」；期货公司加收由每品种 broker_markup 携带
        # （默认 2.0；高交易所基准品种 ap/cu/lh/j/pm/ic/im/au/wh/ec/zc 已下调至 0.1），待东财结算单逐品种校准。
        # size/tick 以交易所标准合约 + akshare(CZCE) 校验；比例值及新品种为估算。
        # ════════════════════════════════════════

        # —— CFFEX 补全：im(中证1000), tl(30年国债) ——
        self._register(
            "im", ContractSpec(size=200, tick=0.2, commission=2.4e-05, is_rate=True, margin=0.14, broker_markup=0.1)
        )
        self._register(
            "tl", ContractSpec(size=10000, tick=0.01, commission=3.01, is_rate=False, margin=0.05, broker_markup=2.0)
        )

        # —— SHFE 补全：ao(氧化铝), br(合成橡胶), bu(沥青), wr(线材) ——
        self._register("ao", ContractSpec(size=20, tick=1.0, commission=0.000101, is_rate=True, margin=0.15))  # 氧化铝
        self._register("br", ContractSpec(size=5, tick=5.0, commission=2.1e-05, is_rate=True, margin=0.2))  # 合成橡胶
        self._register("bu", ContractSpec(size=10, tick=1.0, commission=5.1e-05, is_rate=True, margin=0.18))  # 沥青
        self._register("wr", ContractSpec(size=10, tick=1.0, commission=4.1e-05, is_rate=True, margin=0.15))  # 线材

        # —— INE 补全：bc(国际铜), ec(集运指数/欧线) ——
        self._register("bc", ContractSpec(size=5, tick=10.0, commission=1.1e-05, is_rate=True, margin=0.13))  # 国际铜
        self._register(
            "ec", ContractSpec(size=50, tick=0.5, commission=0.000601, is_rate=True, margin=0.22, broker_markup=0.1)
        )

        # —— DCE 补全：a(豆一), b(豆二), cs(玉米淀粉), jd(鸡蛋), lg(原木), lh(生猪), rr(粳米) ——
        # 注：fb/bb(纤维板/胶合板) 流动性极低，暂未纳入。
        self._register("a", ContractSpec(size=10, tick=1.0, commission=2.01, is_rate=False, margin=0.12))  # 豆一
        self._register("b", ContractSpec(size=10, tick=1.0, commission=1.01, is_rate=False, margin=0.15))  # 豆二
        self._register("cs", ContractSpec(size=10, tick=1.0, commission=1.51, is_rate=False, margin=0.11))  # 玉米淀粉
        self._register("jd", ContractSpec(size=10, tick=1.0, commission=0.000151, is_rate=True, margin=0.14))  # 鸡蛋
        self._register("lg", ContractSpec(size=90, tick=0.5, commission=0.000101, is_rate=True, margin=0.08))
        self._register(
            "lh", ContractSpec(size=16, tick=5.0, commission=0.000201, is_rate=True, margin=0.11, broker_markup=0.1)
        )  # 生猪
        self._register("rr", ContractSpec(size=10, tick=1.0, commission=1.01, is_rate=False, margin=0.09))  # 粳米

        # —— GFEX 补全：si(工业硅), lc(碳酸锂), ps(多晶硅), pd(钯), pt(铂) ——
        self._register("si", ContractSpec(size=5, tick=5.0, commission=0.000101, is_rate=True, margin=0.14))  # 工业硅
        self._register("lc", ContractSpec(size=1, tick=20.0, commission=0.000161, is_rate=True, margin=0.17))  # 碳酸锂
        self._register("ps", ContractSpec(size=3, tick=5.0, commission=0.000101, is_rate=True, margin=0.13))  # 多晶硅
        self._register("pd", ContractSpec(size=1000, tick=0.05, commission=0.000101, is_rate=True, margin=0.16))
        self._register("pt", ContractSpec(size=1000, tick=0.05, commission=0.000101, is_rate=True, margin=0.16))

        # —— CZCE 补全 15 个：size/tick 取 akshare 交易所标准；commission 绝对值取自 akshare 交易所基准，
        #    比例值(PX/SH)按交易所标准费率估算。 ——
        self._register(
            "ap", ContractSpec(size=10, tick=1.0, commission=5.01, is_rate=False, margin=0.17, broker_markup=0.1)
        )  # 苹果
        self._register("cj", ContractSpec(size=5, tick=5.0, commission=3.01, is_rate=False, margin=0.18))  # 红枣
        self._register("cy", ContractSpec(size=5, tick=5.0, commission=1.01, is_rate=False, margin=0.15))  # 棉纱
        self._register("jr", ContractSpec(size=20, tick=1.0, commission=3.01, is_rate=False, margin=0.6))  # 粳稻
        self._register("lr", ContractSpec(size=20, tick=1.0, commission=3.0, margin=0.05))  # 晚籼稻
        self._register("pf", ContractSpec(size=5, tick=2.0, commission=2.01, is_rate=False, margin=0.16))  # 短纤
        self._register("pk", ContractSpec(size=5, tick=2.0, commission=2.01, is_rate=False, margin=0.13))  # 花生
        self._register(
            "pm", ContractSpec(size=50, tick=1.0, commission=30.01, is_rate=False, margin=0.6, broker_markup=0.1)
        )  # 普麦
        self._register("px", ContractSpec(size=5, tick=2.0, commission=0.000101, is_rate=True, margin=0.2))
        self._register("ri", ContractSpec(size=20, tick=1.0, commission=2.51, is_rate=False, margin=0.6))  # 早籼稻
        self._register("rs", ContractSpec(size=10, tick=1.0, commission=2.01, is_rate=False, margin=0.6))  # 菜籽
        self._register("sf", ContractSpec(size=5, tick=2.0, commission=2.01, is_rate=False, margin=0.19))  # 硅铁
        self._register("sh", ContractSpec(size=30, tick=1.0, commission=0.000101, is_rate=True, margin=0.2))
        self._register("sm", ContractSpec(size=5, tick=2.0, commission=2.01, is_rate=False, margin=0.19))  # 锰硅
        self._register(
            "wh", ContractSpec(size=20, tick=1.0, commission=30.01, is_rate=False, margin=0.6, broker_markup=0.1)
        )  # 强麦


# 单例
CONTRACT_SPECS = _ContractRegistry()


# ════════════════════════════════════════════════════════════════════════════════════════
# 期权合约规格表（补充，当前回测引擎不消费）
#
# 东方财富普通用户开通全部权限后可交易期权。期权与期货成本结构不同（按手固定佣金、保证金通常为
# 权利金比例），故单列。以下为流动性较好的主力期权，乘数(multiplier, 元/点)与固定每手佣金为估算，
# 需以交易所/东财最新费率为准；未列出的商品期权可按需补充。键名约定为「标的期货前缀 + '_o'」。
# ════════════════════════════════════════════════════════════════════════════════════════


@dataclass
class OptionSpec:
    """期权合约规格（粗略成本，仅供权限口径补全，不参与期货回测）"""

    underlying: str  # 对应标的期货前缀
    multiplier: float  # 每点价值（元/点），即合约乘数
    commission: float  # 单边每手固定佣金（元/手，含交易所+券商估算）
    margin_rate: float = 0.07  # 保证金占权利金比例（粗略）
    slip_tick: float = 0.5

    def premium_commission(self, lots: int = 1) -> float:
        """单边每手固定佣金合计。"""
        return self.commission * lots

    def slippage(self, premium_tick: float, lots: int = 1) -> float:
        """滑点成本（单边） = lots × multiplier × premium_tick × slip_tick。"""
        return lots * self.multiplier * premium_tick * self.slip_tick


_OPTION_REGISTRY: dict[str, OptionSpec] = {
    # 股指期权 (CFFEX)：乘数均为 100 元/点
    "io": OptionSpec(underlying="if", multiplier=100.0, commission=15.0, margin_rate=0.10),  # 沪深300
    "mo": OptionSpec(underlying="im", multiplier=100.0, commission=15.0, margin_rate=0.10),  # 中证1000
    "ho": OptionSpec(underlying="ih", multiplier=100.0, commission=15.0, margin_rate=0.10),  # 上证50
    # 商品期权（乘数同标的期货，佣金为估算每手固定值）
    "m_o": OptionSpec(underlying="m", multiplier=10.0, commission=1.5),
    "y_o": OptionSpec(underlying="y", multiplier=10.0, commission=1.5),
    "c_o": OptionSpec(underlying="c", multiplier=10.0, commission=1.2),
    "cu_o": OptionSpec(underlying="cu", multiplier=5.0, commission=5.0),
    "au_o": OptionSpec(underlying="au", multiplier=100.0, commission=2.0),
    "ru_o": OptionSpec(underlying="ru", multiplier=10.0, commission=3.0),
    "ta_o": OptionSpec(underlying="ta", multiplier=5.0, commission=3.0),
    "ma_o": OptionSpec(underlying="ma", multiplier=10.0, commission=2.0),
    "sr_o": OptionSpec(underlying="sr", multiplier=10.0, commission=3.0),
    "cf_o": OptionSpec(underlying="cf", multiplier=5.0, commission=4.3),
    "rb_o": OptionSpec(underlying="rb", multiplier=10.0, commission=2.0),
    "i_o": OptionSpec(underlying="i", multiplier=100.0, commission=2.0),
    "ag_o": OptionSpec(underlying="ag", multiplier=15.0, commission=2.0),
    "sc_o": OptionSpec(underlying="sc", multiplier=1000.0, commission=10.0),
    "pg_o": OptionSpec(underlying="pg", multiplier=20.0, commission=6.0),
}

OPTION_CONTRACT_SPECS: dict[str, OptionSpec] = _OPTION_REGISTRY
