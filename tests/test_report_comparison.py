import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from backtest.report import (
    _extract_performance_metrics,
    _extract_risk_metrics,
    _extract_trade_summary,
    format_console_report,
    generate_dataset_report,
)
from backtest.comparison import (
    _parse_pct,
    _safe_name,
    _analyze_return_degradation,
    _analyze_risk_increase,
    _assess_overfitting,
    format_comparison_report,
    generate_merged_report,
    format_merged_report,
)


class TestExtractPerformanceMetrics:
    def test_empty_stats_returns_defaults(self):
        result = _extract_performance_metrics({}, 100000.0)
        assert result['initial_capital'] == 100000.0
        assert result['final_equity'] == 100000.0
        assert result['total_return'] == '0.00%'
        assert result['total_return_abs'] == 0.0
        assert result['total_trades'] == 0
        assert result['winning_trades'] == 0
        assert result['losing_trades'] == 0
        assert result['win_rate'] == '0.00%'
        assert result['win_rate_abs'] == 0.0
        assert result['avg_profit'] == 0
        assert result['avg_loss'] == 0
        assert result['profit_loss_ratio'] == 0
        assert result['sharpe_ratio'] == 0
        assert result['annual_return'] == '0.00%'
        assert result['annual_return_abs'] == 0

    def test_none_stats_returns_defaults(self):
        result = _extract_performance_metrics(None, 100000.0)
        assert result['initial_capital'] == 100000.0
        assert result['total_trades'] == 0

    def test_non_dict_stats_returns_defaults(self):
        result = _extract_performance_metrics([], 100000.0)
        assert result['initial_capital'] == 100000.0
        assert result['total_trades'] == 0

    def test_valid_stats(self):
        stats = {
            'end_balance': 115000.0,
            'total_trades': 50,
            'win_trades': 30,
            'loss_trades': 20,
            'average_win': 800.0,
            'average_loss': -400.0,
            'win_loss_ratio': 2.0,
            'sharpe_ratio': 1.5,
            'annual_return': 0.25,
        }
        result = _extract_performance_metrics(stats, 100000.0)
        assert result['initial_capital'] == 100000.0
        assert result['final_equity'] == 115000.0
        assert result['total_return'] == '15.00%'
        assert result['total_return_abs'] == 15000.0
        assert result['total_trades'] == 50
        assert result['winning_trades'] == 30
        assert result['losing_trades'] == 20
        assert result['win_rate'] == '60.00%'
        assert pytest.approx(result['win_rate_abs']) == 0.6
        assert result['avg_profit'] == 800.0
        assert result['avg_loss'] == -400.0
        assert result['profit_loss_ratio'] == 2.0
        assert result['sharpe_ratio'] == 1.5
        assert result['annual_return'] == '25.00%'
        assert result['annual_return_abs'] == 0.25

    def test_stats_with_zero_trades(self):
        stats = {
            'end_balance': 100000.0,
            'total_trades': 0,
            'win_trades': 0,
            'loss_trades': 0,
        }
        result = _extract_performance_metrics(stats, 100000.0)
        assert result['win_rate'] == '0.00%'
        assert result['win_rate_abs'] == 0.0

    def test_stats_zero_initial_capital(self):
        stats = {'end_balance': 0}
        result = _extract_performance_metrics(stats, 0.0)
        assert result['total_return'] == '0.00%'


class TestExtractRiskMetrics:
    def test_valid_risk_stats(self):
        stats = {
            'max_drawdown': 0.15,
            'max_ddpercent_duration': 10,
            'daily_std': 0.02,
            'return_drawdown_ratio': 1.5,
        }
        result = _extract_risk_metrics(stats)
        assert result['max_drawdown'] == '15.00%'
        assert result['max_drawdown_abs'] == 0.15
        assert result['max_drawdown_duration'] == 10
        assert result['daily_std'] == 0.02
        assert result['return_drawdown_ratio'] == 1.5

    def test_empty_risk_stats(self):
        result = _extract_risk_metrics({})
        assert result['max_drawdown'] == '0.00%'
        assert result['max_drawdown_abs'] == 0
        assert result['max_drawdown_duration'] == 0
        assert result['daily_std'] == 0
        assert result['return_drawdown_ratio'] == 0


