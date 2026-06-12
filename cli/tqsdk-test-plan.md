# TqSdk 实时数据链路改造方案（test + live）

## 1. 背景

### 1.1 现状

项目有两条命令涉及 tqsdk 实时/实盘：

| 命令 | 文件 | 当前状态 | 问题 |
|------|------|---------|------|
| `test` | `cli/commands/test.py` | 用硬编码 2 根 K 线做离线冒烟测试 | 不联网、不接实时数据、不走 Bridge |
| `live` | `cli/commands/live.py` | 调用 `TqsdkStrategyBridge.run()` | **缺 State 参数**、**无多周期数据**，大概率跑不通 |

### 1.2 目标

- **`test` 命令**：连接天勤实时行情 → 驱动 MA 策略 → **打印信号** → 验证信号链路正确性（**不下单**）
- **`live` 命令**：连接天勤实时行情 → 驱动 MA 策略 → 通过 TargetPosTask **执行下单**（模拟盘 / 实盘）
- 两者共享同一套 Bridge 改造代码（多周期订阅 + BarContext 构造），区别仅在最后一步
- 支持多合约同时运行（共享同一个 TqApi 连接）

### 1.3 TqSdk 模拟 vs 实盘机制

```
┌─────────────────────────────────────────────────────┐
│                   天勤账号 (gaolei)                  │
│                                                      │
│  ┌──────────────┐         ┌──────────────────┐      │
│  │  未绑定期货    │  ←→     │  已绑定期货公司    │      │
│  │  公司账户     │         │  账户            │      │
│  └──────┬───────┘         └───────┬──────────┘      │
│         │                         │                  │
│    TqApi(auth)              TqApi(auth)             │
│    ↓                        ↓                      │
│  模拟交易                    实盘交易                │
│  (虚拟资金/成交)            (真金白银)               │
│                                                      │
│  ✅ 同一个账号两边都能用                              │
│  ✅ 模拟不影响实盘                                    │
│  ✅ guest 模式无需注册也能用模拟                       │
└─────────────────────────────────────────────────────┘
```

- **模拟盘**：不绑定期货公司账户即可使用，虚拟资金，成交为模拟
- **实盘**：需在网页端绑定期货公司账户，真实下单到交易所
- **两者完全独立**，同一账号可同时做模拟和实盘
- tqsdk 没有 sim/live 参数，行为由账号绑定状态决定

## 2. 设计原则

1. **MA 策略零改动** — `MaStrategyCore.on_bar(state, ctx)` 接口不变
2. **回测路径和实时路径隔离** — vnpy 回测走 DataFeed 预加载，tqsdk 实时走 API 推送
3. **两边给策略的接口一致** — 都是 `State` + `BarContext(multi={"1m", "5m", "15m"})`
4. **指标计算逻辑只写一份** — 复用 `strategies/core/indicators.py`
5. **test 和 live 共享 Bridge** — 只在"收到信号后做什么"这一步分叉
6. **命令即安全边界** — test 代码里没有下单函数，永远安全
7. **支持多合约** — CLI 创建 1 个 TqApi，传给 N 个 Bridge 共享连接

## 3. 架构

### 3.1 单合约架构

```
                    ┌──────────────────────────────────┐
   python main.py   │                                  │
   test/live        │  cmd_test() / cmd_live()          │
   --strategy ma    │  (都重写)                         │
   --symbol rb2509  │       ↓                          │
                    │  load_strategy() + apply_config() │
                    │       ↓                          │
                    │  State(config)                   │
                    │       ↓                          │
                    │  TqsdkStrategyBridge             │
                    │  (strategy, state)               │
                    │       ↓                          │
                    │  run(symbol, auth, ...)          │
                    │  (订阅多周期 kline_serial)        │
                    │       ↓                          │
                    │  构造 PeriodData + 计算指标        │
                    │       ↓                          │
                    │  BarContext(multi={...})          │
                    │       ↓                          │
                    │  strategy.on_bar(state, ctx)     │
                    │       ↓                          │
                    └───────┬──────────────────────────┘
                            │ Signal
                 ┌──────────┴──────────┐
                 ↓                     ↓
         ┌──────────────┐    ┌──────────────────┐
         │   test 命令    │    │   live 命令       │
         │              │    │                  │
         │ on_signal     │    │ TargetPosTask    │
         │ 回调打印信号   │    │ set_target_volume│
         │ 统计信号数量   │    │ notify_fill()    │
         │ 写入数据库     │    │ 写入数据库       │
         │              │    │                  │
         │ ❌ 不下单     │    │ ✅ 下单(模拟/实盘)│
         └──────────────┘    └──────────────────┘
```

