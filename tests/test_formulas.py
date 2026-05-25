"""测试 common/formulas.py — 18 个量化公式函数"""

import math
import pytest
from common.formulas import (
    calculate_fifo_profit,
    total_return,
    annualized_return,
    win_rate,
    profit_factor,
    trade_cost,
    position_size,
    simple_moving_average,
    golden_cross,
    death_cross,
    stop_loss_triggered,
    take_profit_triggered,
    average_entry_price,
    drawdown_at_point,
    avg_trades_per_day,
    profitable_ratio,
    convert_annual_factor,
)


# ==============================================================================
# calculate_fifo_profit
# ==============================================================================

class TestCalculateFifoProfit:
    """FIFO 盈亏计算"""

    def _make_fill(self, action: str, price: float, volume: int) -> dict:
        return {'action': action, 'price': price, 'volume': volume}

    def test_one_buy_one_sell_profit(self):
        """单买单卖 — 盈利"""
        fills = [
            self._make_fill('buy', 10.0, 100),
            self._make_fill('sell', 12.0, 100),
        ]
        assert calculate_fifo_profit(fills) == 200.0

    def test_one_buy_one_sell_loss(self):
        """单买单卖 — 亏损"""
        fills = [
            self._make_fill('buy', 10.0, 100),
            self._make_fill('sell', 8.0, 100),
        ]
        assert calculate_fifo_profit(fills) == -200.0

    def test_two_buys_one_sell_partial_match(self):
        """两次买入一次卖出 — 部分匹配"""
        fills = [
            self._make_fill('buy', 10.0, 50),
            self._make_fill('buy', 11.0, 50),
            self._make_fill('sell', 12.0, 80),
        ]
        # 卖出 80: FIFO 先匹配第 1 笔 50@10 + 第 2 笔 30@11
        expected = (12 - 10) * 50 + (12 - 11) * 30
        assert calculate_fifo_profit(fills) == pytest.approx(expected)

    def test_two_buys_two_sells(self):
        """两次买入两次卖出"""
        fills = [
            self._make_fill('buy', 10.0, 50),
            self._make_fill('buy', 11.0, 50),
            self._make_fill('sell', 12.0, 50),
            self._make_fill('sell', 13.0, 50),
        ]
        # 卖 50@12 匹配买 50@10 → 100
        # 卖 50@13 匹配买 50@11 → 100
        assert calculate_fifo_profit(fills) == 200.0

    def test_no_trades(self):
        assert calculate_fifo_profit([]) == 0.0

    def test_sells_before_buys(self):
        """卖在买之前 (空头平仓场景) — 仅匹配重叠部分"""
        fills = [
            self._make_fill('sell', 12.0, 50),
            self._make_fill('buy', 10.0, 100),
            self._make_fill('sell', 13.0, 50),
        ]
        # 第 1 笔 sell 50 — 无买入匹配，跳过
        # 第 2 笔 buy 100 — 队列有 1 笔买入(100@10)
        # 第 3 笔 sell 50 — 匹配买入 50@10 → (13-10)*50 = 150
        # 但 FIFO 从第一笔 sell 开始匹配: sell 50@12 匹配 buy 50@10 → (12-10)*50 = 100
        # 然后 sell 50@13 匹配 buy 50@10 → (13-10)*50 = 150
        # total = 250
        assert calculate_fifo_profit(fills) == 250.0

    def test_only_buys(self):
        fills = [self._make_fill('buy', 10.0, 100)]
        assert calculate_fifo_profit(fills) == 0.0

    def test_only_sells(self):
        fills = [self._make_fill('sell', 10.0, 100)]
        assert calculate_fifo_profit(fills) == 0.0

    def test_break_even(self):
        fills = [
            self._make_fill('buy', 10.0, 100),
            self._make_fill('sell', 10.0, 100),
        ]
        assert calculate_fifo_profit(fills) == 0.0


# ==============================================================================
# total_return
# ==============================================================================