class TestExtractTradeSummary:
    def test_valid_trade_stats(self):
        stats = {
            'total_trades': 100,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'total_days': 250,
            'max_consecutive_win': 8,
            'max_consecutive_loss': 4,
        }
        result = _extract_trade_summary(stats)
        assert result['total_trades'] == 100
        assert result['start_date'] == '2024-01-01'
        assert result['end_date'] == '2024-12-31'
        assert result['total_days'] == 250
        assert pytest.approx(result['avg_trades_per_day']) == 0.4
        assert result['max_consecutive_win'] == 8
        assert result['max_consecutive_loss'] == 4

    def test_empty_trade_stats(self):
        result = _extract_trade_summary({})
        assert result['total_trades'] == 0
        assert result['start_date'] == ''
        assert result['end_date'] == ''
        assert result['total_days'] == 0
        assert result['avg_trades_per_day'] == 0.0

    def test_zero_total_days(self):
        stats = {'total_trades': 10, 'total_days': 0}
        result = _extract_trade_summary(stats)
        assert result['avg_trades_per_day'] == 10.0


class TestFormatConsoleReport:
    def test_returns_non_empty_string(self):
        report = {
            'performance': {
                'initial_capital': 100000.0,
                'final_equity': 115000.0,
                'total_return': '15.00%',
                'annual_return': '25.00%',
                'total_trades': 50,
                'winning_trades': 30,
                'losing_trades': 20,
                'win_rate': '60.00%',
                'avg_profit': 800.0,
                'avg_loss': -400.0,
                'profit_loss_ratio': 2.0,
                'sharpe_ratio': 1.5,
            },
            'risk': {
                'max_drawdown': '15.00%',
                'daily_std': 0.02,
                'return_drawdown_ratio': 1.5,
            },
            'trades': {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
                'total_days': 250,
            },
        }
        result = format_console_report(report, '训练集')
        assert isinstance(result, str)
        assert len(result) > 0
        assert '资金概况' in result
        assert '交易统计' in result
        assert '风险评估' in result
        assert '训练集' in result
        assert '100,000.00' in result

    def test_with_defaults(self):
        report = {
            'performance': {},
            'risk': {},
            'trades': {},
        }
        result = format_console_report(report, '测试')
        assert isinstance(result, str)
        assert len(result) > 0
        assert '测试' in result


class TestParsePct:
    def test_percentage_string(self):
        assert _parse_pct('12.5%') == 0.125
        assert _parse_pct('0%') == 0.0
        assert _parse_pct('100%') == 1.0
        assert _parse_pct('-5.0%') == -0.05

    def test_numeric_input(self):
        assert _parse_pct(0.125) == 0.125
        assert _parse_pct(1.0) == 1.0
        assert _parse_pct(0) == 0.0
        assert _parse_pct(-0.05) == -0.05

    def test_empty_string(self):
        with pytest.raises(ValueError):
            _parse_pct('')

    def test_none_value(self):
        assert _parse_pct(None) == 0.0

    def test_integer_input(self):
        assert _parse_pct(1) == 1.0
        assert _parse_pct(0) == 0.0


class TestSafeName:
    def test_dict_with_meta_dataset(self):
        report = {'meta': {'dataset': 'train'}}
        assert _safe_name(report) == 'train'

    def test_dict_with_meta_name_only(self):
        report = {'meta': {'name': 'training_set'}}
        assert _safe_name(report) == 'training_set'

    def test_dict_with_meta_prefers_dataset(self):
        report = {'meta': {'dataset': 'val', 'name': 'validation'}}
        assert _safe_name(report) == 'val'

    def test_dict_without_meta(self):
        report = {'performance': {}}
        assert _safe_name(report) == 'unknown'

    def test_dict_with_empty_meta(self):
        report = {'meta': {}}
        assert _safe_name(report) == 'unknown'

    def test_non_dict_input(self):
        assert _safe_name(None) == 'unknown'
        assert _safe_name('string') == 'unknown'
        assert _safe_name(123) == 'unknown'
        assert _safe_name([]) == 'unknown'


