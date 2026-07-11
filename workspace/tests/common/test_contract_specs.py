"""common/contract_specs.py 成本模型测试

覆盖:
    - ContractSpec.exchange_commission（固定元/手 / 成交额费率 is_rate 两分支）
    - ContractSpec.total_commission（默认 broker_markup ×3 / 显式覆盖）
    - ContractSpec.slippage（lots×size×tick×slip_tick）
    - CONTRACT_SPECS 注册表（get_symbol / get_prefix / 未知品种返回 None）
"""

import pytest

from common.contract_specs import CONTRACT_SPECS, ContractSpec


class TestExchangeCommission:
    def test_fixed_per_lot(self):
        spec = ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.1)
        assert spec.exchange_commission(price=100.0, lots=2) == pytest.approx(3.0)

    def test_rate_by_turnover(self):
        spec = ContractSpec(size=10, tick=1.0, commission=0.0001, is_rate=True, margin=0.1)
        # price × lots × size × rate
        assert spec.exchange_commission(price=2000.0, lots=3) == pytest.approx(2000.0 * 3 * 10 * 0.0001)


class TestTotalCommission:
    def test_default_broker_markup(self):
        # broker_markup 默认 2.0 ⇒ 总 = 交易所基准 ×(1+2.0) = ×3
        spec = ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.1)
        assert spec.total_commission(price=100.0, lots=2) == pytest.approx(1.5 * 3 * 2)

    def test_explicit_broker_markup_field(self):
        spec = ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.1, broker_markup=0.1)
        assert spec.total_commission(price=100.0, lots=1) == pytest.approx(1.5 * 1.1)

    def test_broker_markup_call_override(self):
        spec = ContractSpec(size=10, tick=1.0, commission=1.5, margin=0.1, broker_markup=0.1)
        assert spec.total_commission(price=100.0, lots=1, broker_markup=0.5) == pytest.approx(1.5 * 1.5)


class TestSlippage:
    def test_slippage_formula(self):
        spec = ContractSpec(size=10, tick=1.0, commission=1.0, margin=0.1, slip_tick=0.5)
        assert spec.slippage(lots=2) == pytest.approx(2 * 10 * 1.0 * 0.5)


class TestRegistry:
    def test_get_symbol_returns_spec(self):
        spec = CONTRACT_SPECS.get_symbol("DCE.m2601")
        assert spec is not None
        assert spec.size == 10

    def test_get_prefix_applies_new_cost_model(self):
        # m 品种: 交易所基准 1.51 ×(1+默认 broker_markup 2.0) = 4.53/手
        spec = CONTRACT_SPECS.get_prefix("m")
        assert spec is not None
        assert spec.total_commission(price=100.0, lots=2) == pytest.approx(1.51 * 3 * 2)

    def test_unknown_symbol_returns_none(self):
        assert CONTRACT_SPECS.get_symbol("NOPE.x9999") is None
