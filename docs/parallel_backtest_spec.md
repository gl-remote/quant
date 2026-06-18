# ParallelBacktestOptimizer 并行回测方案

## 1. 目标

在**不修改现有串行路径**的前提下，新增基于 `multiprocessing.ProcessPoolExecutor` 的并行优化器，让 Grid Search 和 Bayesian Search 都能利用多核加速，同时解决 vnpy 引擎非线程安全的问题。

## 2. 核心设计

### 2.1 隔离策略：进程级隔离

每个 worker 子进程拥有独立的：
- Python 解释器 + 内存空间（vnpy 全局状态不冲突）
- vnpy `BacktestingEngine` 实例
- 数据 DataFrame（通过 `initializer` 一次传入，全局变量持有）
- **不写数据库**（结果返回主进程统一入库）

### 2.2 并行策略：Optuna ask/tell API

```
Grid Search:   ask(全部组合) → pool.map → tell(全部)   # 一次全并行
Bayesian:      ask(batch_size=P) → pool.map → tell(batch) → 循环  # 分批并行
```

- Grid Search 一次生成全部参数组合，`pool.map` 全并行，最后一次性 `tell()`
- Bayesian Search 每批 `ask(batch_size=P)` → 并行执行 → 批量 `tell()` → 循环
- `batch_size` 默认 = `min(n_workers, remaining_trials)`，Bayesian 至少需要初始 10-20 个随机 trial 预热 TPE

### 2.3 对比串行（现状） vs ask/tell 并行

| | 串行 optimize(n_jobs=1) | ask/tell + Pool |
|---|---|---|
| Grid | 一个接一个跑 | 全部同时跑 |
| Bayesian | 下一组参数依赖上一组结果(suggest) | TPE 更新延迟一个 batch，收敛性基本无影响 |
| 线程安全 | 安全但慢 | 进程隔离，安全且快 |
| 进度 | study.optimize 自带 | 需要 tqdm + imap_unordered |

## 3. 改动文件清单

### 3.1 `backtest/vnpy_backtest_engine.py` — 新增 `batch_mode`

**`VnpyBacktestEngine.__init__` 不动**

`dm` 参数保持 `DataManager` 必传（现有关调用方不变）。子进程中不会传 `dm`，但可以通过 `dm: DataManager | None = None` 兼容——但更好的做法是：

- `batch_mode` 只在 `_run_backtest` 层级控制，不涉及 `__init__`
- 子进程不传 `dm` 也没问题，因为 `batch_mode=True` 时会跳过 `_create_placeholder_record`
- DataManager 内部持有的 datafeed cache 对子进程无意义——子进程的数据通过 `initializer` 传入

**改动 1：`_run_backtest` 新增 `batch_mode` 参数**（core change）

```python
def _run_backtest(self, df, symbol, strategy_names, strategy_params_list, batch_mode=False):
    # ...
    for strategy_name, strategy_params in zip(...):
        if batch_mode:
            bt_id = -1  # 占位，跳过 _create_placeholder_record
        else:
            bt_placeholder = self._create_placeholder_record(...)
            bt_id = bt_placeholder.id
        # 其余逻辑不变
```

**改动 2：`run()` 透传 `batch_mode`**

```python
def run(self, pairs, batch_mode=False) -> list[BacktestResult]:
    # ...
    batch_results = self._run_backtest(df, symbol, strategy_names, strategy_params_list, batch_mode=batch_mode)
    # ...
```

子进程调用方式：
```python
# 子进程中：不传 dm
engine = VnpyBacktestEngine(backtest_config)  # TypeError: missing required arg
# 改为:
engine = VnpyBacktestEngine.__new__(VnpyBacktestEngine)  # 不调 __init__
# 或者 __init__ 兼容 dm=None。最简单：直接支持 dm=None
```

实际上更简洁的做法是**让 `__init__` 兼容 `dm=None`**，因为子进程中只用到 engine 的 config 参数（capital/commission/slippage 等），`self._dm` 只在 `_create_placeholder_record` 中用到，而 `batch_mode=True` 会跳过它：

```python
def __init__(self, backtest_config: BacktestConfig, dm: DataManager | None = None) -> None:
    self._dm = dm
    # ... 参数校验和 config 提取不变
```

**改动 2：新增 `batch_mode` 参数**

`run()` 方法新增 `batch_mode: bool = False` 参数：

```python
def run(self, pairs, batch_mode=False) -> list[BacktestResult]:
```

**改动 3：`_run_backtest` 中跳过 DB 写入**

```python
def _run_backtest(self, df, symbol, strategy_names, strategy_params_list, batch_mode=False):
    if batch_mode:
        bt_id = -1  # 占位，跳过 _create_placeholder_record
    else:
        bt_placeholder = self._create_placeholder_record(...)
        bt_id = bt_placeholder.id
    # 其余逻辑不变
```

> **为什么只传 `bt_id=-1`？**
> 子进程不写 DB，`bt_id` 只作为 vnpy 引擎初始化时的参数注入（用于策略 Bridge 的 backtest_id 上下文）。子进程返回的结果中 `backtest_id=None`，主进程 collect 后 `dm.insert_backtest()` 会自动分配真实 id。