class TestAnalyzeReturnDegradation:
    def _make_p(self, total_return):
        return {'total_return': total_return}

    def test_decreasing_high_risk(self):
        tp = self._make_p('50.0%')
        vp = self._make_p('30.0%')
        ep = self._make_p('5.0%')
        result = _analyze_return_degradation(tp, vp, ep)
        assert result['risk_level'] == 'high'
        assert result['train_to_test'] > 20

    def test_decreasing_medium_risk(self):
        tp = self._make_p('20.0%')
        vp = self._make_p('12.0%')
        ep = self._make_p('5.0%')
        result = _analyze_return_degradation(tp, vp, ep)
        assert result['risk_level'] == 'medium'

    def test_decreasing_low_risk(self):
        tp = self._make_p('10.0%')
        vp = self._make_p('8.0%')
        ep = self._make_p('5.0%')
        result = _analyze_return_degradation(tp, vp, ep)
        assert result['risk_level'] == 'low'

    def test_no_degradation(self):
        tp = self._make_p('5.0%')
        vp = self._make_p('8.0%')
        ep = self._make_p('10.0%')
        result = _analyze_return_degradation(tp, vp, ep)
        assert result['risk_level'] == 'none'
        assert result['train_to_test'] <= 0

    def test_exact_boundary_20(self):
        tp = self._make_p('30.0%')
        vp = self._make_p('20.0%')
        ep = self._make_p('10.0%')
        result = _analyze_return_degradation(tp, vp, ep)
        assert result['train_to_test'] == 20
        assert result['risk_level'] == 'medium'


class TestAnalyzeRiskIncrease:
    def _make_r(self, max_drawdown):
        return {'max_drawdown': max_drawdown}

    def test_high_risk_increase(self):
        tr = self._make_r('5.0%')
        vr = self._make_r('8.0%')
        er = self._make_r('20.0%')
        result = _analyze_risk_increase(tr, vr, er)
        assert result['risk_level'] == 'high'
        assert result['train_to_test'] > 10

    def test_medium_risk_increase(self):
        tr = self._make_r('5.0%')
        vr = self._make_r('8.0%')
        er = self._make_r('12.0%')
        result = _analyze_risk_increase(tr, vr, er)
        assert result['risk_level'] == 'medium'
        assert 5 < result['train_to_test'] <= 10

    def test_low_risk_increase(self):
        tr = self._make_r('5.0%')
        vr = self._make_r('5.5%')
        er = self._make_r('6.0%')
        result = _analyze_risk_increase(tr, vr, er)
        assert result['risk_level'] == 'low'
        assert result['train_to_test'] <= 5

    def test_exact_boundary_10(self):
        tr = self._make_r('5.0%')
        vr = self._make_r('10.0%')
        er = self._make_r('15.0%')
        result = _analyze_risk_increase(tr, vr, er)
        assert result['train_to_test'] == 10
        assert result['risk_level'] == 'medium'


class TestAssessOverfitting:
    def _make_p(self, total_return):
        return {'total_return': total_return}

    def _make_r(self, max_drawdown):
        return {'max_drawdown': max_drawdown}

    def test_decreasing_returns_increasing_drawdowns_scores_high(self):
        tp = {'total_return': '50.0%', 'sharpe_ratio': 2.0, 'win_rate': '65.0%'}
        vp = {'total_return': '30.0%', 'sharpe_ratio': 1.2, 'win_rate': '55.0%'}
        ep = {'total_return': '5.0%', 'sharpe_ratio': 0.4, 'win_rate': '40.0%'}
        tr = {'max_drawdown': '5.0%'}
        vr = {'max_drawdown': '10.0%'}
        er = {'max_drawdown': '20.0%'}
        result = _assess_overfitting(tp, tr, vp, vr, ep, er)
        assert result['score'] >= 60
        assert result['level'] == 'high'

    def test_moderate_overfitting(self):
        tp = {'total_return': '20.0%', 'sharpe_ratio': 1.5, 'win_rate': '60.0%'}
        vp = {'total_return': '15.0%', 'sharpe_ratio': 1.2, 'win_rate': '55.0%'}
        ep = {'total_return': '10.0%', 'sharpe_ratio': 1.0, 'win_rate': '50.0%'}
        tr = {'max_drawdown': '10.0%'}
        vr = {'max_drawdown': '12.0%'}
        er = {'max_drawdown': '15.0%'}
        result = _assess_overfitting(tp, tr, vp, vr, ep, er)
        assert 10 <= result['score'] < 60
        assert result['level'] in ('low', 'medium')

    def test_no_overfitting(self):
        tp = {'total_return': '10.0%', 'sharpe_ratio': 1.0, 'win_rate': '55.0%'}
        vp = {'total_return': '10.0%', 'sharpe_ratio': 1.0, 'win_rate': '55.0%'}
        ep = {'total_return': '10.0%', 'sharpe_ratio': 1.0, 'win_rate': '55.0%'}
        tr = {'max_drawdown': '10.0%'}
        vr = {'max_drawdown': '10.0%'}
        er = {'max_drawdown': '10.0%'}
        result = _assess_overfitting(tp, tr, vp, vr, ep, er)
        assert result['score'] == 0
        assert result['level'] == 'none'


