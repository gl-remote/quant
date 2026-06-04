# -*- coding: utf-8 -*-
"""
vn.py 回测引擎 (纯执行器)

基于 vnpy_ctastrategy.backtesting.BacktestingEngine，接收 DataFrame + 策略参数，
返回结构化回测结果。不负责数据加载和策略创建。

职责明确：
  - data_utils 负责数据转换
  - strategy_factory 负责策略创建
  - results 负责结果聚合
  - optimizer 负责参数搜索
  - backtest 层仅调用 vnpy 执行回测
"""

from __future__ import annotations

from loguru import logger
from typing import TYPE_CHECKING, Any

import pandas as pd

from strategies.utils import serialize_strategy_params
from config.app_config import BacktestConfig
from data.manager import DataManager

from .data_utils import df_to_vnpy_datalines, resolve_interval, calculate_date_range
from .results import aggregate_walk_forward
from .strategy_factory import create_strategy_class

from common.symbol_utils import parse_contract
from common.types import BacktestResult
from common.constants import DIRECTION_MAP, OFFSET_MAP


class VnpyBacktestEngine:
    """vn.py 回测引擎 (纯执行器)

    接收 DataFrame + 策略名称参数，调用 vnpy BacktestingEngine 执行回测，
    返回结构化结果字典。

    使用方式:
        engine = VnpyBacktestEngine(backtest_config, data_manager)
        results = engine.run(pairs)             # 多策略 × 多品种
        wf_result = engine.run_walk_forward(    # 单策略 Walk-Forward
            data, symbol, strategy_name, strategy_params, ...
        )
    """

    def __init__(self, backtest_config: BacktestConfig, dm: DataManager):
        """
        Args:
            backtest_config: 回测配置（含 capital/commission/slippage 等交易环境参数）
            dm: 数据管理器，提供数据加载能力
        """
        self._dm = dm
        self._run_id: int | None = None
        self._git_hash: str | None = None
        self.initial_capital: float = float(backtest_config.initial_capital)
        self.commission_rate: float = float(backtest_config.commission_rate)
        self.slippage: float = float(backtest_config.slippage)
        self.price_tick: float = float(backtest_config.price_tick)
        self.contract_size: int = int(backtest_config.contract_size)
        self.interval: str = backtest_config.interval

        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital 必须大于 0，当前: {self.initial_capital}")
        if not (0 <= self.commission_rate < 1):
            raise ValueError(f"commission_rate 必须在 [0, 1) 范围内，当前: {self.commission_rate}")
        if self.slippage < 0:
            raise ValueError(f"slippage 不能为负数，当前: {self.slippage}")
        if self.price_tick <= 0:
            raise ValueError(f"price_tick 必须大于 0，当前: {self.price_tick}")
        if self.contract_size <= 0:
            raise ValueError(f"contract_size 必须大于 0，当前: {self.contract_size}")

    def set_git_hash(self, git_hash: str | None) -> None:
        """设置 Git 提交哈希
        """
        self._git_hash = git_hash

    # ── 私有辅助方法 ──────────────────────────────────────────

    def _create_backtest_result(
        self,
        symbol: str,
        backtest_id: int | None,
        strategy_name: str,
        strategy_version: str | None,
        strategy_params: dict[str, float] | None,
        error: str | None,
        data_start: str,
        data_end: str,
        total_days: int,
        stats: dict[str, Any],
        daily_results: list[dict[str, Any]],
        trades: list[dict[str, Any]] | None = None,
    ) -> BacktestResult:
        """创建 BacktestResult 对象

        Args:
            symbol: 品种代码
            backtest_id: 回测记录 ID
            strategy_name: 策略名称
            strategy_version: 策略版本
            strategy_params: 策略参数
            error: 错误信息（如果有）
            data_start: 开始日期
            data_end: 结束日期
            total_days: 总天数
            stats: 统计信息字典
            daily_results: 每日结果列表
            trades: 交易记录列表

        Returns:
            BacktestResult 对象
            
        调试沉淀(2026-06-04):
        - vn.py 回测引擎返回的 statistics 字典中，总交易数的键为 total_trade_count 而非 total_trades
        - 旧代码从 profit_days/loss_days 读取会导致错误的交易统计
        - win_trades/loss_trades 等字段在默认统计输出中可能缺失
        """
        return BacktestResult(
            symbol=symbol,
            backtest_id=backtest_id,
            strategy=strategy_name,
            strategy_version=strategy_version,
            git_hash=self._git_hash,
            strategy_params=strategy_params or {},
            success=error is None,
            error_message=error,
            start_date=data_start,
            end_date=data_end,
            total_days=total_days,
            # 调试记录(2026-06-04): vn.py statistics 中总交易数字段是 total_trade_count 而非 total_trades
            total_trades=stats.get('total_trade_count', stats.get('total_trades', 0)) or 0,
            total_return=stats.get('total_return', 0.0) or 0.0,
            end_balance=stats.get('end_balance', self.initial_capital) or self.initial_capital,
            annual_return=stats.get('annual_return'),
            win_trades=stats.get('win_trades', 0) or 0,
            loss_trades=stats.get('loss_trades', 0) or 0,
            win_rate=stats.get('win_rate'),
            max_consecutive_win=stats.get('max_consecutive_win'),
            max_consecutive_loss=stats.get('max_consecutive_loss'),
            avg_win=stats.get('average_win'),
            avg_loss=stats.get('average_loss'),
            win_loss_ratio=stats.get('win_loss_ratio'),
            sharpe_ratio=stats.get('sharpe_ratio'),
            max_drawdown=stats.get('max_drawdown'),
            max_drawdown_duration=stats.get('max_drawdown_duration', stats.get('max_ddpercent_duration', 0)),
            daily_std=stats.get('return_std', stats.get('daily_std')),
            return_drawdown_ratio=stats.get('return_drawdown_ratio'),
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
            price_tick=self.price_tick,
            contract_size=self.contract_size,
            kline_interval=self.interval,
            daily_results=daily_results if daily_results else [],
            fills=trades if trades else [],
        )

    def _create_placeholder_record(
        self,
        symbol: str,
        strategy_name: str,
        strategy_version: str | None,
        data_start: str,
        data_end: str,
        total_days: int,
    ) -> Any:
        """创建回测占位记录

        Args:
            symbol: 品种代码
            strategy_name: 策略名称
            strategy_version: 策略版本
            data_start: 开始日期
            data_end: 结束日期
            total_days: 总天数

        Returns:
            创建的 Backtest 模型实例
        """
        from data.models import Backtest as BTModel
        return BTModel.create(
            run=self._run_id,
            symbol=symbol,
            strategy=strategy_name,
            strategy_version=strategy_version,
            git_hash=self._git_hash,
            status="running",
            start_date=data_start,
            end_date=data_end,
            total_days=total_days,
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
            price_tick=self.price_tick,
            contract_size=self.contract_size,
            kline_interval=self.interval,
        )

    # ── 公开接口 ──────────────────────────────────────────────

    def run(
        self,
        pairs: list[tuple[str, pd.DataFrame, str, dict[str, Any]]],
    ) -> list[BacktestResult]:
        """执行多策略 × 多品种回测

        每个品种创建一个 vnpy engine，注册该品种的所有策略，一次回放拿到多组结果。

        Args:
            pairs: [(symbol, DataFrame, strategy_name, strategy_params), ...]

        Returns:
            list[BacktestResult]
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"启动 vn.py 回测: {len(pairs)} 个配对")
        logger.info(f"资金={self.initial_capital:,.0f} "
                    f"费率={self.commission_rate:.4%} 滑点={self.slippage}")
        logger.info(f"{'=' * 60}")

        from collections import defaultdict
        groups: dict[int, list[tuple[str, str, dict[str, Any]]]] = defaultdict(list)
        df_map: dict[int, pd.DataFrame] = {}
        for sym, df, strategy_name, strategy_params in pairs:
            df_id = id(df)
            groups[df_id].append((sym, strategy_name, strategy_params))
            df_map[df_id] = df

        results: list[BacktestResult] = []
        for df_id, items in groups.items():
            df = df_map[df_id]
            symbols = [sym for sym, _, _ in items]
            strategy_names = [name for _, name, _ in items]
            strategy_params_list = [params for _, _, params in items]
            symbol = symbols[0]

            logger.info(f"\n>>> 品种: {symbol} ({len(strategy_names)} 个策略)")

            data_start, data_end, total_days = calculate_date_range(df)
            logger.debug(f"数据: {len(df)} 条, {data_start} ~ {data_end}, 共 {total_days} 天")

            batch_results = self._run_backtest(df, symbol, strategy_names, strategy_params_list)
            for i, r in enumerate(batch_results):
                stats = r.get('statistics', {})
                daily = r.get('daily_results', [])
                error = r.get('error')
                sym = symbols[i] if i < len(symbols) else symbol
                strategy_config = r.get('strategy_config')
                results.append(self._create_backtest_result(
                symbol=sym,
                backtest_id=r.get('bt_id'),
                strategy_name=strategy_names[i] if i < len(strategy_names) else "unknown",
                strategy_version=r.get('strategy_version'),
                strategy_params=serialize_strategy_params(strategy_config) if strategy_config else {},
                error=error,
                data_start=data_start,
                data_end=data_end,
                total_days=total_days,
                stats=stats,
                daily_results=daily,
                trades=r.get('trades', []),
            ))

        succeeded = sum(1 for r in results if r.success)
        logger.info(f"\n回测完成: {succeeded}/{len(results)} 成功")
        return results

    def run_walk_forward(
        self,
        data: pd.DataFrame | None,
        symbol: str,
        strategy_name: str,
        strategy_params: dict[str, Any],
        train_size: int | None = None,
        val_size: int | None = None,
        test_size: int | None = None,
        step: int | None = None,
    ) -> dict[str, Any]:
        """执行 Walk-Forward 时间序列验证回测

        Args:
            data: K 线数据 (已由调用方加载和日期过滤)
            symbol: 合约代码
            strategy_name: 策略名称
            strategy_params: 策略参数字典
            train_size/val_size/test_size/step: 窗口参数

        Returns:
            walk_forward 结果字典
        """
        from .walk_forward import walk_forward_split_by_ratio, walk_forward_split

        if data is None or data.empty:
            return {'success': False, 'error': '数据为空', 'windows': 0}

        if train_size is not None and val_size is not None and test_size is not None:
            step_val = step or max(1, test_size // 2)
            windows = walk_forward_split(data, train_size, val_size, test_size, step_val)
        else:
            windows = walk_forward_split_by_ratio(data)

        if not windows:
            return {'success': False, 'error': '无法生成窗口', 'windows': 0}

        logger.info(f"Walk-Forward: {len(windows)} 个窗口, {symbol}")

        window_results = []
        for wi, (train_df, val_df, test_df) in enumerate(windows):
            logger.debug(f"\n>>> Walk-Forward 窗口 {wi + 1}/{len(windows)}")
            train_results = self._run_backtest(
                train_df, symbol, [strategy_name], [strategy_params],
            )
            test_results = self._run_backtest(
                test_df, symbol, [strategy_name], [strategy_params],
            )

            train_result = train_results[0] if train_results else {}
            test_result = test_results[0] if test_results else {}

            if 'error' in train_result or 'error' in test_result:
                logger.warning(
                    f"窗口 {wi + 1} 回测异常，跳过: "
                    f"train_error={train_result.get('error')}, "
                    f"test_error={test_result.get('error')}"
                )
                continue

            window_results.append({
                'window': wi,
                'train_rows': len(train_df),
                'val_rows': len(val_df),
                'test_rows': len(test_df),
                'train_start': str(train_df['datetime'].iloc[0])[:10],
                'train_end': str(train_df['datetime'].iloc[-1])[:10],
                'test_start': str(test_df['datetime'].iloc[0])[:10],
                'test_end': str(test_df['datetime'].iloc[-1])[:10],
                'statistics': test_result.get('statistics', {}),
                'statistics_is': train_result.get('statistics', {}),
            })

        aggregate = aggregate_walk_forward(window_results)

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"OOS均收益={aggregate.return_mean:.2%}, "
            f"夏普={aggregate.sharpe_mean:.2f}, "
            f"IS-OOS差距={aggregate.is_oos_return_gap:.2%}, "
            f"盈利窗口比={aggregate.positive_window_ratio:.0%}"
        )

        return {
            'success': True,
            'symbol': symbol,
            'windows': len(windows),
            'window_results': window_results,
            'aggregate': aggregate.to_dict(),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy_names: list[str],
        strategy_params_list: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """在单个数据集上执行 vnpy 回测

        Args:
            df: K 线数据
            symbol: 品种代码
            strategy_names: 策略名称列表
            strategy_params_list: 策略参数列表

        Returns:
            list[dict]，每个 dict:
              - statistics, daily_results, strategy_config, strategy_version
              - error (如果失败)
        """
        from vnpy_ctastrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Exchange

        c = parse_contract(symbol)
        if c is None:
            raise ValueError(f"无法解析合约代码: {symbol!r}")
        pure_symbol = c.contract_code
        exchange_code = c.exchange
        vt_symbol = f"{pure_symbol}.{Exchange(exchange_code).value}"

        interval = resolve_interval(self.interval)
        bars = df_to_vnpy_datalines(df, pure_symbol, exchange_code, interval)

        data_start, data_end, total_days = calculate_date_range(df)
        
        results: list[dict[str, Any]] = []
        for strategy_name, strategy_params in zip(strategy_names, strategy_params_list):
            # 提前获取策略版本号
            from strategies import load_strategy
            _core = load_strategy(strategy_name)
            strategy_version = getattr(type(_core), 'VERSION', None)
            
            # 创建占位记录
            bt_placeholder = self._create_placeholder_record(
                symbol=symbol,
                strategy_name=strategy_name,
                strategy_version=strategy_version,
                data_start=data_start,
                data_end=data_end,
                total_days=total_days,
            )
            bt_id = bt_placeholder.id

            strategy_cls = create_strategy_class(
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                symbol=symbol,
                period=self.interval,
                capital=self.initial_capital,
                contract_size=self.contract_size,
                run_id=self._run_id or 0,
                backtest_id=bt_id,
            )

            engine = BacktestingEngine()
            # vnpy print → loguru，加上下文，丢进度条
            _ctx = f"bt{bt_id}/{symbol}/{strategy_name}"
            _params_summary = ", ".join(f"{k}={v}" for k, v in strategy_params.items())
            def _vnpy_output(msg: str, _ctx: str = _ctx) -> None:
                if "回放进度" in msg:
                    return
                logger.debug(f"[vnpy|{_ctx}] {msg}")
            engine.output = _vnpy_output
            logger.debug(f"[vnpy|{_ctx}] 参数: {_params_summary}")
            engine.set_parameters(
                vt_symbol=vt_symbol,
                interval=interval,
                start=df['datetime'].iloc[0].to_pydatetime(),
                end=df['datetime'].iloc[-1].to_pydatetime(),
                rate=self.commission_rate,
                slippage=self.slippage,
                size=self.contract_size,
                pricetick=self.price_tick,
                capital=int(self.initial_capital),
            )
            engine.add_strategy(strategy_cls, {'price_tick': self.price_tick})
            engine.history_data = bars

            try:
                with logger.contextualize(bt_id=f"|bt{bt_id}"):
                    engine.run_backtesting()
                daily_results = engine.calculate_result()
                statistics = engine.calculate_statistics()
                
                """
                从 vnpy 回测引擎中提取交易记录并格式化
                
                调试沉淀(2026-06-04):
                - vn.py BacktestingEngine.trades 是一个字典，而非列表！
                - 字典键格式: 'BACKTESTING.1', 'BACKTESTING.2'... 等序号字符串
                - 值类型: vnpy.trader.object.TradeData 对象
                - 旧代码直接遍历字典导致只拿到键字符串，报 'str' object has no attribute 'datetime' 错误
                - 需要用 dict.values() 获取 TradeData 对象列表
                
                调试沉淀(2026-06-05):
                - TradeData 没有 trade_pnl 字段！vnpy 的 PnL 按天汇总在 DailyResult 上
                - plain_trade 需要通过 FIFO 配对开平仓自行计算
                - 配对规则: 按 datetime 排序，OPEN 入队，CLOSE 与队列中最旧的开仓配对
                - LONG open + SHORT close → price_diff > 0 时盈利
                - SHORT open + LONG close → price_diff < 0 时盈利
                """
                trades_list = []
                if hasattr(engine, 'trades'):
                    trades_list = list(engine.trades.values())

                # FIFO 配对开平仓，计算逐笔盈亏
                trades_list.sort(key=lambda t: t.datetime.timestamp() if t.datetime else 0)
                open_queue: list[tuple[str, float, float]] = []  # (direction, price, volume)
                trade_pnls: list[float] = [0.0] * len(trades_list)

                for i, trade in enumerate(trades_list):
                    offset_val = getattr(trade, 'offset', None)
                    offset_str = offset_val.value if offset_val is not None and hasattr(offset_val, 'value') else str(offset_val) if offset_val else ''
                    offset = OFFSET_MAP.get(offset_str, offset_str)
                    if offset == 'open':
                        direction_val = getattr(trade, 'direction', None)
                        direction_str = direction_val.value if direction_val is not None and hasattr(direction_val, 'value') else str(direction_val) if direction_val else ''
                        direction = DIRECTION_MAP.get(direction_str, direction_str)
                        open_queue.append((direction, getattr(trade, 'price', 0.0), getattr(trade, 'volume', 0.0)))
                        trade_pnls[i] = 0.0
                    else:
                        # 平仓：按 FIFO 与开仓配对
                        close_price = getattr(trade, 'price', 0.0)
                        remaining = getattr(trade, 'volume', 0.0)
                        total_pnl = 0.0
                        while remaining > 0 and open_queue:
                            open_dir, open_price, open_vol = open_queue[0]
                            matched_vol = min(remaining, open_vol)
                            price_diff = close_price - open_price
                            if open_dir == 'long':
                                total_pnl += price_diff * matched_vol * self.contract_size
                            else:  # short
                                total_pnl += -price_diff * matched_vol * self.contract_size
                            remaining -= matched_vol
                            if matched_vol >= open_vol:
                                open_queue.pop(0)
                            else:
                                open_queue[0] = (open_dir, open_price, open_vol - matched_vol)
                        trade_pnls[i] = total_pnl

                """
                将 vnpy TradeData 对象转换为标准字典（字段名与 ORM BacktestTrade 对齐）

                字段映射（vnpy TradeData → 标准字段）:
                    datetime   → datetime
                    direction  → direction (枚举值转字符串)
                    offset     → offset    (枚举值转字符串)
                    price      → open_price, close_price
                    volume     → quantity
                    pnl        → 通过 FIFO 配对计算（TradeData 无此字段）
                    commission → commission（TradeData 无此字段，暂=0）
                    (symbol 由外层注入)

                调试沉淀(2026-06-04):
                - direction 和 offset 是枚举类型，需调用 .value 获取字符串值
                - 避免直接访问 trade 对象属性，使用 getattr() 以防字段缺失
                - open_price/close_price 在单笔成交中取同一值 price，完整交易的开平仓价由策略层组装
                
                调试沉淀(2026-06-05):
                - TradeData 无 trade_pnl 和 commission 字段，统一通过 FIFO 配对计算
                - commission 隐藏在 vnpy 引擎内部计算中，无法逐笔提取，暂填 0
                """
                formatted_trades = []
                for i, trade in enumerate(trades_list):
                    dt = getattr(trade, 'datetime', None)
                    direction_val = getattr(trade, 'direction', None)
                    offset_val = getattr(trade, 'offset', None)
                    price_val = getattr(trade, 'price', 0.0)
                    quantity_val = getattr(trade, 'volume', 0.0)

                    direction = DIRECTION_MAP.get(direction_val.value) if direction_val is not None and hasattr(direction_val, 'value') else DIRECTION_MAP.get(str(direction_val), str(direction_val))
                    offset = OFFSET_MAP.get(offset_val.value) if offset_val is not None and hasattr(offset_val, 'value') else OFFSET_MAP.get(str(offset_val), str(offset_val))

                    trade_dict = {
                        'datetime': dt,
                        'symbol': symbol,
                        'direction': direction,
                        'offset': offset,
                        'open_price': price_val,
                        'close_price': price_val,
                        'quantity': quantity_val,
                        'pnl': trade_pnls[i],
                        'commission': 0.0,
                        'reason': getattr(trade, 'reason', ''),
                    }
                    formatted_trades.append(trade_dict)

                # vnpy calculate_statistics 不输出 win_trades/loss_trades 等字段
                # 从交易记录的 pnl 字段自行计算并注入 statistics 字典
                if formatted_trades:
                    win_list = [t for t in formatted_trades if t['pnl'] > 0]
                    loss_list = [t for t in formatted_trades if t['pnl'] <= 0]
                    win_cnt = len(win_list)
                    loss_cnt = len(loss_list)
                    total_trade_cnt = win_cnt + loss_cnt
                    avg_win_val = sum(t['pnl'] for t in win_list) / win_cnt if win_cnt else 0
                    avg_loss_val = abs(sum(t['pnl'] for t in loss_list) / loss_cnt) if loss_cnt else 0

                    # 最大连续盈利/亏损
                    max_consecutive_win = 0
                    max_consecutive_loss = 0
                    cur_win = 0
                    cur_loss = 0
                    for t in formatted_trades:
                        if t['pnl'] > 0:
                            cur_win += 1
                            cur_loss = 0
                            if cur_win > max_consecutive_win:
                                max_consecutive_win = cur_win
                        else:
                            cur_loss += 1
                            cur_win = 0
                            if cur_loss > max_consecutive_loss:
                                max_consecutive_loss = cur_loss

                    statistics['win_trades'] = win_cnt
                    statistics['loss_trades'] = loss_cnt
                    statistics['average_win'] = avg_win_val
                    statistics['average_loss'] = avg_loss_val
                    statistics['win_rate'] = win_cnt / total_trade_cnt if total_trade_cnt else 0
                    statistics['win_loss_ratio'] = avg_win_val / avg_loss_val if avg_loss_val > 0 else 0
                    statistics['max_consecutive_win'] = max_consecutive_win
                    statistics['max_consecutive_loss'] = max_consecutive_loss

                logger.info(f"[{symbol}][{strategy_name}] 提取到 {len(formatted_trades)} 条交易记录")
            except Exception as e:
                logger.exception(
                    f"回测执行异常 [{symbol}][{strategy_name}]: {e}",
                )
                results.append({
                    'bt_id': bt_id,
                    'statistics': {},
                    'daily_results': [],
                    'trades': [],
                    'error': str(e),
                    'strategy_config': None,
                    'strategy_version': strategy_version or '',
                })
                continue

            results.append({
                'bt_id': bt_id,
                'statistics': statistics,
                'daily_results': daily_results.reset_index().to_dict('records'),
                'trades': formatted_trades,
                'strategy_config': None,
                'strategy_version': strategy_version or '',
            })

        return results