class TestTotalReturn:
    def test_positive_return(self):
        assert total_return(100000.0, 110000.0) == pytest.approx(0.1)

    def test_negative_return(self):
        assert total_return(100000.0, 90000.0) == pytest.approx(-0.1)

    def test_break_even(self):
        assert total_return(100000.0, 100000.0) == 0.0

    def test_zero_capital(self):
        assert total_return(0.0, 100000.0) == 0.0

    def test_negative_capital(self):
        assert total_return(-100000.0, 110000.0) == 0.0

    def test_below_min_trades(self):
        """交易次数不足 — 返回 0.0"""
        assert total_return(100000.0, 110000.0, min_trades=5, total_trades=3) == 0.0

    def test_meets_min_trades(self):
        assert total_return(100000.0, 110000.0, min_trades=5, total_trades=5) == pytest.approx(0.1)

    def test_zero_total_trades(self):
        assert total_return(100000.0, 110000.0, min_trades=1, total_trades=0) == 0.0


# ==============================================================================
# annualized_return
# ==============================================================================

class TestAnnualizedReturn:
    def test_one_year_unchanged(self):
        """一年正好，年化收益率 == 总收益率"""
        assert annualized_return(0.1, 252) == pytest.approx(0.1)

    def test_half_year_annualized(self):
        """半年年化放大"""
        result = annualized_return(0.05, 126)
        expected = (1.05) ** 2 - 1
        assert result == pytest.approx(expected)

    def test_two_years_annualized(self):
        """两年年化缩小"""
        result = annualized_return(0.2, 504)
        expected = (1.2) ** 0.5 - 1
        assert result == pytest.approx(expected)

    def test_zero_days(self):
        result = annualized_return(0.1, 0)
        assert result == 0.1

    def test_bankruptcy(self):
        """total_ret <= -1 (破产) — 返回 -1.0"""
        assert annualized_return(-1.0, 252) == -1.0
        assert annualized_return(-2.0, 252) == -1.0

    def test_custom_annual_factor(self):
        result = annualized_return(0.1, 365, annual_factor=365)
        assert result == pytest.approx(0.1)


# ==============================================================================
# win_rate
# ==============================================================================

class TestWinRate:
    def test_half_wins(self):
        assert win_rate(5, 10) == 0.5

    def test_all_wins(self):
        assert win_rate(10, 10) == 1.0

    def test_all_losses(self):
        assert win_rate(0, 10) == 0.0

    def test_zero_trades(self):
        assert win_rate(0, 0) == 0.0

    def test_negative_total_trades(self):
        assert win_rate(5, -1) == 0.0


# ==============================================================================
# profit_factor
# ==============================================================================

class TestProfitFactor:
    def test_normal_case(self):
        assert profit_factor(1000.0, 500.0) == 2.0

    def test_negative_loss(self):
        """total_loss 为负值"""
        assert profit_factor(1000.0, -500.0) == 2.0

    def test_zero_loss(self):
        assert profit_factor(1000.0, 0.0) == 0.0

    def test_zero_win(self):
        assert profit_factor(0.0, 500.0) == 0.0

    def test_all_zeros(self):
        assert profit_factor(0.0, 0.0) == 0.0


# ==============================================================================
# trade_cost
# ==============================================================================

class TestTradeCost:
    def test_normal_case(self):
        # price=100, quantity=10, rate=0.0003, slippage=1.0
        # = 0.0003 * 100 * 10 + 1.0 * 10 = 0.3 + 10 = 10.3
        result = trade_cost(100.0, 10, 0.0003, 1.0)
        assert result == pytest.approx(10.3)

    def test_zero_commission(self):
        assert trade_cost(100.0, 10, 0.0, 0.0) == 0.0

    def test_zero_quantity(self):
        assert trade_cost(100.0, 0, 0.0003, 1.0) == 0.0


# ==============================================================================
# position_size
# ==============================================================================

class TestPositionSize:
    def test_normal_case(self):
        # capital=100000, ratio=0.1, price=100, contract_size=10
        # 100000 * 0.1 / (100 * 10) = 10000 / 1000 = 10
        assert position_size(100000.0, 0.1, 100.0, 10) == 10

    def test_fractional_truncated(self):
        """分数手数截断"""
        # 100000 * 0.1 / (105 * 10) = 10000 / 1050 ≈ 9.52 → 9
        assert position_size(100000.0, 0.1, 105.0, 10) == 9

    def test_minimum_one_lot(self):
        """最小 1 手"""
        # 100000 * 0.01 / (5000 * 100) = 0.002 → 1
        assert position_size(100000.0, 0.01, 5000.0, 100) == 1

    def test_zero_price(self):
        assert position_size(100000.0, 0.1, 0.0, 10) == 1

    def test_zero_contract_size(self):
        assert position_size(100000.0, 0.1, 100.0, 0) == 1

    def test_negative_price(self):
        assert position_size(100000.0, 0.1, -100.0, 10) == 1