class TestGenerateDatasetReport:
    def test_basic_report_generation(self, tmp_path):
        stats = {
            'end_balance': 110000.0,
            'total_trades': 20,
            'win_trades': 12,
            'loss_trades': 8,
            'average_win': 500.0,
            'average_loss': -300.0,
            'win_loss_ratio': 1.67,
            'sharpe_ratio': 1.2,
            'annual_return': 0.15,
            'max_drawdown': 0.08,
            'max_ddpercent_duration': 5,
            'daily_std': 0.015,
            'return_drawdown_ratio': 1.88,
            'start_date': '2024-01-01',
            'end_date': '2024-06-30',
            'total_days': 120,
            'max_consecutive_win': 5,
            'max_consecutive_loss': 3,
        }
        output_dir = str(tmp_path / 'reports')
        report = generate_dataset_report(
            statistics=stats,
            dataset_name='train',
            symbol='rb888',
            initial_capital=100000.0,
            output_dir=output_dir,
            save_trades=False,
            save_equity=False,
        )
        assert report['meta']['dataset'] == 'train'
        assert report['meta']['symbol'] == 'rb888'
        assert report['meta']['initial_capital'] == 100000.0
        assert 'performance' in report
        assert 'risk' in report
        assert 'trades' in report
        assert report['performance']['total_trades'] == 20
        report_path = tmp_path / 'reports' / 'rb888_train_report.json'
        assert report_path.exists()
        with open(report_path) as f:
            saved = json.load(f)
        assert saved['meta']['dataset'] == 'train'

    def test_generate_report_with_trades_and_equity(self, tmp_path):
        stats = {
            'end_balance': 105000.0,
            'total_trades': 10,
            'win_trades': 6,
            'loss_trades': 4,
            'average_win': 400.0,
            'average_loss': -200.0,
        }
        daily_results = [
            {'datetime': '2024-01-02', 'net_pnl': 500.0, 'drawdown': 0.0,
             'trades': [{'symbol': 'rb888', 'pnl': 500.0}]},
            {'datetime': '2024-01-03', 'net_pnl': -200.0, 'drawdown': 200.0,
             'trades': [{'symbol': 'rb888', 'pnl': -200.0}]},
        ]
        output_dir = str(tmp_path / 'reports')
        report = generate_dataset_report(
            statistics=stats,
            daily_results=daily_results,
            dataset_name='val',
            symbol='rb888',
            output_dir=output_dir,
            save_trades=True,
            save_equity=True,
        )
        trades_path = tmp_path / 'reports' / 'rb888_val_trades.json'
        equity_path = tmp_path / 'reports' / 'rb888_val_equity.json'
        assert trades_path.exists()
        assert equity_path.exists()
        with open(equity_path) as f:
            equity_data = json.load(f)
        assert len(equity_data) == 2
        assert equity_data[0]['equity'] == 100500.0

    def test_generate_report_empty_stats(self, tmp_path):
        output_dir = str(tmp_path / 'reports')
        report = generate_dataset_report(
            statistics={},
            dataset_name='test',
            symbol='',
            output_dir=output_dir,
            save_trades=False,
            save_equity=False,
        )
        assert report['meta']['dataset'] == 'test'
        assert report['performance']['total_trades'] == 0