### 3.2 多合约架构

```
CLI 层 (cmd_live / cmd_test)
  │
  ├── api = tqsdk.TqApi(auth=auth)           ← 1 个 API 连接
  │
  ├── bridge_rb = TqsdkStrategyBridge(..., api=api)
  │   └── bridge_rb.run(symbol="SHFE.rb2509")
  │
  ├── bridge_m = TqsdkStrategyBridge(..., api=api)
  │   └── bridge_m.run(symbol="DCE.m2509")
  │
  └── bridge_i = TqsdkStrategyBridge(..., api=api)
      └── bridge_i.run(symbol="DCE.i2509")

所有 Bridge 共享同 1 个 api.wait_update() 循环
每个 Bridge 有独立的 State / PeriodData / BarContext
```

## 4. 各文件改动详情

### 4.1 `strategies/bridges/tqsdk_bridge.py` — 核心改造（test 和 live 共用）

#### 4.1.1 构造函数：支持外部注入 api

```python
class TqsdkStrategyBridge:
    def __init__(self, strategy: Strategy, state: State[T], api=None):
        self._strategy = strategy
        self._state = state
        self.api = api  # 外部注入（多合约场景）或 None（run() 内部创建）
```

#### 4.1.2 新增 `run()`：唯一入口，替代所有旧方法

```python
def run(self, symbol: str, auth=None, on_signal=None, web_gui=False):
    """唯一入口 — 覆盖所有使用场景

    Args:
        symbol: 合约代码 (e.g. SHFE.rb2509)
        auth: 天勤认证。None 则用 guest 或从配置读取
        on_signal: 收到信号后的回调。
            - None (默认): live 模式，信号→TargetPosTask 下单
            - callable: test 模式，信号→回调处理（不下单）
        web_gui: 是否启用浏览器可视化

    行为矩阵:
        on_signal=None,  web_gui=False  → 终端 live 模式
        on_signal=None,  web_gui=True   → 浏览器 live 模式
        on_signal=fn,   web_gui=False   → 终端 test 模式
        on_signal=fn,   web_gui=True    → 浏览器 test 模式
    """
```

**内部实现要点：**