# ==============================================================================
# simple_moving_average
# ==============================================================================

class TestSimpleMovingAverage:
    def test_normal_period(self):
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert simple_moving_average(prices, 3) == pytest.approx(40.0)  # (30+40+50)/3

    def test_partial_data(self):
        """数据量不足时使用全部数据"""
        prices = [10.0, 20.0]
        assert simple_moving_average(prices, 5) == pytest.approx(15.0)

    def test_single_value(self):
        assert simple_moving_average([10.0], 5) == 10.0

    def test_empty_list(self):
        assert simple_moving_average([], 5) == 0.0

    def test_zero_period(self):
        assert simple_moving_average([10.0, 20.0], 0) == 0.0

    def test_negative_period(self):
        assert simple_moving_average([10.0, 20.0], -1) == 0.0

    def test_period_longer_than_data(self):
        prices = [1.0, 2.0, 3.0]
        assert simple_moving_average(prices, 100) == pytest.approx(2.0)


# ==============================================================================
# golden_cross / death_cross
# ==============================================================================

class TestGoldenCross:
    def test_cross_occurs(self):
        """短线上穿长线"""
        assert golden_cross(10.0, 11.0, 12.0, 11.0) is True

    def test_no_cross_staying_above(self):
        """短线一直在长线上方"""
        assert golden_cross(12.0, 10.0, 13.0, 11.0) is False

    def test_no_cross_staying_below(self):
        """短线一直在长线下方"""
        assert golden_cross(8.0, 10.0, 9.0, 11.0) is False

    def test_equal_at_prev(self):
        """前一刻短线等于长线，当前上穿"""
        assert golden_cross(10.0, 10.0, 11.0, 10.0) is True

    def test_cross_down(self):
        """短线下穿长线 (不是金叉)"""
        assert golden_cross(12.0, 10.0, 9.0, 11.0) is False


class TestDeathCross:
    def test_cross_occurs(self):
        """短线下穿长线"""
        assert death_cross(12.0, 10.0, 9.0, 11.0) is True

    def test_no_cross_staying_below(self):
        assert death_cross(8.0, 10.0, 7.0, 11.0) is False

    def test_no_cross_staying_above(self):
        assert death_cross(12.0, 10.0, 13.0, 9.0) is False

    def test_equal_at_prev(self):
        """前一刻短线等于长线，当前下穿"""
        assert death_cross(10.0, 10.0, 9.0, 10.0) is True

    def test_cross_up(self):
        """短线上穿长线 (不是死叉)"""
        assert death_cross(8.0, 10.0, 12.0, 10.0) is False


# ==============================================================================
# stop_loss_triggered / take_profit_triggered
# ==============================================================================

class TestStopLossTriggered:
    def test_hit(self):
        """跌 5% 触发 3% 止损"""
        assert stop_loss_triggered(100.0, 95.0, 0.03) is True

    def test_not_hit(self):
        """跌 1% 不触发 3% 止损"""
        assert stop_loss_triggered(100.0, 99.0, 0.03) is False

    def test_exact_boundary(self):
        """刚好触发"""
        # (100 - 97) / 100 = 0.03 >= 0.03
        assert stop_loss_triggered(100.0, 97.0, 0.03) is True

    def test_price_rise(self):
        """上涨不触发止损"""
        assert stop_loss_triggered(100.0, 110.0, 0.03) is False

    def test_zero_entry_price(self):
        assert stop_loss_triggered(0.0, 100.0, 0.03) is False

    def test_negative_entry_price(self):
        assert stop_loss_triggered(-100.0, 95.0, 0.03) is False


class TestTakeProfitTriggered:
    def test_hit(self):
        """涨 6% 触发 5% 止盈"""
        assert take_profit_triggered(100.0, 106.0, 0.05) is True

    def test_not_hit(self):
        """涨 3% 不触发 5% 止盈"""
        assert take_profit_triggered(100.0, 103.0, 0.05) is False

    def test_exact_boundary(self):
        assert take_profit_triggered(100.0, 105.0, 0.05) is True

    def test_price_fall(self):
        """下跌不触发止盈"""
        assert take_profit_triggered(100.0, 90.0, 0.05) is False

    def test_zero_entry_price(self):
        assert take_profit_triggered(0.0, 100.0, 0.05) is False


