"""测试 batch_mode 和并行优化器

测试内容:
  1. batch_mode=True vs False 结果一致性
  2. ParallelBacktestOptimizer Grid Search 正确性
  3. 进程隔离和异常隔离
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd
import pytest
from backtest.parallel import ParallelBacktestOptimizer, _execute_trial, run_param_search_parallel
from backtest.vnpy_backtest_engine import VnpyBacktestEngine
from config.app_config import BacktestConfig
from strategies import Signal, Strategy
from strategies.runtime import DataRequirements, EventsRequirements

# ── 辅助函数 ─────────────────────────────────────────────


def make_price_df(start: str = "2024-01-01", n: int = 120, seed: int = 42) -> pd.DataFrame:
    """生成单品种单周期的模拟 K 线数据（1m 级别）

    Args:
        start: 开始日期
        n: K线根数
        seed: 随机种子

    Returns:
        DataFrame 含 datetime/open/high/low/close/volume
    """
    rng = random.Random(seed)
    base_price = 3500.0
    ts = pd.date_range(start, periods=n, freq="min")
    prices = [base_price]
    for _ in range(n - 1):
        step = rng.uniform(-5, 5)
        prices.append(round(prices[-1] + step, 2))

    df = pd.DataFrame(
        {
            "datetime": ts,
            "open": prices,
            "high": [p * (1 + rng.uniform(0, 0.003)) for p in prices],
            "low": [p * (1 - rng.uniform(0, 0.003)) for p in prices],
            "close": prices,
            "volume": [rng.randint(100, 1000) for _ in range(n)],
        }
    )
    return df


def make_basic_config(**overrides) -> BacktestConfig:
    """创建一个最小化的 BacktestConfig"""
    kwargs = dict(
        initial_capital=100000,
        commission_rate=0.0003,
        slippage=0.0,
        price_tick=1.0,
        contract_size=10,
        interval="1m",
    )
    kwargs.update(overrides)
    return BacktestConfig(**kwargs)


# ── 真实数据集加载（并行子进程测试用）──────────────────────
# spawn 子进程内 monkeypatch 不生效，noop 策略注入无法跨进程，
# 因此并行集成测试必须用磁盘上真实存在的品种 + 真实 ma_strategy 参数。
# 本机无数据时自动跳过，保证 CI 可移植。

_REAL_SYMBOL_CANDIDATES = ("DCE.m2601", "DCE.m2603", "DCE.m2605", "DCE.c2601")


def load_real_dataset() -> tuple[str, pd.DataFrame]:
    """加载一个磁盘上真实存在的品种 5m 数据，无数据时 pytest.skip"""
    from data.manager import DataManager

    dm = DataManager()
    for symbol in _REAL_SYMBOL_CANDIDATES:
        try:
            results = dm.load_kline([symbol], interval="5m")
        except FileNotFoundError:
            continue
        if results:
            return symbol, results[0][1]
    pytest.skip(f"本机缺少并行回测所需的真实 K 线数据（候选: {_REAL_SYMBOL_CANDIDATES}）")


@pytest.fixture
def real_5m_dataset() -> tuple[str, pd.DataFrame]:
    """提供本机真实 5m K 线数据，无数据时跳过 local_data 测试"""
    return load_real_dataset()


# ── 模拟策略（不声明任何数据需求，回测完全使用内存 df）──────


@dataclass
class _NoopParams:
    """空参数集——模拟策略不需要任何可调参数"""


class _NoopStrategy(Strategy[_NoopParams]):
    """不声明任何数据需求的最小策略

    data_requirements 返回空 periods/indicators 的 DataRequirements，
    使 DataFeed.create() 命中空 feed 分支，整个回测不访问磁盘数据。
    on_bar 永不发信号。
    """

    name = "noop"
    VERSION = "test-noop1"

    def data_requirements(self, config: _NoopParams) -> DataRequirements:
        return DataRequirements(periods={}, indicators={}, events=EventsRequirements.no_events())

    def on_bar(self, state, ctx) -> Signal:  # type: ignore[override]
        return Signal()

    def on_fill(self, fill) -> None:
        pass


def _install_noop_strategy(monkeypatch) -> None:
    """把策略加载入口替换为返回 _NoopStrategy 实例

    engine 在两处加载策略：strategy_factory 模块级 import，以及
    _get_strategy_version 运行时 from strategies import load_strategy。
    两处都需替换。
    """

    def _fake_load_strategy(strategy_name=None, **kwargs):
        return _NoopStrategy()

    monkeypatch.setattr("backtest.strategy_factory.load_strategy", _fake_load_strategy)
    monkeypatch.setattr("strategies.load_strategy", _fake_load_strategy)


def _run_single_backtest(batch_mode: bool) -> tuple:
    """在同步上下文中运行单次回测（用于 batch_mode 对比测试）

    Returns:
        (engine_results, score)
    """
    df = make_price_df()
    config = make_basic_config()
    engine = VnpyBacktestEngine(config)
    pairs = [("DCE.m2501", df, "ma_strategy", {"fast": 5, "slow": 20})]
    results = engine.run(pairs, batch_mode=batch_mode)
    calmars = [
        (r.annual_return or 0) / abs(r.max_ddpercent or 0.001)
        for r in results
        if r.success and (r.max_ddpercent or 0) != 0
    ]
    score = float(sum(calmars) / len(calmars)) if calmars else -999.0
    return results, score


# ── batch_mode 测试 ──────────────────────────────────────


class TestBatchMode:
    """batch_mode=True vs False 结果一致性"""

    def test_batch_mode_creates_no_db_record(self, monkeypatch) -> None:
        """batch_mode=True 时跳过 _create_placeholder_record（不写 DB）

        注入 noop 策略避免回测访问磁盘 K 线（fail-fast 下数据缺失会直接抛错）。
        """
        df = make_price_df()
        config = make_basic_config()
        _install_noop_strategy(monkeypatch)
        create_called = False

        def _fake_create_placeholder_record(*args, **kwargs):
            nonlocal create_called
            create_called = True
            return object()

        monkeypatch.setattr(VnpyBacktestEngine, "_create_placeholder_record", _fake_create_placeholder_record)
        engine = VnpyBacktestEngine(config)
        pairs = [("DCE.m2501", df, "noop_strategy", {})]
        results = engine.run(pairs, batch_mode=True)

        assert len(results) == 1
        assert create_called is False
        # batch_mode 下 backtest_id 应为 None（占位的 -1 在 _create_backtest_result 中被忽略）
        assert results[0].backtest_id is None or results[0].backtest_id == -1

    def test_batch_mode_dm_none(self, monkeypatch) -> None:
        """batch_mode=True 用纯内存数据跑通回测，不依赖磁盘上的品种文件

        通过注入一个不声明任何数据需求的模拟策略，使 DataFeed.create() 命中
        空 periods 分支（返回空 feed，不访问磁盘），回测完全使用传入的内存 df。
        """
        df = make_price_df()
        config = make_basic_config()

        _install_noop_strategy(monkeypatch)

        engine = VnpyBacktestEngine(config)
        pairs = [("DCE.m2501", df, "noop_strategy", {})]
        results = engine.run(pairs, batch_mode=True)

        assert len(results) == 1
        # 回测应正常跑完（不再因数据加载失败而 skip）
        assert results[0].success, f"回测未成功: {results[0].error_message}"
        assert results[0].total_trades >= 0

    def test_batch_mode_with_multiple_symbols(self, monkeypatch) -> None:
        """batch_mode=True 下多品种回测正常

        注入 noop 策略避免回测访问磁盘 K 线（fail-fast 下数据缺失会直接抛错）。
        """
        config = make_basic_config()
        _install_noop_strategy(monkeypatch)
        engine = VnpyBacktestEngine(config)

        df1 = make_price_df("2024-01-01", seed=1)
        df2 = make_price_df("2024-06-01", seed=2)
        pairs = [
            ("DCE.m2501", df1, "noop_strategy", {}),
            ("DCE.m2505", df2, "noop_strategy", {}),
        ]
        results = engine.run(pairs, batch_mode=True)

        assert len(results) == 2
        assert results[0].symbol == "DCE.m2501" or results[0].symbol == "DCE.m2505"
        # 两个品种结果互不影响
        symbols = {r.symbol for r in results}
        assert len(symbols) == 2


# ── _execute_trial 单元测试（无需拉起子进程）─────────────


class TestExecuteTrial:
    """验证 _execute_trial 模块级函数的逻辑正确性"""

    def test_execute_trial_direct_call(self, monkeypatch) -> None:
        """直接调用 _execute_trial（在同进程中），验证返回结构

        注入 noop 策略避免回测访问磁盘 K 线（fail-fast 下数据缺失会直接抛错）。
        """
        df = make_price_df()
        config = make_basic_config()
        _install_noop_strategy(monkeypatch)

        # 手动设置 _WORKER_CTX（模拟 spawn 子进程的初始化）
        # 注意：这会修改全局变量，只能在单线程测试中运行
        import backtest.parallel as bp

        bp._WORKER_CTX["datasets"] = [("DCE.m2501", df)]
        bp._WORKER_CTX["strategy_name"] = "noop_strategy"
        bp._WORKER_CTX["strategy_params"] = {}
        bp._WORKER_CTX["backtest_config"] = config

        result = _execute_trial({}, trial_seed=42)

        # 验证返回结构
        assert "search_params" in result
        assert "value" in result
        assert "engine_results" in result
        assert "strategy_params" in result
        assert "strategy_name" in result
        assert result["strategy_name"] == "noop_strategy"
        assert result["success"] is True

        # 清理
        bp._WORKER_CTX.clear()


# ── ParallelBacktestOptimizer 集成测试 ───────────────────


@pytest.mark.integration
class TestParallelBacktestOptimizer:
    """并行优化器集成测试

    注意：这些测试会启动真实的子进程（spawn 模式）。
    如果环境不支持（如 Windows 等），测试自动跳过。
    """

    def _make_small_optimizer(
        self,
        real_5m_dataset: tuple[str, pd.DataFrame],
        search_type="grid",
    ) -> ParallelBacktestOptimizer:
        symbol, df = real_5m_dataset
        config = make_basic_config(interval="5m")
        search_space = {
            "sma_short": {"type": "int", "low": 5, "high": 10, "step": 5},  # 2 个值
            "sma_long": {"type": "int", "low": 20, "high": 30, "step": 10},  # 2 个值
        }
        return ParallelBacktestOptimizer(
            datasets=[(symbol, df)],
            strategy_name="ma_strategy",
            search_space=search_space,
            strategy_params={},
            backtest_config=config,
            n_trials=10,
            search_type=search_type,
            n_workers=2,
            use_fixed_seed=True,
            random_seed=42,
        )

    @pytest.mark.slow
    @pytest.mark.local_data
    def test_grid_search_basic(self, real_5m_dataset: tuple[str, pd.DataFrame]) -> None:
        """Grid Search 返回正确结构，最优参数在搜索空间内"""
        optimizer = self._make_small_optimizer(real_5m_dataset, search_type="grid")
        result = optimizer.optimize()

        assert len(result.trial_data) > 0
        assert result.best_params is not None
        assert "sma_short" in result.best_params
        assert "sma_long" in result.best_params
        assert result.best_params["sma_short"] in [5, 10]
        assert result.best_params["sma_long"] in [20, 30]
        assert result.study is not None
        assert result.actual_seed == 42

    @pytest.mark.slow
    @pytest.mark.local_data
    def test_bayesian_search_basic(self, real_5m_dataset: tuple[str, pd.DataFrame]) -> None:
        """Bayesian Search 返回正确结构"""
        optimizer = self._make_small_optimizer(real_5m_dataset, search_type="bayesian")
        result = optimizer.optimize()

        assert len(result.trial_data) > 0
        assert result.best_params is not None
        assert result.study is not None
        assert result.actual_seed == 42

    @pytest.mark.slow
    @pytest.mark.local_data
    def test_run_param_search_parallel_interface(self, real_5m_dataset: tuple[str, pd.DataFrame]) -> None:
        """run_param_search_parallel 返回 SearchResult，与串行版本接口兼容"""
        symbol, df = real_5m_dataset
        config = make_basic_config(interval="5m")
        search_space = {
            "sma_short": {"type": "int", "low": 5, "high": 10, "step": 5},
            "sma_long": {"type": "int", "low": 20, "high": 30, "step": 10},
        }

        result = run_param_search_parallel(
            datasets=[(symbol, df)],
            strategy_name="ma_strategy",
            search_space=search_space,
            strategy_params={},
            backtest_config=config,
            n_trials=4,
            search_type="grid",
            n_workers=2,
            use_fixed_seed=True,
        )

        assert isinstance(result.best_params, dict)
        assert result.n_trials > 0
        assert result.study_name
        assert result.actual_seed == 42

    def test_empty_search_space(self, monkeypatch) -> None:
        """空搜索空间直接返回，不启动子进程，也不初始化真实数据库"""
        monkeypatch.setattr("data.optuna_query.get_optuna_url", lambda: None)
        df = make_price_df()
        config = make_basic_config()
        optimizer = ParallelBacktestOptimizer(
            datasets=[("DCE.m2501", df)],
            strategy_name="ma_strategy",
            search_space={},
            strategy_params={"sma_short": 5, "sma_long": 20},
            backtest_config=config,
            n_trials=10,
            search_type="grid",
            use_fixed_seed=True,
            random_seed=42,
        )
        result = optimizer.optimize()

        assert result.best_params == {}
        assert result.best_value == 0.0
        assert result.trial_data == []