```python
def run(self, symbol, auth=None, on_signal=None, web_gui=False):
    if not tqsdk.ensure():
        logger.error("天勤量化API未安装")
        return

    # API 管理：优先用外部注入的，否则自己创建
    close_on_exit = False
    if self.api is None:
        self.api = tqsdk.TqApi(auth=auth or self._ensure_auth(auth, symbol),
                                  web_gui=web_gui)
        close_on_exit = True

    try:
        self.initialize(self.api)
        self.symbol = symbol

        # === 多周期订阅 ===
        reqs = self._strategy.data_requirements(self._state.strategy_config)
        period_map = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "d": 86400}
        self._klines: dict[str, Any] = {}
        if reqs:
            for period_name in reqs.periods:
                duration = period_map.get(period_name, 60)
                self._klines[period_name] = self.api.get_kline_serial(symbol, duration)
        else:
            self._klines["1m"] = self.api.get_kline_serial(symbol, 60)

        # === 初始化 PeriodData（复用回测的数据结构和指标计算）===
        self._init_period_data()

        # === 下单任务（仅 live 模式创建）===
        target_pos = None
        if on_signal is None:  # live 模式才需要
            target_pos = tqsdk.TargetPosTask(self.api, symbol)

        prev_lens = {name: len(kl) for name, kl in self._klines.items()}
        log_msg = f"开始运行策略: {symbol}，按Ctrl+C停止"
        if web_gui:
            log_msg += "，浏览器访问 http://127.0.0.1:9876"
        logger.info(log_msg)

        # === 主循环 ===
        while True:
            self.api.wait_update()
            for period_name, klines in self._klines.items():
                if self.api.is_changing(klines):
                    current_len = len(klines)
                    for i in range(prev_lens[period_name], current_len):
                        signal = self._on_bar_multi(klines=klines, idx=i,
                                                     main_period=period_name)
                        if signal.action:
                            close_price = float(klines.close.iloc[i])
                            # 分叉点：test 回调 vs live 下单
                            if on_signal:
                                on_signal(signal, close_price)
                            elif target_pos:
                                self._execute_order(target_pos, signal, close_price)
                    prev_lens[period_name] = current_len
    except KeyboardInterrupt:
        logger.info("策略已停止")
    except Exception as e:
        logger.exception(f"策略运行错误: {e}")
    finally:
        if close_on_exit and self.api:
            self.api.close()
```

#### 4.1.3 新增 `_init_period_data()`：构造 PeriodData + 复用指标计算

```python
def _init_period_data(self):
    """用 tqsdk kline_serial DataFrame 初始化 PeriodData 对象
    
    复用 strategies.runtime.period.PeriodData 和 
    strategies.core.indicators 的指标计算函数，
    与回测路径完全相同。
    """
    from strategies.runtime.period import PeriodData
    from strategies.runtime.data_feed import register_indicators, calculate_all

    self._period_data: dict[str, PeriodData] = {}
    for period_name, klines in self._klines.items():
        pd_obj = PeriodData(
            symbol=self.symbol,
            period=period_name,
            df=klines.copy(),  # 复制避免污染原始 DataFrame
        )
        # 注册并计算指标（与回测路径完全相同的逻辑）
        reqs = self._strategy.data_requirements(self._state.strategy_config)
        if reqs and period_name in reqs.indicators:
            for ind_req in reqs.indicators[period_name]:
                register_indicators(pd_obj, ind_req.name, ind_req.params)
            calculate_all(pd_obj)
        self._period_data[period_name] = pd_obj
```

#### 4.1.4 重写 `_on_bar_multi()`：构造完整 BarContext（含多周期指标）

```python
def _on_bar_multi(self, klines, idx, main_period) -> Signal:
    """从多周期 kline_serial 构造完整 BarContext 并驱动策略"""

    bar = Bar(
        symbol=self.symbol,
        datetime=_to_datetime(klines.datetime.iloc[idx]),
        open=float(klines.open.iloc[idx]),
        high=float(klines.high.iloc[idx]),
        low=float(klines.low.iloc[idx]),
        close=float(klines.close.iloc[idx]),
        volume=float(klines.volume.iloc[idx]),
    )

    # 更新主周期的 PeriodData 并重算最新行指标
    if main_period in self._period_data:
        self._period_data[main_period].append_bar(bar)
        calculate_all(self._period_data[main_period], from_idx=-1)

    # 构造 multi 字典：PeriodDataView（策略熟悉的接口）
    multi: dict[str, Any] = {}
    for period_name, pd_obj in self._period_data.items():
        multi[period_name] = pd_obj.view

    ctx = BarContext(symbol=self.symbol, bar=bar, multi=multi, events=[])
    self._update_peak_prices(bar)
    return self._strategy.on_bar(self._state, ctx)
```

#### 4.1.5 废弃旧方法

**删除以下方法，由新的 `run()` 统一替代：**
- ~~`run()`~~ — 旧的（单周期 + 自动下单）
- ~~`run_with_gui()`~~ — 旧的（单周期 + 浏览器 + 自动下单）
- ~~`_run_loop()`~~ — 旧的内部实现
- ~~`_watch_klines()`~~ — 旧的（单周期循环 + 硬编码日K + 强制下单）