class TestFormatComparisonReport:
    def test_returns_formatted_string(self):
        comparison = {
            'metrics_table': {
                'total_return': {'train': 0.3, 'val': 0.2, 'test': 0.1},
                'annual_return': {'train': 0.4, 'val': 0.3, 'test': 0.15},
                'sharpe_ratio': {'train': 2.0, 'val': 1.5, 'test': 1.0},
                'max_drawdown': {'train': 0.1, 'val': 0.12, 'test': 0.15},
                'win_rate': {'train': 0.6, 'val': 0.55, 'test': 0.5},
                'profit_loss_ratio': {'train': 2.0, 'val': 1.8, 'test': 1.5},
                'total_trades': {'train': 100, 'val': 80, 'test': 60},
            },
            'return_degradation': {
                'message': '收益从训练集到测试集大幅下降(>20%)，强烈提示过拟合',
                'train_to_val': 10.0,
                'val_to_test': 10.0,
                'train_to_test': 20.0,
            },
            'risk_increase': {
                'message': '测试集回撤略有增加，需关注风险控制',
                'train_to_test': 5.0,
            },
            'stability_analysis': {
                'message': '策略在各数据集上表现一致，稳定性好',
                'avg_cv': 0.3,
            },
            'overfitting_assessment': {
                'score': 50,
                'level': 'medium',
                'advice': '中等过拟合风险，建议调整参数',
                'details': {
                    'return_degradation': '50.0%',
                    'drawdown_increase': '5.0%',
                    'sharpe_decline': '50.0%',
                    'winrate_decline': '16.7%',
                },
            },
        }
        result = format_comparison_report(comparison)
        assert isinstance(result, str)
        assert len(result) > 0
        assert '指标对比总览' in result
        assert '收益递减分析' in result
        assert '风险递增分析' in result
        assert '策略稳定性' in result
        assert '过拟合综合评估' in result

    def test_with_defaults(self):
        comparison = {
            'metrics_table': {},
            'return_degradation': {},
            'risk_increase': {},
            'stability_analysis': {},
            'overfitting_assessment': {},
        }
        result = format_comparison_report(comparison)
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateMergedReport:
    def _make_result(self, symbol, ret, sharpe, dd, wr, trades, of_level='none', of_score=0):
        return {
            'success': True,
            'symbol': symbol,
            'comparison': {
                'metrics_table': {
                    'total_return': {'test': ret},
                    'sharpe_ratio': {'test': sharpe},
                    'max_drawdown': {'test': dd},
                    'win_rate': {'test': wr},
                    'profit_loss_ratio': {'test': 1.5},
                    'total_trades': {'test': trades},
                },
                'overfitting_assessment': {
                    'score': of_score,
                    'level': of_level,
                },
            },
        }

    def test_empty_results(self, tmp_path):
        merged = generate_merged_report([], str(tmp_path))
        assert merged['meta']['symbol_count'] == 0
        assert merged['symbols'] == []

    def test_single_symbol(self, tmp_path):
        results = [self._make_result('DCE.m2509', 0.15, 1.5, 0.08, 0.6, 50)]
        merged = generate_merged_report(results, str(tmp_path))
        assert merged['meta']['symbol_count'] == 1
        assert merged['symbols'][0]['symbol'] == 'DCE.m2509'
        assert merged['aggregate']['total_return']['mean'] == pytest.approx(0.15)
        assert merged['aggregate']['profitable_ratio'] == 1.0

    def test_multiple_symbols(self, tmp_path):
        results = [
            self._make_result('DCE.m2509', 0.15, 1.5, 0.08, 0.6, 50),
            self._make_result('CZCE.TA509', 0.10, 1.2, 0.05, 0.55, 30),
            self._make_result('SHFE.rb2410', -0.05, -0.5, 0.15, 0.35, 20),
        ]
        merged = generate_merged_report(results, str(tmp_path))
        assert merged['meta']['symbol_count'] == 3
        agg = merged['aggregate']
        assert agg['profitable_ratio'] == pytest.approx(2 / 3)
        assert agg['total_trades']['total'] == 100

    def test_skips_failed_results(self, tmp_path):
        results = [
            self._make_result('DCE.m2509', 0.15, 1.5, 0.08, 0.6, 50),
            {'success': False, 'symbol': 'FAIL', 'error': 'no data'},
        ]
        merged = generate_merged_report(results, str(tmp_path))
        assert merged['meta']['symbol_count'] == 1
        assert 'FAIL' not in merged['meta']['symbols']

    def test_saves_json_file(self, tmp_path):
        results = [self._make_result('DCE.m2509', 0.15, 1.5, 0.08, 0.6, 50)]
        generate_merged_report(results, str(tmp_path))
        report_path = tmp_path / 'merged_report.json'
        assert report_path.exists()
        with open(report_path) as f:
            saved = json.load(f)
        assert saved['meta']['symbol_count'] == 1

    def test_ranking_by_return(self, tmp_path):
        results = [
            self._make_result('A', 0.3, 2.0, 0.05, 0.7, 100),
            self._make_result('B', 0.1, 1.0, 0.1, 0.5, 50),
            self._make_result('C', 0.2, 1.5, 0.08, 0.6, 75),
        ]
        merged = generate_merged_report(results, str(tmp_path))
        ranking = merged['ranking']['total_return']
        assert ranking[0]['symbol'] == 'A'
        assert ranking[1]['symbol'] == 'C'
        assert ranking[2]['symbol'] == 'B'

    def test_ranking_by_drawdown_ascending(self, tmp_path):
        results = [
            self._make_result('A', 0.3, 2.0, 0.05, 0.7, 100),
            self._make_result('B', 0.1, 1.0, 0.15, 0.5, 50),
            self._make_result('C', 0.2, 1.5, 0.08, 0.6, 75),
        ]
        merged = generate_merged_report(results, str(tmp_path))
        ranking = merged['ranking']['max_drawdown']
        assert ranking[0]['symbol'] == 'A'

    def test_overfitting_summary(self, tmp_path):
        results = [
            self._make_result('A', 0.3, 2.0, 0.05, 0.7, 100, 'high', 70),
            self._make_result('B', 0.1, 1.0, 0.1, 0.5, 50, 'low', 15),
            self._make_result('C', 0.2, 1.5, 0.08, 0.6, 75, 'none', 5),
        ]
        merged = generate_merged_report(results, str(tmp_path))
        ofs = merged['overfitting_summary']
        assert ofs['distribution']['high'] == 1
        assert ofs['distribution']['low'] == 1
        assert ofs['distribution']['none'] == 1
        assert 'A' in ofs['high_risk_symbols']


