"""基于 multiprocessing 的并行参数优化器

使用 ProcessPoolExecutor 实现进程级隔离，绕过 vnpy 引擎非线程安全限制。
Grid Search 全并行，Bayesian Search 分批并行。

设计:
  - 子进程通过 spawn 模式启动，vnpy 引擎完全隔离
  - 数据通过 initializer 一次传入子进程全局变量，避免重复 pickle 大 DataFrame
  - 子进程 batch_mode=True 不写 DB，结果返回到主进程统一入库
  - 使用 Optuna ask/tell API 控制采样和反馈

调用链路:
  CLI → run_param_search_parallel → ParallelBacktestOptimizer.optimize()
       → ProcessPoolExecutor.map/_execute_trial
       → VnpyBacktestEngine().run(pairs, batch_mode=True)
"""

from __future__ import annotations

import multiprocessing as mp
import os
import random
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from datetime import datetime
from typing import Any, cast

import optuna
import optuna.distributions
import pandas as pd
from loguru import logger
from tqdm import tqdm

from config.app_config import BacktestConfig

from .optimizer import OptunaResult, SearchResult

# ── 子进程全局变量（通过 _init_worker initializer 设置）──
# spawn 模式下每个子进程独立 import 此模块，各自拥有一份副本，
# 不存在多进程共享冲突。
_WORKER_CTX: dict[str, Any] = {}


