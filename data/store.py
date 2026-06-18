"""内部存储层 - 数据库操作实现（对外隐藏）

提供数据库连接管理和 CRUD 操作，被 DataManager 调用，
外部模块不应直接使用此模块。

重构说明（2026-06-06）：
  - 原 `insert_backtest_detailed` 有两个几乎相同的大分支（更新/新建），逻辑重复
  - 提取 `_build_backtest_fields` 统一字段构造，消除 60+ 行重复赋值
  - 业务聚合查询（`get_run_summary` / `get_backtests_for_run` / `get_optuna_data`）
    拆出 `_build_summary_for_symbol` / `_query_trial_stats` 等辅助
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa
from loguru import logger
from peewee import OperationalError

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportArgumentType=false
# pyright: reportAttributeAccessIssue=false, reportUnusedCallResult=false
# 注: 以上规则抑制是因为 peewee ORM 缺少类型存根，所有方法链、
# 字段描述符访问、`dict[str, object]` 查询返回值都会产生误报。
import common.constants as constants
from common.schemas import (
    BacktestDailySchema,
    TradeRecordSchema,
)
from common.types import BacktestResult

from .models import (
    Backtest,
    BacktestDaily,
    BacktestParam,
    BacktestRecord,
    BacktestTrade,
    ExportMetadata,
    OperationLog,
    Run,
    RunStudy,
    SchemaInfo,
    TradeRecord,
    database,
)


def _f(val: Any) -> float:
    """安全转换 → float（Peewee .dicts() 返回 dict[str, Any]，值可能是 int/float/None）"""
    return float(val) if val is not None else 0.0


def _i(val: Any) -> int:
    """安全转换 → int"""
    return int(val) if val is not None else 0


def _normalize_max_dd(raw_value: float | None) -> float:
    """返回 max_drawdown 原值，仅做 None → 0.0 的安全转换

    【为什么存在这个函数】
    历史上有 bug: 把 vnpy 返回的绝对金额再除以 100 做"归一化"，导致 max_drawdown 被错误缩小 100 倍。
    这个函数作为语义标签存在: 明确告诉维护者"这里不能再做任何除法"，同时处理 None 输入。

    :param raw_value: vnpy 回测引擎返回的 max_drawdown（绝对金额，单位=合约货币）
    :return: 原值，None 时返回 0.0
    """
    if raw_value is None:
        return 0.0
    return float(raw_value)


class DataStore:
    """数据存储层 - 管理数据库连接和 CRUD 操作"""

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path: str = db_path
        database.init(
            db_path,
            pragmas={
                "journal_mode": "wal",
                "foreign_keys": 1,
            },
        )
        self._insert_count: int = 0
        self._init_tables()

    def _init_tables(self) -> None:
        """初始化数据库表 + 执行版本化迁移"""
        from . import schema as _schema

        database.create_tables(
            [
                Run,
                RunStudy,
                ExportMetadata,
                OperationLog,
                Backtest,
                BacktestParam,
                BacktestTrade,
                BacktestDaily,
                SchemaInfo,
            ],
            safe=True,
        )
        _schema.run_pending_migrations()

    def close(self) -> None:
        """关闭数据库连接"""
        if not database.is_closed():
            database.close()

    # ── 日志操作 ──────────────────────────────────────────

    def log(
        self,
        command: str,
        message: str,
        symbol: str | None = None,
        status: str = "INFO",
    ) -> None:
        """写入操作日志"""
        OperationLog.create(
            command=command,
            symbol=symbol,
            message=message,
            status=status,
            created_at=datetime.now(),
        )

        self._insert_count += 1
        if self._insert_count % constants.PRUNE_CHECK_INTERVAL == 0:
            self._prune_old_logs()
        total = OperationLog.select().count()
        if total >= constants.MAX_OPERATION_LOG_ROWS:
            self._prune_old_logs()

    def _prune_old_logs(self) -> int:
        """自动清理过旧日志，保留最近 MAX_OPERATION_LOG_ROWS 条"""
        try:
            max_rows = constants.MAX_OPERATION_LOG_ROWS
            total = OperationLog.select().count()
            if total <= max_rows - 1:
                return 0

            cutoff_id = (
                OperationLog.select(OperationLog.id)
                .order_by(OperationLog.id.desc())
                .offset(max_rows - 2)
                .limit(1)
                .scalar()
            )
            if cutoff_id is None:
                return 0

            deleted = OperationLog.delete().where(OperationLog.id < cutoff_id).execute()
            if deleted > 0:
                logger.info(f"操作日志自动清理: 删除 {deleted} 条旧记录")
            return int(deleted)
        except Exception as e:
            logger.warning(f"操作日志清理失败: {e}")
            return 0

    def get_logs(self, limit: int = 100) -> list[dict[str, object]]:
        """查询操作日志"""
        rows = list(OperationLog.select().order_by(OperationLog.id.desc()).limit(limit).dicts())
        for row in rows:
            for field in ["created_at", "updated_at"]:
                if row.get(field) is not None:
                    row[field] = str(row[field])
        return rows

    # ── 元数据操作 ────────────────────────────────────────

    def get_metadata(
        self,
        symbol: str,
        provider: str | None = None,
        interval: str | None = None,
    ) -> dict[str, object] | None:
        """查询品种元数据

        Args:
            symbol: 品种代码
            provider: 数据源过滤（可选），不传则返回最新一条
            interval: 周期过滤（可选）
        """
        try:
            query = ExportMetadata.select().where(ExportMetadata.symbol == symbol)
            if provider:
                query = query.where(ExportMetadata.provider == provider)
            if interval:
                query = query.where(ExportMetadata.interval == interval)
            row = query.order_by(ExportMetadata.id.desc()).limit(1).dicts()
            result = next(iter(row), None)
        except OperationalError as e:
            logger.debug(f"元数据表不可用，返回 None: {e}")
            return None

        if result:
            for field in ["start_date", "end_date", "min_dt", "max_dt", "created_at", "updated_at"]:
                if result.get(field) is not None:
                    result[field] = str(result[field])
        return result

    def upsert_metadata(
        self,
        symbol: str,
        provider: str,
        interval: str,
        filepath: str,
        start_date: str,
        end_date: str,
        min_dt: str,
        max_dt: str,
        total_rows: int,
    ) -> None:
        """插入或更新元数据（按 symbol+provider+interval 匹配）"""
        now = datetime.now()
        row, created = ExportMetadata.get_or_create(
            symbol=symbol,
            provider=provider,
            interval=interval,
            defaults=dict(
                filepath=filepath,
                start_date=start_date,
                end_date=end_date,
                min_dt=min_dt,
                max_dt=max_dt,
                total_rows=total_rows,
                created_at=now,
                updated_at=now,
            ),
        )
        if not created:
            ExportMetadata.update(
                filepath=filepath,
                start_date=start_date,
                end_date=end_date,
                min_dt=min_dt,
                max_dt=max_dt,
                total_rows=total_rows,
                updated_at=now,
            ).where(ExportMetadata.id == row.id).execute()

    # ── 运行记录 ──────────────────────────────────────────

    def create_run(
        self,
        strategy: str,
        engine: str,
        symbols: int,
        use_fixed_seed: bool = False,
        random_seed: int | None = None,
    ) -> int:
        """创建一次批量回测运行记录，返回 run_id"""
        r = Run.create(
            strategy=strategy,
            engine=engine,
            symbols=symbols,
            use_fixed_seed=1 if use_fixed_seed else 0,
            random_seed=random_seed,
        )
        return int(r.id)

    def finish_run(self, run_id: int, status: str = "success") -> None:
        """标记运行完成"""
        Run.update(status=status).where(Run.id == run_id).execute()

    def link_study(self, run_id: int, study_name: str) -> None:
        """关联 run 与 Optuna study"""
        RunStudy.get_or_create(run_id=run_id, study_name=study_name)

    def update_run_seed(self, run_id: int, use_fixed_seed: bool, random_seed: int) -> None:
        """更新运行记录的随机种子"""
        Run.update(
            use_fixed_seed=1 if use_fixed_seed else 0,
            random_seed=random_seed,
        ).where(Run.id == run_id).execute()

    # ── 回测记录操作 ─────────────────────────────────────

    def insert_backtest_detailed(
        self,
        result: BacktestResult,
        run_id: int | None = None,
        data_src: str | None = None,
    ) -> int:
        """插入完整的回测记录

        通过 `_build_backtest_fields` 统一构造字段，消除更新/新建分支的重复赋值。
        """
        now = datetime.now()
        fields = self._build_backtest_fields(result, now, data_src)
        if run_id is not None:
            fields["run"] = run_id

        if result.backtest_id:
            bt = Backtest.get_by_id(result.backtest_id)
            for key, value in fields.items():
                setattr(bt, key, value)
            bt.save()
        else:
            bt = Backtest.create(**fields)

        # 写入参数（更新时先删旧参数再插入，避免重复）
        params = result.strategy_params
        if params:
            if result.backtest_id:
                BacktestParam.delete().where(BacktestParam.backtest == bt).execute()
            for name, value in params.items():
                BacktestParam.create(backtest=bt, param_name=name, param_value=float(value))
        return int(bt.id)

    def _build_backtest_fields(
        self,
        result: BacktestResult,
        now: datetime,
        data_src: str | None,
    ) -> dict[str, Any]:
        """统一构造 Backtest 记录的字段字典

        消除 insert_backtest_detailed 中更新/新建分支的 60+ 行重复赋值。
        """
        fields: dict[str, Any] = dict(
            symbol=result.symbol,
            strategy=result.strategy,
            strategy_version=result.strategy_version,
            git_hash=result.git_hash,
            status=result.status,
            error_message=result.error_message,
            start_date=result.start_date,
            end_date=result.end_date,
            total_days=result.total_days,
            initial_capital=result.initial_capital,
            commission_rate=result.commission_rate,
            slippage=result.slippage,
            price_tick=result.price_tick,
            contract_size=result.contract_size,
            kline_interval=result.kline_interval,
            end_balance=result.end_balance,
            total_return=result.total_return,
            annual_return=result.annual_return,
            total_trades=result.total_trades,
            win_trades=result.win_trades,
            loss_trades=result.loss_trades,
            win_rate=result.win_rate,
            max_consecutive_win=result.max_consecutive_win,
            max_consecutive_loss=result.max_consecutive_loss,
            avg_win=result.avg_win,
            avg_loss=result.avg_loss,
            win_loss_ratio=result.win_loss_ratio,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=_normalize_max_dd(result.max_drawdown),
            max_ddpercent=result.max_ddpercent,
            max_drawdown_duration=result.max_drawdown_duration or 0,
            daily_std=result.daily_std,
            return_drawdown_ratio=result.return_drawdown_ratio,
            total_net_pnl=result.total_net_pnl,
            daily_net_pnl=result.daily_net_pnl,
            total_commission=result.total_commission,
            daily_commission=result.daily_commission,
            total_slippage=result.total_slippage,
            daily_slippage=result.daily_slippage,
            total_turnover=result.total_turnover,
            daily_turnover=result.daily_turnover,
            profit_days=result.profit_days,
            loss_days=result.loss_days,
            daily_trade_count=result.daily_trade_count,
            daily_return_pct=result.daily_return_pct,
            ewm_sharpe=result.ewm_sharpe,
            rgr_ratio=result.rgr_ratio,
            engine_config=json.dumps(result.engine_config) if result.engine_config else None,
            data_src=data_src or result.data_src,
            updated_at=now,
        )
        if result.backtest_id is None:
            fields["run"] = None
        return fields

    def insert_backtest_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> int:
        """批量插入交易明细

        输入 trades 字段名必须与 ORM BacktestTrade 对齐:
            datetime, symbol, direction, offset,
            open_price, close_price, quantity, pnl, commission
        """
        now = datetime.now()
        rows: list[dict[str, object]] = []

        for trade in trades:
            rows.append(
                {
                    "backtest_id": backtest_id,
                    "symbol": str(trade["symbol"]),
                    "datetime": trade["datetime"],
                    "direction": str(trade["direction"]).lower(),
                    "offset": str(trade.get("offset", "open")).lower(),
                    "open_price": _f(trade["open_price"]),
                    "close_price": _f(trade["close_price"]),
                    "quantity": _f(trade["quantity"]),
                    "pnl": _f(trade.get("pnl", 0.0)),
                    "commission": _f(trade.get("commission", 0.0)),
                    "reason": str(trade.get("reason", "")),
                    "created_at": now,
                }
            )

        if not rows:
            return 0

        # Pandera 验证
        try:
            trades_df = pd.DataFrame(rows)
            trades_df["datetime"] = pd.to_datetime(trades_df["datetime"])
            TradeRecordSchema.validate(trades_df)
        except pa.errors.SchemaError as e:
            logger.error(f"交易记录验证失败 [bt={backtest_id}]: {e}")
            raise
        except Exception as e:
            logger.warning(f"交易记录验证跳过 [bt={backtest_id}]: {e}")

        with database.atomic():
            BacktestTrade.insert_many(rows).execute()
        return len(rows)

    def query_backtests(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        status: str = "success",
        limit: int = 50,
    ) -> list[BacktestRecord]:
        """查询回测记录"""
        query = Backtest.select().where(Backtest.status == status)

        if symbol:
            query = query.where(Backtest.symbol == symbol)
        if strategy:
            query = query.where(Backtest.strategy == strategy)

        results_raw = query.order_by(Backtest.created_at.desc()).limit(limit).dicts()
        results = list(results_raw)

        records = []
        for row in results:
            row["created_at"] = str(row.get("created_at", ""))
            records.append(BacktestRecord(**row))
        return records

    def get_backtest(self, backtest_id: int) -> BacktestRecord | None:
        """查询单条回测记录"""
        row = Backtest.select().where(Backtest.id == backtest_id).dicts()
        result = next(iter(row), None)
        if result:
            result["created_at"] = str(result.get("created_at", ""))
            return BacktestRecord(**result)
        return None

    def query_trades(self, backtest_id: int) -> list[TradeRecord]:
        """查询交易明细"""
        rows = list(
            BacktestTrade.select()
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.datetime.asc())
            .dicts()
        )

        records = []
        for row in rows:
            for dt_field in ("datetime", "created_at"):
                if row.get(dt_field) is not None:
                    row[dt_field] = str(row[dt_field])
            row["backtest_id"] = row.pop("backtest_id") if "backtest_id" in row else backtest_id
            records.append(TradeRecord(**row))
        return records

    def insert_backtest_daily(self, backtest_id: int, daily_results: list[dict[str, object]]) -> int:
        """批量插入每日资金曲线数据"""
        now = datetime.now()
        rows: list[dict[str, object]] = []
        peak: float = 0.0

        for daily in daily_results:
            dt = daily.get("date", daily.get("datetime"))
            if not dt:
                continue
            date_str = str(dt).split(" ")[0] if " " in str(dt) else str(dt).split("T")[0]

            net_pnl = _f(daily.get("net_pnl", daily.get("daily_return", 0.0)))
            equity = _f(daily.get("balance", daily.get("equity", 0.0)))
            if equity > peak:
                peak = equity
            drawdown = (equity - peak) / peak if peak > 0 else 0.0

            rows.append(
                {
                    "backtest_id": backtest_id,
                    "date": date_str,
                    "equity": equity,
                    "daily_return": net_pnl,
                    "drawdown": drawdown,
                    "turnover": _f(daily.get("turnover", 0.0) or 0),
                    "commission": _f(daily.get("commission", 0.0) or 0),
                    "slippage": _f(daily.get("slippage", 0.0) or 0),
                    "trade_count": _i(daily.get("trade_count", 0) or 0),
                    "created_at": now,
                }
            )

        if not rows:
            return 0

        try:
            daily_df = pd.DataFrame(rows)
            daily_df["date"] = pd.to_datetime(daily_df["date"])
            BacktestDailySchema.validate(daily_df)
        except pa.errors.SchemaError as e:
            logger.error(f"每日资金曲线验证失败 [bt={backtest_id}]: {e}")
            raise
        except Exception as e:
            logger.warning(f"每日资金曲线验证跳过 [bt={backtest_id}]: {e}")

        with database.atomic():
            BacktestDaily.insert_many(rows).execute()
        return len(rows)

    def query_daily(self, backtest_id: int) -> list[dict[str, object]]:
        """查询每日资金曲线"""
        rows = list(
            BacktestDaily.select()
            .where(BacktestDaily.backtest_id == backtest_id)
            .order_by(BacktestDaily.date.asc())
            .dicts()
        )

        results = []
        for row in rows:
            results.append(
                {
                    "date": str(row.get("date", "")),
                    "equity": row.get("equity", 0),
                    "daily_return": row.get("daily_return", 0),
                    "drawdown": row.get("drawdown", 0),
                    "turnover": row.get("turnover"),
                    "commission": row.get("commission"),
                    "slippage": row.get("slippage"),
                    "trade_count": row.get("trade_count"),
                }
            )
        return results

    def get_run_info(self, run_id: int) -> dict[str, object] | None:
        """获取运行信息"""
        row = Run.select().where(Run.id == run_id).dicts()
        result = next(iter(row), None)
        if result:
            for field in ["created_at", "updated_at"]:
                if result.get(field) is not None:
                    result[field] = str(result[field])
            if "use_fixed_seed" in result:
                result["use_fixed_seed"] = bool(result["use_fixed_seed"])
        return result

    def get_all_runs(self) -> list[dict[str, object]]:
        """获取所有运行记录"""
        rows = list(
            Run.select(
                Run.id,
                Run.strategy,
                Run.engine,
                Run.symbols,
                Run.status,
                Run.created_at,
                Run.use_fixed_seed,
                Run.random_seed,
            )
            .order_by(Run.id.desc())
            .dicts()
        )
        result = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "strategy": r["strategy"],
                    "engine": r["engine"],
                    "symbols": r["symbols"],
                    "status": r["status"],
                    "created": str(r["created_at"]),
                    "use_fixed_seed": bool(r["use_fixed_seed"]),
                    "random_seed": r["random_seed"],
                }
            )
        return result

    # ── 业务聚合查询 ─────────────────────────────────────

    def _filter_by_best_trial(self, backtests: list[dict[str, Any]], run_id: int) -> list[dict[str, Any]]:
        """过滤出全局最优 trial 对应的回测记录

        【设计意图】
        一个 run 通常会跑多组参数（Optuna trial），报告应展示"最优参数在各品种上的表现"。
        通过读取 Backtest.engine_config 中的 trial_index，筛选出 trial 编号等于 get_best_trial_index() 的记录。

        【回退策略 — 重要】
        - 若 best_trial <= 0（未找到优化记录）→ 原样返回全部（退化为"每个品种取自己最优"）
        - 若过滤后得到空列表 → 原样返回全部（避免报告空白），但记录一条 warning 方便排查
        """
        best_trial = self.get_best_trial_index(run_id)
        if best_trial <= 0:
            return backtests

        filtered: list[dict[str, Any]] = []
        for bt in backtests:
            ec = bt.get("engine_config")
            if isinstance(ec, str):
                try:
                    cfg = json.loads(ec)
                except Exception:
                    continue
            else:
                cfg = ec
            if cfg.get("trial_index") == best_trial:
                filtered.append(bt)

        if not filtered:
            logger.warning(
                "run=%d 最优 trial=%d 在回测记录中找不到匹配，将展示全部记录（可能是 engine_config 未写入 trial_index）",
                run_id,
                best_trial,
            )
            return backtests
        return filtered

    def get_run_summary(self, run_id: int) -> list[dict[str, object]]:
        """获取每品种最优回测记录（仅全局最优参数组合）"""
        rows = list(
            Backtest.select(
                Backtest.id,
                Backtest.symbol,
                Backtest.total_return,
                Backtest.total_trades,
                Backtest.win_rate,
                Backtest.win_loss_ratio,
                Backtest.annual_return,
                Backtest.max_drawdown,
                Backtest.max_ddpercent,
                Backtest.sharpe_ratio,
                Backtest.end_balance,
                Backtest.total_net_pnl,
                Backtest.total_commission,
                Backtest.total_slippage,
                Backtest.profit_days,
                Backtest.loss_days,
                Backtest.ewm_sharpe,
                Backtest.rgr_ratio,
                Backtest.data_src,
                Backtest.start_date,
                Backtest.end_date,
                Backtest.kline_interval,
                Backtest.engine_config,
            )
            .where(Backtest.run_id == run_id, Backtest.status == "success")
            .order_by(Backtest.symbol, Backtest.total_return.desc())
            .dicts()
        )

        rows = self._filter_by_best_trial(rows, run_id)

        best: dict[str, dict[str, object]] = {}
        for r in rows:
            self._update_best_for_symbol(best, r)
        return [best[s] for s in sorted(best)]

    def _update_best_for_symbol(self, best: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        """为单个品种维护最高收益的回测摘要

        作为 `get_run_summary` 中的循环体抽离，便于阅读和测试。
        """
        sym = str(row["symbol"])
        total_return = _f(row["total_return"] or 0)
        if sym not in best or total_return > _f(best[sym].get("total_return") or 0):
            best[sym] = {
                "id": row["id"],
                "symbol": sym,
                "total_return": total_return,
                "total_trades": row["total_trades"] or 0,
                "win_rate": _f(row["win_rate"] or 0) * 100,
                "win_loss_ratio": _f(row["win_loss_ratio"] or 0),
                "annual_return": _f(row["annual_return"] or 0),
                "max_drawdown": _f(row["max_drawdown"] or 0),
                "max_ddpercent": _f(row["max_ddpercent"] or 0),
                "sharpe": _f(row["sharpe_ratio"] or 0),
                "end_balance": _f(row["end_balance"] or 0),
                "total_net_pnl": _f(row["total_net_pnl"] or 0),
                "total_commission": _f(row["total_commission"] or 0),
                "total_slippage": _f(row["total_slippage"] or 0),
                "profit_days": row["profit_days"] or 0,
                "loss_days": row["loss_days"] or 0,
                "ewm_sharpe": _f(row["ewm_sharpe"] or 0),
                "rgr_ratio": _f(row["rgr_ratio"] or 0),
                "ret_cls": "badge-green" if total_return > 0 else "badge-red",
                "sr_cls": "badge-green" if _f(row["sharpe_ratio"] or 0) > 0 else "badge-red",
                "data_src": row["data_src"],
                "start_date": row["start_date"],
                "end_date": row["end_date"],
                "kline_interval": row["kline_interval"],
            }

    def get_backtests_for_run(self, run_id: int) -> list[dict[str, object]]:
        """获取某 run 下所有回测记录（含参数和日线数据，仅全局最优参数组合）"""
        backtests = list(Backtest.select().where(Backtest.run_id == run_id, Backtest.status == "success").dicts())

        backtests = self._filter_by_best_trial(backtests, run_id)

        result = []
        for bt in backtests:
            bt_id = _i(bt["id"])

            params = list(
                BacktestParam.select(BacktestParam.param_name, BacktestParam.param_value)
                .where(BacktestParam.backtest == bt_id)
                .order_by(BacktestParam.param_name)
                .dicts()
            )

            daily = self.query_daily(bt_id)

            result.append(
                {
                    "id": bt_id,
                    "symbol": bt["symbol"],
                    "strategy": bt["strategy"],
                    "status": bt["status"],
                    "start_date": bt["start_date"],
                    "end_date": bt["end_date"],
                    "initial_capital": bt["initial_capital"],
                    "end_balance": bt["end_balance"],
                    "total_return": _f(bt["total_return"] or 0),
                    "sharpe_ratio": _f(bt["sharpe_ratio"] or 0),
                    "max_drawdown": _f(bt["max_drawdown"] or 0),
                    "max_ddpercent": _f(bt["max_ddpercent"] or 0),
                    "win_rate": _f(bt["win_rate"] or 0) * 100,
                    "total_trades": bt["total_trades"] or 0,
                    "total_net_pnl": _f(bt["total_net_pnl"] or 0),
                    "daily_net_pnl": _f(bt["daily_net_pnl"] or 0),
                    "total_commission": _f(bt["total_commission"] or 0),
                    "daily_commission": _f(bt["daily_commission"] or 0),
                    "total_slippage": _f(bt["total_slippage"] or 0),
                    "daily_slippage": _f(bt["daily_slippage"] or 0),
                    "total_turnover": _f(bt["total_turnover"] or 0),
                    "daily_turnover": _f(bt["daily_turnover"] or 0),
                    "profit_days": bt["profit_days"] or 0,
                    "loss_days": bt["loss_days"] or 0,
                    "daily_trade_count": _f(bt["daily_trade_count"] or 0),
                    "daily_return_pct": _f(bt["daily_return_pct"] or 0),
                    "ewm_sharpe": _f(bt["ewm_sharpe"] or 0),
                    "rgr_ratio": _f(bt["rgr_ratio"] or 0),
                    "data_src": bt["data_src"],
                    "kline_interval": bt["kline_interval"],
                    "strategy_version": bt["strategy_version"],
                    "git_hash": bt["git_hash"],
                    "params": [{"name": p["param_name"], "value": p["param_value"]} for p in params],
                    "daily": daily,
                }
            )
        return result

    def get_best_trial_index(self, run_id: int) -> int:
        """获取最优 trial 在引擎配置中的编号（用于 trades.json 导出过滤）"""
        try:
            rows = list(
                database.execute_sql(
                    "SELECT t.number FROM trials t "
                    "JOIN trial_values tv ON t.trial_id = tv.trial_id "
                    "WHERE t.study_id=(SELECT s.study_id FROM studies s "
                    "  JOIN run_studies rs ON rs.study_name=s.study_name "
                    "  WHERE rs.run_id=?) "
                    "AND t.state='COMPLETE' "
                    "ORDER BY tv.value DESC LIMIT 1",
                    (run_id,),
                )
            )
            if rows:
                return int(rows[0][0])
        except Exception:
            pass
        return 0

    def get_equity_data(self, backtest_id: int) -> dict[str, object] | None:
        """获取指定回测记录的资金曲线数据"""
        rows = self.query_daily(backtest_id)
        if not rows:
            return None

        return {
            "dates": [r["date"] for r in rows],
            "equity": [_f(r["equity"]) for r in rows],
            "drawdown": [_f(r["drawdown"]) for r in rows],
        }

    def get_optuna_data(self, run_id: int) -> dict[str, object] | None:
        """获取 Optuna 优化数据

        内部拆出 `_query_trial_stats` / `_query_param_rows` / `_query_best_params`
        三个小方法，避免主函数的 SQL 字符串和处理逻辑混合在一起。
        """
        study_rows = list(RunStudy.select(RunStudy.study_name).where(RunStudy.run_id == run_id).dicts())
        if not study_rows:
            return None

        study_name = study_rows[0]["study_name"]

        direction_row = self._query_study_direction(study_name)
        is_maximize = direction_row and direction_row[0][0] == "MAXIMIZE"
        agg_func = "MAX" if is_maximize else "MIN"

        trial_nums, trial_values = self._query_trial_stats(study_name)
        params_rows = self._query_param_rows(study_name)
        best = self._query_best_params(study_name, agg_func)

        param_names = sorted(set(p[1] for p in params_rows))
        param_scatter = None
        if len(param_names) >= 2:
            p1, p2 = param_names[0], param_names[1]
            param_scatter = {
                "x_label": p1,
                "y_label": p2,
                "x_vals": [_f(p[2]) for p in params_rows if p[1] == p1],
                "y_vals": [_f(p[2]) for p in params_rows if p[1] == p2],
                "scores": trial_values,
            }

        return {
            "study_name": study_name,
            "trial_count": len(trial_nums),
            "trial_nums": trial_nums,
            "trial_values": trial_values,
            "best_params": [{"name": p[0], "value": _f(p[1])} for p in best],
            "param_scatter": param_scatter,
            "report_file": f"optimization_{study_name}.html",
        }

    def _query_study_direction(self, study_name: str) -> list[tuple[Any, ...]]:
        return list(
            database.execute_sql(
                "SELECT direction FROM study_directions "
                "WHERE study_id=(SELECT study_id FROM studies WHERE study_name=?)",
                (study_name,),
            )
        )

    def _query_trial_stats(self, study_name: str) -> tuple[list[int], list[float]]:
        rows = list(
            database.execute_sql(
                "SELECT t.number, tv.value FROM trials t "
                "LEFT JOIN trial_values tv ON t.trial_id = tv.trial_id "
                "WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?) "
                "AND t.state='COMPLETE' "
                "ORDER BY t.number",
                (study_name,),
            )
        )
        nums = [r[0] for r in rows]
        values = [_f(r[1] or 0) for r in rows]
        return nums, values

    def _query_param_rows(self, study_name: str) -> list[tuple[Any, ...]]:
        return list(
            database.execute_sql(
                "SELECT t.number, tp.param_name, tp.param_value "
                "FROM trials t JOIN trial_params tp ON t.trial_id = tp.trial_id "
                "WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?) "
                "AND t.state='COMPLETE' "
                "ORDER BY t.number, tp.param_name",
                (study_name,),
            )
        )

    def _query_best_params(self, study_name: str, agg_func: str) -> list[tuple[Any, ...]]:
        return list(
            database.execute_sql(
                f"""
                SELECT tp.param_name, tp.param_value FROM trial_params tp
                JOIN trial_values tv ON tp.trial_id = tv.trial_id
                JOIN trials t ON t.trial_id = tp.trial_id
                WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?)
                  AND tv.value=(
                      SELECT {agg_func}(tv2.value) FROM trial_values tv2
                      JOIN trials t2 ON tv2.trial_id=t2.trial_id
                      WHERE t2.study_id=(SELECT study_id FROM studies WHERE study_name=?))
                """,
                (study_name, study_name),
            )
        )

    def delete_backtest(self, backtest_id: int) -> bool:
        """硬删除回测记录及其关联的交易明细和每日资金曲线

        Args:
            backtest_id: 回测记录 ID

        Returns:
            是否成功删除
        """
        try:
            bt = Backtest.get_or_none(Backtest.id == backtest_id)
            if bt is None:
                logger.warning(f"回测记录不存在 id={backtest_id}")
                return False
            with database.atomic():
                BacktestDaily.delete().where(BacktestDaily.backtest_id == backtest_id).execute()
                BacktestTrade.delete().where(BacktestTrade.backtest_id == backtest_id).execute()
                bt.delete_instance()
            logger.info(f"已删除回测记录 id={backtest_id} 及其关联数据")
            return True
        except Exception as e:
            logger.error(f"删除回测记录失败 id={backtest_id}: {e}")
            return False