**保留不变的方法：**
- `initialize()` / `notify_fill()` / `_update_peak_prices()` / `on_bar()` / `_ensure_auth()` — 复用
- `_execute_order()` — 从旧代码中提取的下单逻辑封装

### 4.2 `cli/commands/test.py` — 重写为信号链路验证

```python
def cmd_test(args: argparse.Namespace):
    """连接天勤实时数据运行策略，打印信号（不下单）"""

    cm = ConfigManager()
    strategy = load_strategy(args.strategy)
    apply_strategy_config(strategy, cm)
    tc = cm.get_trading_config()

    state = State(
        symbol=args.symbol,
        period=f"{tc.get('kline_period', 1)}m",
        strategy_config=strategy.config,
        capital=float(tc.get('initial_capital', 100000)),
        contract_size=int(tc.get('contract_size', 10)),
        margin=float(tc.get('margin_ratio', 0.1)),
    )

    bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
    auth = _get_tq_auth(cm)

    # 数据库持久化
    TestSession = get_live_session_model("test_sessions")
    TestTrade = get_live_trade_model("test_trades")
    session = TestSession.create(
        symbol=args.symbol, strategy="ma",
        mode="test", status="running", started_at=datetime.now(),
    )

    signal_count = 0
    buy_count = 0
    sell_count = 0

    def on_signal(signal: Signal, price: float):
        nonlocal signal_count, buy_count, sell_count
        signal_count += 1
        diag = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
        direction = "long" if signal.action == TRADE_ACTION_BUY else "short"
        offset = "open" if signal.volume > 0 else "close"
        logger.info(f"[TEST] #{signal_count} {signal.action} "
                     f"price={price:.2f} vol={signal.volume} "
                     f"reason={signal.reason} | {diag}")

        # 写入数据库
        TestTrade.create(
            session=session.id, datetime=datetime.now(),
            symbol=args.symbol, direction=direction, offset=offset,
            price=price, quantity=signal.volume, reason=signal.reason,
        )
        if signal.action == TRADE_ACTION_BUY:
            buy_count += 1
        elif signal.action == TRADE_ACTION_SELL:
            sell_count += 1

    gui = getattr(args, 'gui', False)
    logger.info(f"[TEST] 策略={get_strategy_class_name(strategy)} "
                f"标的={args.symbol} GUI={'开' if gui else '关'}")

    try:
        bridge.run(symbol=args.symbol, auth=auth,
                    on_signal=on_signal, web_gui=gui)
    except KeyboardInterrupt:
        pass
    finally:
        session.update(status='stopped', ended_at=datetime.now(),
            total_signals=signal_count, buy_signals=buy_count,
            sell_signals=sell_count)
        logger.info(f"[TEST] 完成: 信号={signal_count} "
                     f"买入={buy_count} 卖出={sell_count}")
```

### 4.3 `cli/commands/live.py` — 修复并接入新 Bridge

**当前 bug**：
```python
# L65 — 缺少 state 参数！
bridge = TqsdkStrategyBridge(strategy=strategy, symbol=args.symbol)
# 应改为：
bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
```

**改动后核心逻辑**：
```python
def cmd_live(args):
    # ... 加载策略、创建 State（同 test.py）...

    bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
    auth = _get_tq_auth(cm)

    # 数据库持久化
    LiveSession = get_live_session_model("live_sessions")
    LiveTrade = get_live_trade_model("live_trades")
    session = LiveSession.create(
        symbol=args.symbol, strategy="ma",
        mode="sim",  # 由账号绑定状态决定实际是 sim 还是 live
        status="running", started_at=datetime.now(),
        initial_capital=state.capital,
    )

    def on_fill_callback(fill, pnl, commission):
        """每次成交时写入数据库"""
        LiveTrade.create(session=session.id, ...)
        session.update(current_balance=..., total_pnl=..., ...)

    try:
        # on_signal=None → live 模式，自动通过 TargetPosTask 下单
        bridge.run(symbol=args.symbol, auth=auth, web_gui=getattr(args, 'gui', False))
    except KeyboardInterrupt:
        pass
    finally:
        session.update(status='stopped', ended_at=datetime.now())
```

