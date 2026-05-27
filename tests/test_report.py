"""report/ 报告格式化集成测试

覆盖:
    - format_single_report: 成功/失败/无曲线
    - format_summary_report: 列表/过滤/空列表
    - report 工具函数: _na_str / _get_attr
    - 公共 API 导入
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import DataManager  # noqa: E402
from data.store import DataStore  # noqa: E402
from common.constants import STATUS_SUCCESS, STATUS_FAILED  # noqa: E402
from conftest import insert_full_backtest  # noqa: E402


# ═══════════════════════════════════════════════════════════
# format_single_report
# ═══════════════════════════════════════════════════════════

class TestFormatSingleReport:
    def test_success_report_contains_key_metrics(self, temp_db_path):
        from report import format_single_report
        dm = DataManager()
        dm._init_store = lambda: None
        dm._store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(dm._store)

        text = format_single_report(dm, bt_id)
        assert '回测报告 #' in text
        assert 'DCE.m2509' in text
        assert 'ma' in text
        assert '1.0' in text
        assert 'abc1234' in text
        assert 'success' in text
        assert '2024-01-01' in text
        assert '2024-12-31' in text
        assert '100,000.00' in text
        assert '118,000.00' in text
        assert '1.35' in text
        assert '80' in text
        assert '45' in text
        assert '35' in text
        assert '120' in text
        assert '100,200.00' in text
        assert '100,100.00' in text
        assert '100,450.00' in text
        assert '多' in text
        assert '空' in text
        assert '开' in text
        assert '平' in text
        dm.close()

    def test_failed_report_shows_error(self, temp_db_path):
        from report import format_single_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        bt_id = dm._store.insert_backtest_detailed(
            symbol='DCE.bad', strategy='ma', status=STATUS_FAILED,
            error_message='数据不足无法回测', statistics={},
            engine_config={}, params={},
            start_date=None, end_date=None,
        )
        text = format_single_report(dm, bt_id)
        assert '失败' in text or 'failed' in text
        assert '数据不足无法回测' in text
        dm.close()

    def test_nonexistent_id(self, temp_db_path):
        from report import format_single_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        text = format_single_report(dm, 99999)
        assert '错误' in text or '未找到' in text
        dm.close()

    def test_no_daily_no_crash(self, temp_db_path):
        from report import format_single_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        bt_id = dm._store.insert_backtest_detailed(
            symbol='DCE.m2509', strategy='ma', status=STATUS_SUCCESS,
            error_message=None,
            statistics={'total_trades': 3, 'end_balance': 101000.0},
            engine_config={'initial_capital': 100000.0},
            params={},
            start_date='2024-01-01', end_date='2024-03-31',
        )
        text = format_single_report(dm, bt_id)
        assert '交易日数:   0 天' in text
        assert '资金曲线' not in text
        dm.close()


# ═══════════════════════════════════════════════════════════
# format_summary_report
# ═══════════════════════════════════════════════════════════

class TestFormatSummaryReport:
    def test_list_success_records(self, temp_db_path):
        from report import format_summary_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        insert_full_backtest(dm._store, symbol='DCE.m2509')
        insert_full_backtest(dm._store, symbol='DCE.rb2410')

        text = format_summary_report(dm, limit=10)
        assert '回测汇总' in text
        assert '2 条' in text
        assert 'DCE.m2509' in text
        assert 'DCE.rb2410' in text
        assert 'abc1234' in text
        assert '1.0' in text
        assert 'python main.py report --id' in text
        dm.close()

    def test_empty_list(self, temp_db_path):
        from report import format_summary_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        text = format_summary_report(dm)
        assert '未找到' in text
        dm.close()

    def test_filter_by_symbol(self, temp_db_path):
        from report import format_summary_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        insert_full_backtest(dm._store, symbol='DCE.m2509')
        insert_full_backtest(dm._store, symbol='DCE.rb2410')

        text = format_summary_report(dm, symbol='DCE.m2509')
        assert 'DCE.m2509' in text
        assert 'DCE.rb2410' not in text
        dm.close()

    def test_filter_by_strategy(self, temp_db_path):
        from report import format_summary_report
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        insert_full_backtest(dm._store, symbol='DCE.m2509', strategy='ma')
        insert_full_backtest(dm._store, symbol='DCE.rb2410', strategy='bband')

        text = format_summary_report(dm, strategy='bband')
        assert 'bband' in text
        assert '1 条' in text
        assert 'DCE.rb2410' in text
        assert 'DCE.m2509' not in text
        dm.close()


# ═══════════════════════════════════════════════════════════
# 公共 API & 工具函数
# ═══════════════════════════════════════════════════════════

class TestReportPublicAPI:
    def test_format_single_report_importable(self):
        from report import format_single_report
        assert callable(format_single_report)

    def test_format_summary_report_importable(self):
        from report import format_summary_report
        assert callable(format_summary_report)


class TestReportHelpers:
    def test_na_str_none(self):
        from report.reports import _na_str
        assert _na_str(None) == 'N/A'

    def test_na_str_value(self):
        from report.reports import _na_str
        assert _na_str('hello') == 'hello'
        assert _na_str(123) == '123'

    def test_get_attr_dict(self):
        from report.reports import _get_attr
        d = {'a': 1, 'b': 2}
        assert _get_attr(d, 'a') == 1
        assert _get_attr(d, 'c', 'default') == 'default'
        assert _get_attr(d, 'missing') is None

    def test_get_attr_object(self):
        from report.reports import _get_attr

        class Obj:
            a = 10
            b = 20
        o = Obj()
        assert _get_attr(o, 'a') == 10
        assert _get_attr(o, 'c', 99) == 99
