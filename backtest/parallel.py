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

import atexit
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

# 子进程日志 sink id，供 _cleanup_worker 退出时移除，避免文件句柄泄漏。
_WORKER_LOGGER_ID: int | None = None


def _cleanup_worker() -> None:
    """子进程退出时清理：移除 _init_worker 注册的日志 sink，关闭文件句柄。

    通过 atexit 注册，确保进程正常退出或被进程池回收时都能释放资源。
    清理失败不应阻断进程退出，因此吞掉异常。
    """
    global _WORKER_LOGGER_ID
    if _WORKER_LOGGER_ID is None:
        return
    try:
        logger.remove(_WORKER_LOGGER_ID)
    except Exception:
        # sink 已被移除或 loguru 内部状态异常时忽略
        pass
    finally:
        _WORKER_LOGGER_ID = None


def _init_worker(
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    strategy_params: dict[str, Any],
    backtest_config: BacktestConfig,
    run_id: int,
) -> None:
    """子进程初始化：每个 worker 启动时执行一次"""
    global _WORKER_CTX, _WORKER_LOGGER_ID
    _WORKER_CTX["datasets"] = datasets
    _WORKER_CTX["strategy_name"] = strategy_name
    _WORKER_CTX["strategy_params"] = strategy_params
    _WORKER_CTX["backtest_config"] = backtest_config

    # ── 子进程独立日志文件 ──────────────────────────
    from report.output_paths import workers_dir

    logs_dir = str(workers_dir(run_id))
    os.makedirs(logs_dir, exist_ok=True)
    pid = os.getpid()
    _WORKER_LOGGER_ID = logger.add(
        os.path.join(logs_dir, f"worker_{pid}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )
    # 注册退出清理，确保日志 sink 文件句柄被释放
    atexit.register(_cleanup_worker)
    logger.debug(f"[worker {pid}] 初始化完成")


def _execute_trial(params: dict[str, Any], trial_seed: int = 0) -> dict[str, Any]:
    """在子进程中执行单个 trial（模块顶层函数，spawn 兼容 pickle）

    单个 trial 的异常被隔离在此函数内：捕获后返回 success=False 的最差分结果，
    避免一个 trial 崩溃导致整批 future.result() 抛错、丢失已完成的其他 trial。

    Args:
        params: 当前 trial 的搜索参数（含分布采样值）
        trial_seed: trial 级别随机种子

    Returns:
        dict: {search_params, value, engine_results, strategy_params, strategy_name, success[, error]}
    """
    ctx = _WORKER_CTX

    random.seed(trial_seed)

    merged_params = {**ctx["strategy_params"], **params}
    try:
        from .vnpy_backtest_engine import VnpyBacktestEngine

        engine = VnpyBacktestEngine(ctx["backtest_config"])
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
            "success": True,
        }
    except Exception as exc:
        logger.error("[worker {}] trial 执行失败 params={}: {}", os.getpid(), params, exc)
        return {
            "search_params": params,
            "value": -999.0,
            "engine_results": [],
            "strategy_params": merged_params,
            "strategy_name": ctx["strategy_name"],
            "success": False,
            "error": str(exc),
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

    def optimize(self) -> OptunaResult:
        """执行并行优化

        Returns:
            OptunaResult 包含最优参数、全部 trial 数据、study 实例
        """
        from data.optuna_query import get_optuna_url

        from .optuna_study import create_grid_space, get_study

        result = OptunaResult()

        # ── 创建 study ───────────────────────────────
        storage = get_optuna_url()
        logger.info("Optuna study 存储: {} ({})", self._study_name, storage)

        # ── 选择 sampler ─────────────────────────────
        sampler: optuna.samplers.BaseSampler
        total_trials: int

        if self._search_type == "grid":
            grid_space = create_grid_space(self._search_space)
            sampler = optuna.samplers.GridSampler(grid_space, seed=self._actual_seed)
            n_combinations = 0 if not grid_space else 1
            for values in grid_space.values():
                n_combinations *= len(values)
            total_trials = min(self._n_trials, n_combinations) if n_combinations > 0 else 0
            logger.info("Grid Search: 搜索空间={}, 计划试验={}", grid_space, total_trials)
        else:
            sampler = optuna.samplers.TPESampler(seed=self._actual_seed)  # type: ignore[assignment]
            total_trials = self._n_trials

        study = get_study(
            study_name=self._study_name,
            storage=storage,
            sampler=sampler,
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

        trial_data: list[dict[str, Any]] = []
        interrupted = False
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
            try:
                if self._search_type == "grid":
                    self._execute_grid(pool, study, total_trials, trial_data)
                else:
                    self._execute_bayesian(pool, study, total_trials, trial_data)
            except KeyboardInterrupt:
                # 用户中断：取消未开始的任务并尽快回收子进程，保留已完成结果
                interrupted = True
                logger.warning("收到中断信号，正在停止并行优化（已完成 {} 个 trial）", len(trial_data))
                pool.shutdown(wait=False, cancel_futures=True)

        # 中断或正常完成都尽量构建结果（study 可能无完成 trial）
        try:
            result.best_params = study.best_params
            result.best_value = study.best_value or 0.0
        except (ValueError, RuntimeError):
            # 无任何完成的 trial 时 best_params/best_value 会抛错
            result.best_params = {}
            result.best_value = 0.0
        result.trial_data = trial_data
        result.study = study
        result.actual_seed = self._actual_seed

        if interrupted:
            logger.info(
                "并行优化被中断: 已完成 {} 个 trial, best_value={:.4f} study={}",
                len(trial_data),
                result.best_value,
                self._study_name,
            )
            return result

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
        trial_data: list[dict[str, Any]],
    ) -> None:
        """Grid Search: study.ask(全部) → pool.submit 全并行 → study.tell(全部)

        GridSampler 已注册网格空间，study.ask() 自动返回下一组组合参数。
        结果实时追加到外部传入的 trial_data，确保中断时已完成结果不丢失。
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

    def _execute_bayesian(
        self,
        pool: ProcessPoolExecutor,
        study: optuna.Study,
        n_trials: int,
        trial_data: list[dict[str, Any]],
    ) -> None:
        """Bayesian Search: 循环 study.ask(batch) → submit → tell

        通过 fixed_distributions 向 TPESampler 注册搜索空间，
        确保 trial.params 包含真实采样值而非空 dict。
        结果实时追加到外部传入的 trial_data，确保中断时已完成结果不丢失。
        """
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
    study_name: str = "",
    random_seed: int = 42,
    use_fixed_seed: bool = False,
) -> SearchResult:
    """执行并行参数搜索（Grid 全并行 / Bayesian 分批并行）

    Optuna 数据库路径由 data 层管理（get_optuna_url），调用方无需关心。

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
        study_name=study_name,
        random_seed=random_seed,
        use_fixed_seed=use_fixed_seed,
    )
    from .optuna_study import optuna_result_to_search_result

    opt_result = optimizer.optimize()

    return optuna_result_to_search_result(opt_result, optimizer.study_name)