### 4.4 `cli/main.py` — 参数调整

```python
# test 子命令
p = sub.add_parser("test", help="通过天勤实时数据验证策略信号链路（不下单）")
p.add_argument("--strategy", required=True)
p.add_argument("--symbol", required=True, help="合约代码 (e.g. SHFE.rb2509)")
p.add_argument("--gui",
               action="store_true",
               help="启用浏览器可视化 (默认关闭)")

# live 子命令（已有，微调帮助文案和参数）
p = sub.add_parser("live", help="天勤模拟/实盘交易（会下单，模拟/实盘取决于账号是否绑定期货公司）")
p.add_argument("--strategy", required=True)
p.add_argument("--symbol", required=True, help="合约代码 (e.g. SHFE.rb2509)")
p.add_argument("--gui", action="store_true", help="启用浏览器可视化")
# ... 其他已有参数不变 ...
```

## 5. 使用方式

### 单合约

```bash
# ===== test 命令：信号验证（不下单）=====

# 连接实时行情，打印策略信号（默认用 guest 凭证，无需配置）
python main.py test --strategy ma --symbol SHFE.rb2509

# + 浏览器可视化（看 K 线图和策略信号标记）
python main.py test --strategy ma --symbol SHFE.rb2509 --gui


# ===== live 命令：实际交易（会下单）=====

# 模拟盘交易（天勤账号未绑定期货公司 = 模拟）
python main.py live --strategy ma --symbol SHFE.rb2509

# 模拟盘 + 浏览器可视化
python main.py live --strategy ma --symbol SHFE.rb2509 --gui

# 实盘交易（需在天勤网页端绑定期货公司账户，慎用！）
# 与上面命令完全相同，区别只在于账号是否绑定了期货公司
python main.py live --strategy ma --symbol SHFE.rb2509
```

### 多合约（CLI 层面，Bridge 层已就绪）

```bash
# 未来可扩展为：
python main.py live --strategy ma --symbols SHFE.rb2509,DCE.m2509,DCE.i2509

# 内部等价于：
#   api = TqApi(auth=auth)
#   for s in symbols:
#     bridge = TqsdkStrategyBridge(..., api=api)
#     bridge.run(symbol=s)
```

**说明**：
- tqsdk 没有 sim/live 参数。模拟 vs 完全取决于你的**天勤账号是否绑定了期货公司账户**
- 未绑定 → 下单走天勤模拟撮合（虚拟资金，不影响真实账户）
- 已绑定 → 下单发到真实期货交易所

**重要安全保证**：`test` 命令的代码路径中**不包含任何下单逻辑**（不调 TargetPosTask），因此即使账号已绑定期货公司，运行 `test` 也永远不会下单。这是代码层面的硬隔离，不是靠配置或 flag。

## 6. 三条路径对比

| 维度 | 回测 (vnpy) | test (tqsdk) | live (tqsdk) |
|------|-------------|--------------|--------------|
| 入口 | cmd_backtest | cmd_test | cmd_live |
| 数据来源 | 本地数据库历史 K 线 | 天勤服务器实时推送 | 天勤服务器实时推送 |
| 桥接器 | VnpyBacktestBridge | TqsdkStrategyBridge | TqsdkStrategyBridge |
| 多周期数据 | DataFeed 预加载全部历史 | PeriodData 实时追加 | 同左 |
| 指标计算 | DataFeed 批量预计算 | **复用同一套 indicators 函数** | 同左 |
| BarContext 构建 | `_ctx_cache` O(1) 查找 | 从 PeriodDataView 实时构造 | 同左 |
| 收到信号后 | vnpy 引擎模拟成交 | **回调打印，不下单** | **TargetPosTask 下单** |
| State 管理 | StrategyFactory.make_state() | cmd_test 创建 | cmd_live 创建 |
| 结果存储 | backtests + backtest_trades | test_sessions + test_trades | live_sessions + live_trades |
| MA 策略接口 | **完全相同** | **完全相同** | **完全相同 |