### 3.2 `backtest/parallel.py` — 新增文件

核心并行优化器实现。

#### 模块级全局变量 + worker initializer

```python
"""子进程全局变量（由 initializer 设置）"""
_WORKER_CTX = {
    "datasets": [],          # list[tuple[str, pd.DataFrame]]
    "strategy_name": "",
    "strategy_params": {},
    "config": None,          # BacktestConfig
    "search_space": {},
}

def _init_worker(datasets, strategy_name, strategy_params,
                  backtest_config, search_space, worker_id):
    """每个子进程初始化时执行一次（spawn 模式）"""
    global _WORKER_CTX
    _WORKER_CTX["datasets"] = datasets
    _WORKER_CTX["strategy_name"] = strategy_name
    _WORKER_CTX["strategy_params"] = strategy_params
    _WORKER_CTX["config"] = backtest_config
    _WORKER_CTX["search_space"] = search_space

    # 子进程独立日志文件（可选）
    import logging
    logging.getLogger().setLevel(logging.WARNING)
```

#### 模块级 trial 执行函数（可 pickle）

```python
def _execute_trial(params: dict) -> dict:
    """在子进程中执行单个 trial（模块顶层函数，spawn 兼容）"""
    from backtest.vnpy_backtest_engine import VnpyBacktestEngine

    ctx = _WORKER_CTX
    engine = VnpyBacktestEngine(ctx["config"], dm=None)

    merged_params = {**ctx["strategy_params"], **params}
    pairs = [(sym, df, ctx["strategy_name"], merged_params)
             for sym, df in ctx["datasets"]]
    engine_results = engine.run(pairs, batch_mode=True)

    # 计算 Calmar 均值（与现有 objective 一致）
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
```

#### ParallelBacktestOptimizer 类

```python
class ParallelBacktestOptimizer:
    """基于 ProcessPoolExecutor 的并行优化器

    支持 Grid Search（全并行）和 Bayesian Search（分批并行）。
    所有子进程通过 spawn 模式启动，vnpy 引擎完全隔离。
    """

    def __init__(
        self,
        datasets: list[tuple[str, pd.DataFrame]],
        strategy_name: str,
        strategy_params: dict | None,
        backtest_config: BacktestConfig,
        search_space: dict,
        n_trials: int = 50,
        search_type: str = "bayesian",
        n_workers: int | None = None,   # 默认 os.cpu_count()
        batch_size: int | None = None,  # Bayesian 每批并行数，默认 n_workers
        study_db_path: str = "",
        study_name: str = "",
        random_seed: int = 42,
        use_fixed_seed: bool = False,
    ):
        ...

    def optimize(self) -> OptunaResult:
        """执行并行优化（Grid 全并行 / Bayesian 分批并行）

        流程:
        1. 创建 Optuna study
        2. Grid: ask(全部) → pool.map → tell(全部)
        3. Bayesian: 循环 ask(batch_size) → pool.map → tell(batch)
        4. 返回 OptunaResult
        """
        result = OptunaResult()
        study = optuna.create_study(...)

        if self._search_type == "grid":
            # Grid: 一次 ask 全部组合
            n_trials, _ = self._calc_grid_size()
            trial_params = self._ask_all_grid(study, n_trials)

            with ProcessPoolExecutor(
                max_workers=self._n_workers,
                mp_context=mp.get_context("spawn"),
                initializer=_init_worker,
                initargs=(...),
            ) as pool:
                trial_results = list(pool.map(_execute_trial, trial_params))

            for trial, outcome in zip(trial_params, trial_results):
                study.tell(trial, outcome["value"])
                result.trial_data.append(outcome)

        else:
            # Bayesian: 分批并行
            with ProcessPoolExecutor(
                max_workers=self._n_workers,
                mp_context=mp.get_context("spawn"),
                initializer=_init_worker,
                initargs=(...),
            ) as pool:
                remaining = n_trials
                with tqdm(total=n_trials) as pbar:
                    while remaining > 0:
                        bs = min(self._batch_size, remaining)
                        trials = [study.ask() for _ in range(bs)]
                        params_list = [t.params for t in trials]

                        futures = [pool.submit(_execute_trial, p)
                                   for p in params_list]
                        for f in futures:
                            outcome = f.result()
                            result.trial_data.append(outcome)
                            pbar.update(1)

                        for t, o in zip(trials, result.trial_data[-bs:]):
                            study.tell(t, o["value"])

                        remaining -= bs

        result.best_params = study.best_params
        result.best_value = study.best_value or 0.0
        result.study = study
        result.actual_seed = self._actual_seed
        return result
```

#### ask_all_grid 辅助

```python
def _ask_all_grid(self, study, n_trials):
    """生成全部 grid 组合的 trial 对象"""
    from optuna.samplers import GridSampler
    trials = []
    for _ in range(n_trials):
        trials.append(study.ask())  # GridSampler 自动按顺序返回
    return trials
```