# ==============================================================================
# average_entry_price
# ==============================================================================

class TestAverageEntryPrice:
    def test_add_to_position(self):
        """加仓均价"""
        # (100 * 50 + 200 * 60) / 300 = 17000 / 300 ≈ 56.67
        result = average_entry_price(100, 50.0, 200, 60.0)
        assert result == pytest.approx(17000.0 / 300.0)

    def test_same_price(self):
        result = average_entry_price(100, 50.0, 100, 50.0)
        assert result == 50.0

    def test_new_position_only(self):
        """首次建仓 (old_position=0)"""
        result = average_entry_price(0, 0.0, 100, 50.0)
        assert result == 50.0

    def test_negative_old_position(self):
        """旧仓位为负 — 函数按 total>0 判断返回正常值"""
        # total = -1 + 100 = 99 > 0, 正常计算
        result = average_entry_price(-1, 50.0, 100, 50.0)
        expected = (-1 * 50.0 + 100 * 50.0) / 99
        assert result == pytest.approx(expected)

    def test_total_zero(self):
        """总仓位 0 — 返回 0.0"""
        assert average_entry_price(0, 50.0, 0, 60.0) == 0.0


# ==============================================================================
# drawdown_at_point
# ==============================================================================

class TestDrawdownAtPoint:
    def test_normal_drawdown(self):
        """从 100 跌到 90 → 回撤 10%"""
        assert drawdown_at_point(100.0, 90.0) == pytest.approx(0.1)

    def test_no_drawdown(self):
        """新高"""
        assert drawdown_at_point(100.0, 110.0) == pytest.approx(-0.1)

    def test_full_drawdown(self):
        """跌光"""
        assert drawdown_at_point(100.0, 0.0) == 1.0

    def test_zero_peak(self):
        assert drawdown_at_point(0.0, 100.0) == 0.0

    def test_negative_peak(self):
        assert drawdown_at_point(-100.0, -90.0) == 0.0


# ==============================================================================
# avg_trades_per_day
# ==============================================================================

class TestAvgTradesPerDay:
    def test_normal(self):
        assert avg_trades_per_day(100, 10) == 10.0

    def test_zero_days(self):
        """0 天 — 直接返回交易次数"""
        assert avg_trades_per_day(10, 0) == 10.0

    def test_negative_days(self):
        assert avg_trades_per_day(10, -1) == 10.0

    def test_fractional(self):
        result = avg_trades_per_day(7, 3)
        assert result == pytest.approx(7.0 / 3.0)

    def test_zero_trades(self):
        assert avg_trades_per_day(0, 10) == 0.0


# ==============================================================================
# profitable_ratio
# ==============================================================================

class TestProfitableRatio:
    def test_half_profitable(self):
        assert profitable_ratio(5, 10) == 0.5

    def test_all_profitable(self):
        assert profitable_ratio(10, 10) == 1.0

    def test_none_profitable(self):
        assert profitable_ratio(0, 10) == 0.0

    def test_zero_total(self):
        assert profitable_ratio(0, 0) == 0.0

    def test_negative_total(self):
        assert profitable_ratio(5, -1) == 0.0


# ==============================================================================
# convert_annual_factor
# ==============================================================================

class TestConvertAnnualFactor:
    def test_minute_kline(self):
        """1 分钟 K 线: 14400/60 = 240 根/天 * 252 = 60480"""
        assert convert_annual_factor(60) == 60480

    def test_hourly_kline(self):
        """1 小时 K 线: 14400/3600 = 4 根/天 * 252 = 1008"""
        assert convert_annual_factor(3600) == 1008

    def test_daily_kline(self):
        """日线: 14400/86400 = 0.166... — 一年 252 根"""
        result = convert_annual_factor(86400)
        # 14400/86400 = 0.1666... * 252 = 42
        assert result == 42

    def test_invalid_seconds(self):
        """非法秒数 — 返回 252"""
        assert convert_annual_factor(0) == 252
        assert convert_annual_factor(-1) == 252

    def test_5min_kline(self):
        """5 分钟 K 线: 14400/300 * 252"""
        expected = int(14400 / 300 * 252)
        assert convert_annual_factor(300) == expected