## 7. 各模块职责边界

```
MaStrategyCore (strategies/ma_strategy.py)
  职责：纯策略逻辑 — 接收行情 → 输出信号
  输入：State + BarContext(multi={...})
  输出：Signal
  不变 ❌

TqsdkStrategyBridge (bridges/tqsdk_bridge.py)
  职责：天勤 API ↔ 策略 的协议转换层
  做：
    - 多周期 kline_serial 订阅
    - PeriodData 初始化 + 每根 K 线更新
    - 指标计算调度（调用已有的 register/calculate 函数）
    - State 管理
    - 信号分发（test 回调 / live 下单）
    - 持久化通知（写入数据库）
  不做：
    - 数据文件 I/O（tqsdk 自己推送）
    - 统计指标计算（report 层的事）

cmd_test (cli/commands/test.py)
  职责：test 命令入口
  做：加载策略 → 创建 State/Bridge → 传 on_signal 打印回调 → 调 bridge.run()
  不做：碰任何下单相关逻辑

cmd_live (cli/commands/live.py)
  职责：live 命令入口
  做：加载策略 → 创建 State/Bridge → 调 bridge.run()（自动触发 TargetPosTask 下单）
  不做：自己构造 Bar / 管理多周期数据

data/models.py
  职责：ORM Model 定义
  新增 BaseLiveModel → LiveSession / LiveTrade（动态表名）
  不做：业务逻辑、写入时机、数据校验
```

## 8. 已决策项

- [x] **指标实时计算**：**采用 PeriodData 结构 + 复用回测指标计算逻辑**
  - tqsdk 拿到的多周期 kline_serial DataFrame → 直接构造 `PeriodData` 对象
  - 调用已有的 `register_*()` / `calculate_all()` 计算指标
  - 策略通过 `ctx.multi["5m"].indicator("sma_10")` 读取，与回测路径**完全相同**
  - **不需要** DataFeed 的数据加载/缓存/过期检查逻辑（tqsdk 已负责数据推送）
  - **不需要**自定义适配器类（TqSdkPeriodView 方案废弃）
- [x] **live 安全确认**：**不需要额外 flag。命令职责即安全边界：**
  - `test` = 只看信号，**代码里就不调 TargetPosTask**，永远不下单（不管账号是否绑定期货公司）
  - `live` = 会调用 TargetPosTask 下单，模拟还是实盘取决于天勤账号是否绑定期货公司
  - **即使账号已绑定实盘，test 命令仍然安全**——因为下单逻辑根本不存在于 test 的代码路径中
- [x] **退出后持久化**：**2 个 ORM Model，4 张物理表，字段统一**
  - `LiveSession` model → 映射 `test_sessions` / `live_sessions`（通过运行时指定表名）
  - `LiveTrade` model → 映射 `test_trades` / `live_trades`
  - test 表中 pnl/commission 为 NULL（不下单就没有真实盈亏）
- [x] **函数设计**：**单一 `run()` 入口，参数控制行为**
  - 删除旧的 `run()` / `run_with_gui()` / `_run_loop()` / `_watch_klines()`
  - 新 `run(symbol, auth, on_signal=None, web_gui=False)` 为唯一入口
  - `on_signal=None` → live 下单模式；`on_signal=fn` → test 打印模式
- [x] **多合约支持**：**CLI 创建 1 个 TqApi，注入给 N 个 Bridge**
  - Bridge 构造函数接受可选 `api` 参数
  - 有 api → 直接用；无 api → 自己创建（兼容单合约用法）
  - 所有 Bridge 共享同一个 `wait_update()` 循环