def _init_worker(
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    strategy_params: dict[str, Any],
    backtest_config: BacktestConfig,
    run_id: int,
) -> None:
    """子进程初始化：每个 worker 启动时执行一次

    1. 初始化全局上下文
    2. 预构造 DataFeed 写入运行时缓存，让 Bridge.on_init
       调 DataFeed.create() 时命中的内存缓存直接返回，避免重复构建。
    """
    global _WORKER_CTX
    _WORKER_CTX["datasets"] = datasets
    _WORKER_CTX["strategy_name"] = strategy_name
    _WORKER_CTX["strategy_params"] = strategy_params
    _WORKER_CTX["backtest_config"] = backtest_config

    # ── 子进程独立日志文件 ──────────────────────────
    from report.output_paths import workers_dir

    logs_dir = str(workers_dir(run_id))
    os.makedirs(logs_dir, exist_ok=True)
    pid = os.getpid()
    logger.add(
        os.path.join(logs_dir, f"worker_{pid}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )
    logger.debug(f"[worker {pid}] 初始化完成")

    # ── 预构造 DataFeed 写入运行时缓存 ──
    # 使用 load_strategy_and_config 获取策略专属配置类型，
    # 构造 DataFeed 后写入 set_cached_feed，后续 trial 的
    # Bridge.on_init → DataFeed.create() 命中缓存直接返回。
    from strategies.runtime import set_cached_feed
    from strategies.runtime.data_feed import DataFeed, _source_date_range

    from .strategy_factory import load_strategy_and_config

    strategy_cls, config = load_strategy_and_config(strategy_name, strategy_params)
    reqs = strategy_cls().data_requirements(config)

    if reqs is not None and reqs.periods:
        for symbol, df in datasets:
            feed = DataFeed(symbol=symbol)
            feed.apply_requirements(reqs)

            feed_df = df.copy()
            if "datetime" in feed_df.columns:
                feed_df = feed_df.set_index("datetime")
            feed.feed_history_df(feed_df)
            feed.calculate_all()

            src_range = _source_date_range(feed_df)
            if src_range is not None:
                set_cached_feed(symbol, feed, src_range[0], src_range[1])

        logger.debug(f"[worker {pid}] DataFeed 缓存预填完成: {len(datasets)} 品种")


def _execute_trial(params: dict[str, Any], trial_seed: int = 0) -> dict[str, Any]:
    """在子进程中执行单个 trial（模块顶层函数，spawn 兼容 pickle）

    Args:
        params: 当前 trial 的搜索参数（含分布采样值）
        trial_seed: trial 级别随机种子

    Returns:
        dict: {search_params, value, engine_results, strategy_params, strategy_name}
    """
    ctx = _WORKER_CTX

    random.seed(trial_seed)

    from .vnpy_backtest_engine import VnpyBacktestEngine

    engine = VnpyBacktestEngine(ctx["backtest_config"])
    merged_params = {**ctx["strategy_params"], **params}
    pairs = [(sym, df, ctx["strategy_name"], merged_params) for sym, df in ctx["datasets"]]
    engine_results = engine.run(pairs, batch_mode=True)

    # Calmar 比率均值（与现有 OptunaOptimizer.objective 保持一致）
    calmars = [
        (r.annual_return or 0) / abs(r.max_ddpercent or 0.001)
        for r in engine_results
        if r.success and (r.max_ddpercent or 0) != 0
    ]
    score = float(sum(calmars) / len(calmars)) if calmars else -999.0

    return {
        "search_params": params,
        "value": score,
        "engine_results": engine_results,
        "strategy_params": merged_params,
        "strategy_name": ctx["strategy_name"],
    }


def _build_fixed_distributions(
    search_space: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """将 search_space 配置转换为 Optuna fixed_distributions 格式

    用于 study.ask(fixed_distributions=...)，确保 TPESampler 有分布可采样。
    """
    distributions: dict[str, Any] = {}
    for name, spec in search_space.items():
        stype = spec.get("type", "int")
        if stype == "int":
            distributions[name] = optuna.distributions.IntDistribution(
                int(spec["low"]),
                int(spec["high"]),
                step=int(spec.get("step", 1)),
            )
        elif stype == "float":
            step = float(spec.get("step", 0.01)) if spec.get("step") else None
            distributions[name] = optuna.distributions.FloatDistribution(
                float(spec["low"]),
                float(spec["high"]),
                step=step,
            )
        elif stype == "categorical":
            distributions[name] = optuna.distributions.CategoricalDistribution(spec.get("choices", []))
    return distributions


class ParallelBacktestOptimizer:
    """基于 ProcessPoolExecutor 的并行参数优化器

    进程级隔离，解决 vnpy BacktestingEngine 非线程安全的问题。
    使用 Optuna ask/tell API 实现 Grid Search 全并行和 Bayesian Search 分批并行。

    Grid Search:
        study.ask(全部组合) → pool.map 全并行 → study.tell(全部一次性)

    Bayesian Search:
        循环: study.ask(batch_size, fixed_distributions) → pool.submit 并行 → study.tell(batch)
    """

    def __init__(
        self,
        datasets: list[tuple[str, pd.DataFrame]],
        strategy_name: str,
        search_space: dict[str, dict[str, Any]],
        strategy_params: dict[str, Any] | None = None,
        backtest_config: BacktestConfig | None = None,
        n_trials: int = 50,
        search_type: str = "bayesian",
        n_workers: int | None = None,
        batch_size: int | None = None,
        study_db_path: str = "",
        study_name: str = "",
        run_id: int = 0,
        random_seed: int = 42,
        use_fixed_seed: bool = False,
    ) -> None:
        self._datasets = datasets
        self._strategy_name = strategy_name
        self._search_space = search_space
        self._strategy_params = strategy_params or {}
        self._backtest_config = backtest_config
        self._n_trials = n_trials
        self._search_type = search_type
        self._n_workers = n_workers or os.cpu_count() or 4
        self._batch_size = batch_size or self._n_workers
        self._study_db_path = study_db_path
        self._use_fixed_seed = use_fixed_seed
        self._run_id = run_id

        if use_fixed_seed:
            self._actual_seed = random_seed
        else:
            self._actual_seed = random.randint(1, 999999)

        if study_name:
            self._study_name = study_name
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._study_name = f"{strategy_name}_{ts}"

        # 预计算 search_space 的 fixed_distributions
        self._fixed_distributions = _build_fixed_distributions(search_space)

    def _create_grid_space(self) -> dict[str, list[Any]]:
        """将 search_space 转换为 {"param": [values, ...]} 格式"""
        grid: dict[str, list[Any]] = {}
        for name, config in self._search_space.items():
            ptype = config.get("type", "int")
            if ptype == "categorical":
                grid[name] = list(config.get("choices", []))
            else:
                low = config.get("low", 0)
                high = config.get("high", 10)
                step = config.get("step", 1)
                values: list[Any] = []
                current = low
                while current <= high:
                    values.append(current)
                    current += step  # type: ignore[operator]
                grid[name] = values
        return grid

    def optimize(self) -> OptunaResult:
        """执行并行优化

        Returns:
            OptunaResult 包含最优参数、全部 trial 数据、study 实例
        """
        result = OptunaResult()

        # ── 创建 study ───────────────────────────────
        storage: str | None = None
        if self._study_db_path:
            if self._study_db_path.startswith("sqlite:///"):
                storage = self._study_db_path
            else:
                db_path = os.path.abspath(self._study_db_path)
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                storage = f"sqlite:///{db_path}"
            logger.info("Optuna study 存储: {} ({})", self._study_name, storage)

        # ── 选择 sampler ─────────────────────────────
        sampler: optuna.samplers.BaseSampler
        total_trials: int

        if self._search_type == "grid":
            grid_space = self._create_grid_space()
            sampler = optuna.samplers.GridSampler(grid_space, seed=self._actual_seed)
            n_combinations = 0 if not grid_space else 1
            for values in grid_space.values():
                n_combinations *= len(values)
            total_trials = min(self._n_trials, n_combinations) if n_combinations > 0 else 0
            logger.info("Grid Search: 搜索空间={}, 计划试验={}", grid_space, total_trials)
        else:
            sampler = optuna.samplers.TPESampler(seed=self._actual_seed)  # type: ignore[assignment]
            total_trials = self._n_trials

        study = optuna.create_study(
            study_name=self._study_name,
            direction="maximize",
            storage=storage,
            sampler=sampler,
            load_if_exists=True,
        )

        if total_trials == 0:
            logger.warning("无 trial 可执行")
            result.best_params = {}
            result.best_value = 0.0
            result.trial_data = []
            result.study = study
            result.actual_seed = self._actual_seed
            return result

        # ── 启动进程池并执行 ─────────────────────────
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        with ProcessPoolExecutor(
            max_workers=self._n_workers,
            mp_context=mp.get_context("spawn"),
            initializer=cast(Any, _init_worker),
            initargs=cast(
                Any,
                (
                    self._datasets,
                    self._strategy_name,
                    self._strategy_params,
                    self._backtest_config,
                    self._run_id,
                ),
            ),
        ) as pool:
            if self._search_type == "grid":
                trial_data = self._execute_grid(pool, study, total_trials)
            else:
                trial_data = self._execute_bayesian(pool, study, total_trials)

        result.best_params = study.best_params
        result.best_value = study.best_value or 0.0
        result.trial_data = trial_data
        result.study = study
        result.actual_seed = self._actual_seed

        logger.info(
            "并行优化完成: best_value={:.4f} best_params={} study={} seed={} workers={}",
            result.best_value,
            result.best_params,
            self._study_name,
            self._actual_seed,
            self._n_workers,
        )
        return result

    def _execute_grid(
        self,
        pool: ProcessPoolExecutor,
        study: optuna.Study,
        n_trials: int,
    ) -> list[dict[str, Any]]:
        """Grid Search: study.ask(全部) → pool.submit 全并行 → study.tell(全部)

        GridSampler 已注册网格空间，study.ask() 自动返回下一组组合参数。
        """
        distributions = _build_fixed_distributions(self._search_space)
        trial_objects: list[optuna.trial.Trial] = []
        for _ in range(n_trials):
            trial_objects.append(study.ask(fixed_distributions=distributions))

        future_to_trial: dict[Future[Any], optuna.trial.Trial] = {}
        for i, trial in enumerate(trial_objects):
            seed = self._actual_seed + i if self._use_fixed_seed else random.randint(1, 999999)
            future = pool.submit(_execute_trial, trial.params, seed)
            future_to_trial[future] = trial

        trial_data: list[dict[str, Any]] = []
        with tqdm(total=n_trials, desc="Grid Search") as pbar:
            for future in as_completed(future_to_trial):
                outcome = future.result()
                trial = future_to_trial[future]
                try:
                    study.tell(trial, outcome["value"])
                except RuntimeError as exc:
                    if "Study.stop" not in str(exc):
                        raise
                trial_data.append(outcome)
                pbar.update(1)

        return trial_data

    def _execute_bayesian(
        self,
        pool: ProcessPoolExecutor,
        study: optuna.Study,
        n_trials: int,
    ) -> list[dict[str, Any]]:
        """Bayesian Search: 循环 study.ask(batch) → submit → tell

        通过 fixed_distributions 向 TPESampler 注册搜索空间，
        确保 trial.params 包含真实采样值而非空 dict。
        """
        trial_data: list[dict[str, Any]] = []
        remaining = n_trials
        trial_idx = 0

        with tqdm(total=n_trials, desc="Bayesian Search") as pbar:
            while remaining > 0:
                bs = min(self._batch_size, remaining)
                batch_trials = [study.ask(fixed_distributions=self._fixed_distributions) for _ in range(bs)]

                future_to_trial: dict[Future[Any], optuna.trial.Trial] = {}
                for i, trial in enumerate(batch_trials):
                    seed = self._actual_seed + trial_idx + i if self._use_fixed_seed else random.randint(1, 999999)
                    future = pool.submit(_execute_trial, trial.params, seed)
                    future_to_trial[future] = trial

                for future in as_completed(future_to_trial):
                    outcome = future.result()
                    trial = future_to_trial[future]
                    study.tell(trial, outcome["value"])
                    trial_data.append(outcome)
                    pbar.update(1)

                trial_idx += bs
                remaining -= bs

        return trial_data

    @property
    def study_name(self) -> str:
        return self._study_name


def run_param_search_parallel(
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    search_space: dict[str, dict[str, Any]],
    strategy_params: dict[str, Any],
    backtest_config: BacktestConfig,
    run_id: int = 0,
    n_trials: int = 50,
    search_type: str = "bayesian",
    n_workers: int | None = None,
    batch_size: int | None = None,
    study_db_path: str = "",
    study_name: str = "",
    random_seed: int = 42,
    use_fixed_seed: bool = False,
) -> SearchResult:
    """执行并行参数搜索（Grid 全并行 / Bayesian 分批并行）

    Args:
        datasets: [(symbol, DataFrame), ...]
        strategy_name: 策略名称
        search_space: 搜索空间定义
        strategy_params: 策略默认参数
        backtest_config: 回测配置（通过 spawn pickle 传给子进程，无问题）
        run_id: 运行 ID，用于 worker 日志目录（r{run_id}/workers/）
        n_trials: 最大试验次数
        search_type: "grid" 或 "bayesian"
        n_workers: 并行进程数（默认 os.cpu_count()）
        batch_size: Bayesian 每批并行数（默认 n_workers）
        study_db_path: Optuna study 存储路径
        study_name: 自定义 study 名称
        random_seed: 随机种子
        use_fixed_seed: 是否使用固定随机种子

    Returns:
        SearchResult
    """
    optimizer = ParallelBacktestOptimizer(
        datasets=datasets,
        strategy_name=strategy_name,
        search_space=search_space,
        strategy_params=strategy_params,
        backtest_config=backtest_config,
        run_id=run_id,
        n_trials=n_trials,
        search_type=search_type,
        n_workers=n_workers,
        batch_size=batch_size,
        study_db_path=study_db_path,
        study_name=study_name,
        random_seed=random_seed,
        use_fixed_seed=use_fixed_seed,
    )
    opt_result = optimizer.optimize()

    return SearchResult(
        best_params=opt_result.best_params,
        best_value=opt_result.best_value,
        n_trials=len(opt_result.trial_data),
        study_name=optimizer.study_name,
        trial_data=opt_result.trial_data,
        actual_seed=opt_result.actual_seed,
    )