class TestFormatMergedReport:
    def _make_merged(self):
        return {
            'meta': {
                'symbol_count': 2,
                'symbols': ['DCE.m2509', 'CZCE.TA509'],
                'generated_at': '2024-01-01',
            },
            'symbols': [
                {
                    'symbol': 'DCE.m2509',
                    'test_metrics': {
                        'total_return': 0.15, 'sharpe_ratio': 1.5,
                        'max_drawdown': 0.08, 'win_rate': 0.6, 'total_trades': 50,
                    },
                    'overfitting_level': 'low',
                    'overfitting_score': 15,
                },
            ],
            'aggregate': {
                'total_return': {'mean': 0.15, 'median': 0.15, 'min': 0.15, 'max': 0.15},
                'sharpe_ratio': {'mean': 1.5, 'median': 1.5, 'min': 1.5, 'max': 1.5},
                'max_drawdown': {'mean': 0.08, 'median': 0.08, 'min': 0.08, 'max': 0.08},
                'win_rate': {'mean': 0.6, 'median': 0.6, 'min': 0.6, 'max': 0.6},
                'total_trades': {'total': 50, 'avg': 50, 'count': 1},
                'profitable_ratio': 1.0,
            },
            'ranking': {
                'total_return': [{'symbol': 'DCE.m2509', 'value': 0.15}],
                'sharpe_ratio': [{'symbol': 'DCE.m2509', 'value': 1.5}],
                'max_drawdown': [{'symbol': 'DCE.m2509', 'value': 0.08}],
                'win_rate': [{'symbol': 'DCE.m2509', 'value': 0.6}],
            },
            'overfitting_summary': {
                'distribution': {'high': 0, 'medium': 0, 'low': 1, 'none': 0},
                'high_risk_symbols': [],
                'total': 1,
                'high_risk_ratio': 0.0,
            },
        }

    def test_returns_non_empty_string(self):
        merged = self._make_merged()
        result = format_merged_report(merged)
        assert isinstance(result, str)
        assert len(result) > 0
        assert '多品种合并回测报告' in result
        assert 'DCE.m2509' in result

    def test_contains_key_sections(self):
        merged = self._make_merged()
        result = format_merged_report(merged)
        assert '品种关键指标' in result
        assert '整体聚合统计' in result
        assert '过拟合风险汇总' in result
        assert '各指标排名' in result