## 9. 数据库表设计

### Model 1：`LiveSession` — 会话汇总

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| **标识** | | |
| symbol | VARCHAR(20) | 品种代码 (如 SHFE.rb2509) |
| strategy | VARCHAR(50) | 策略名称 |
| strategy_version | VARCHAR(20) | 策略版本号 |
| git_hash | VARCHAR(40) | 提交哈希 |
| **运行状态** | | |
| mode | VARCHAR(10) | "test" / "sim" / "live" |
| status | VARCHAR(20) | running / stopped / error |
| started_at | DATETIME | 开始时间 |
| ended_at | DATETIME | 结束时间 |
| **金额变动（live 时实时更新，test 时为 NULL）** | | |
| initial_capital | FLOAT | 初始资金 |
| current_balance | FLOAT | 当前权益 |
| total_pnl | FLOAT | 累计净盈亏 |
| total_commission | FLOAT | 累计手续费 |
| total_trades | INTEGER | 总成交笔数 |
| **信号统计（test 时填充，live 时为 0）** | | |
| total_signals | INTEGER | 总信号数 |
| buy_signals | INTEGER | 买入信号数 |
| sell_signals | INTEGER | 卖出信号数 |
| **统计指标（预留，暂不填）** | | |
| total_return | FLOAT NULL | 总收益率 |
| sharpe_ratio | FLOAT NULL | 夏普比率 |
| max_drawdown | FLOAT NULL | 最大回撤 |
| win_rate | FLOAT NULL | 胜率 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### Model 2：`LiveTrade` — 逐笔记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| session_id | INTEGER FK → LiveSession.id | 关联会话 |
| datetime | DATETIME | 时间（test=信号时间, live=成交时间） |
| symbol | VARCHAR(20) | 品种代码 |
| direction | VARCHAR(10) | 方向 (long/short) |
| offset | VARCHAR(10) | 开平标志 (open/close) |
| price | FLOAT | 价格（test=触发价, live=成交价） |
| quantity | FLOAT | 数量（手） |
| pnl | FLOAT | 净盈亏（test 时为 NULL 或 0） |
| commission | FLOAT | 手续费（test 时为 NULL 或 0） |
| reason | VARCHAR(512) | 触发原因 |
| created_at | DATETIME | 创建时间 |

### Peewee 实现方式

```python
# data/models.py

class BaseLiveModel(OrmBaseModel):
    """Live/Test 共用的基类"""
    class Meta:
        table_name = None  # 子类必须指定

def get_live_session_model(table_name: str):
    """返回映射到指定表名的 LiveSession model"""
    class LiveSession(BaseLiveModel):
        # （字段定义见上表）
        class Meta:
            table_name = table_name
    return LiveSession

# 使用：
TestSession = get_live_session_model("test_sessions")   # test 用
LiveSession = get_live_session_model("live_sessions")   # live 用
TestTrade   = get_live_trade_model("test_trades")       # test 用
LiveTrade   = get_live_trade_model("live_trades")       # live 用
```

### 写入时机

```
===== test 命令 =====
启动时:
  TestSession.create(symbol='SHFE.rb2509', strategy='ma', mode='test', status='running')

每次产生 Signal 时:
  TestTrade.create(session_id=..., datetime=now, direction=..., offset=...,
                   price=bar.close, quantity=signal.volume, reason=...)

退出时:
  session.update(status='stopped', ended_at=now(), total_signals=n, ...)

===== live 命令 =====
启动时:
  LiveSession.create(symbol='SHFE.rb2509', strategy='ma', mode='sim',
                     status='running', initial_capital=100000)

每次产生 Fill 时:
  LiveTrade.create(session_id=..., datetime=fill.timestamp, ..., price=fill.price,
                   pnl=pnl, commission=commission, ...)
  LiveSession.update(current_balance=..., total_pnl=..., total_trades=...)

退出时:
  LiveSession.update(status='stopped', ended_at=now())
```