或者更直接：不用 `ask()`，直接用 `itertools.product` 生成全部参数组合，创建 mock trial。

> **注意**：`study.ask()` 在 GridSampler 模式下会按顺序遍历网格。我们在外面 batch 调用 `study.ask()` 即可获取全部组合。

### 3.3 `backtest/optimizer.py` — 新增入口函数

```python
def run_param_search_parallel(
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    strategy_params: dict[str, Any],
    backtest_config: BacktestConfig,
    search_space: dict[str, dict[str, Any]],
    n_trials: int = 50,
    search_type: str = "bayesian",
    n_workers: int | None = None,
    batch_size: int | None = None,
    study_db_path: str = "",
    study_name: str = "",
    random_seed: int = 42,
    use_fixed_seed: bool = False,
) -> SearchResult:
    """执行并行参数搜索"""
    optimizer = ParallelBacktestOptimizer(
        datasets=datasets,
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        backtest_config=backtest_config,
        search_space=search_space,
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
    ...
```

### 3.4 `cli/commands/backtest.py` — CLI 集成

新增 `--parallel` / `--workers` 参数：

```python
# 在 _execute_search_mode 中判断
if args.parallel:
    result = run_param_search_parallel(
        datasets=...,
        backtest_config=bc,  # 传 BacktestConfig，不传 engine
        n_workers=args.workers or os.cpu_count(),
        ...
    )
else:
    result = run_param_search(engine=engine, ...)
```

**关键：旧路径完全不变，新路径不传 `engine` 实例**（engine 在子进程中自己创建）。

### 3.5 `__init__.py` 导出

```python
# backtest/__init__.py
from .parallel import ParallelBacktestOptimizer, run_param_search_parallel
```

## 4. 数据流全景

```
CLI (主进程)
 │
 ├─ dm.load_kline() → datasets: list[(symbol, DataFrame)]
 │
 ├─ ParallelBacktestOptimizer.__init__(datasets, search_space, config, ...)
 │
 ├─ ProcessPoolExecutor (spawn, initializer)
 │    └─ _init_worker(datasets, config, ...)              # 每个 worker 一次
 │    │
 │    ├─ worker 1: _execute_trial(params_1)                # 创建 VnpyBacktestEngine
 │    │             → engine.run(pairs, batch_mode=True)    # bt_id=-1, 不写 DB
 │    │             → 返回 trial_result(dict)
 │    │
 │    ├─ worker 2: _execute_trial(params_2)
 │    │
 │    └─ ...
 │
 ├─ collect trial_results → study.tell()
 │
 ├─ 主进程统一串行写入:
 │    └─ _persist_search_results()
 │         ├─ dm.insert_backtest(result)     # 单线程串行写, 无冲突
 │         ├─ dm.insert_backtest_daily(...)
 │         └─ dm.insert_backtest_trades(...)
 │
 └─ build_dashboard()
```

## 5. 边界情况

### 5.1 种子一致性

- `use_fixed_seed=True`：每个子进程中设置 `numpy.random.seed(seed)` + `random.seed(seed + worker_id)`
- `use_fixed_seed=False`：主进程为每个 trial 分配不同种子，作为参数传入

### 5.2 进程数与 trial 数的匹配

- `n_workers = min(n_trials, os.cpu_count())` 
- Bayesian 的 `batch_size = min(n_workers, remaining_trials)`，每批动态调整

### 5.3 日志与进度

- 子进程 `loguru` 输出到各自 `output/r{run_id}/workers/worker_{id}.log`
- 主进程用 `tqdm` + `pool.submit()` + `as_completed()` 实时更新进度
- Bayesian 路径中，`tell()` 后立即 `logger.info(...)` 输出当前批次最优

### 5.4 内存

- 子进程持有 `datasets`（完整 DataFrame），spawn 模式下从 `initializer` pickle 传入
- 峰值内存 ≈ `N_workers × (1 份数据集)`，对大 DataFrame 需要注意
- **优化**：`initializer` 用 `shared_memory` 或 Arrow IPC 传递数据（二期优化，初始用 pickle 即可）

### 5.5 异常处理

- `trial` 执行异常 → 返回 `score=-999.0`，`engine_results=[]`，不中断整体
- `ProcessPoolExecutor` 非预期崩溃 → `Future.exception()` 捕获，重试或跳过

## 6. 测试计划

| 测试 | 方式 |
|---|---|
| batch_mode 正确性 | 同一 config 跑 batch_mode=True vs False，结果完全一致 |
| Grid Search 并行 | 小搜索空间并行 vs 串行，参数和分数完全一致 |
| Bayesian Search 并行 | 固定种子，并行 vs 串行的 best_params 接近（允许因 batch 顺序差异微微浮动） |
| 多品种并行 | 3 品种 × 3 params，验证结果一一对应 |
| 异常隔离 | 一个 trial 抛异常不影响其他 trial |

## 7. 不在本期范围内

- Walk-Forward 窗口并行（窗口数通常太少，收益小）
- 分布式回测（多机 Spark/Ray）
- shared_memory 优化 DataFrame 传递
- 子进程日志独立文件
