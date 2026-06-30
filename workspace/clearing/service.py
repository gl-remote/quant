"""回测成交清算服务。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

import pandas as pd
from common.contract_specs import BROKER_ADDON_DFCF, CONTRACT_SPECS, ContractSpec
from data.models import TradeRecord
from loguru import logger


class ClearingDataManager(Protocol):
    def get_backtests_for_clearing(self, run_id: int) -> list[dict[str, object]]: ...

    def query_trades(self, backtest_id: int) -> list[TradeRecord]: ...

    def replace_clearing_outputs(
        self,
        backtest_id: int,
        clearing_rows: list[dict[str, object]],
        account_ledger_rows: list[dict[str, object]],
        position_ledger_rows: list[dict[str, object]],
        summary_fields: dict[str, object],
    ) -> None: ...


@dataclass
class OpenLot:
    trade_id: int
    symbol: str
    direction: str
    open_time: datetime
    price: float
    remaining: float
    reason: str
    decision_payload: dict[str, object] | None = None


@dataclass
class CostSpec:
    size: float
    price_tick: float
    spec: ContractSpec | None


class BacktestClearingService:
    """基于 backtest_trades 和 K 线生成清算结果。"""

    def __init__(self, dm: ClearingDataManager) -> None:
        self._dm: ClearingDataManager = dm

    def clear_run(self, run_id: int) -> None:
        backtests = self._dm.get_backtests_for_clearing(run_id)
        for backtest in backtests:
            self.clear_backtest(backtest)

    def clear_backtest(self, backtest: dict[str, object]) -> None:
        backtest_id = _int_field(backtest, "id")
        trades = self._dm.query_trades(backtest_id)
        bars = self._load_bars(backtest)
        rows = self._build_clearings(backtest, trades, bars)
        account_ledger_rows = self._build_account_ledger(backtest, rows)
        position_ledger_rows = self._build_position_ledger(backtest, trades, rows)
        summary = self._build_summary(backtest, rows)
        self._dm.replace_clearing_outputs(backtest_id, rows, account_ledger_rows, position_ledger_rows, summary)
        logger.info("清算完成 backtest_id={} clearings={}", backtest_id, len(rows))

    def _load_bars(self, backtest: dict[str, object]) -> pd.DataFrame:
        data_src = backtest.get("data_src")
        if not data_src:
            return pd.DataFrame()
        path = Path(str(data_src))
        if not path.exists():
            logger.warning("清算 K 线数据不存在: {}", path)
            return pd.DataFrame()
        df = pd.read_csv(path)
        if "datetime" not in df.columns:
            logger.warning("清算 K 线缺少 datetime: {}", path)
            return pd.DataFrame()
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df.sort_values("datetime").reset_index(drop=True)

    def _build_clearings(
        self,
        backtest: dict[str, object],
        trades: list[TradeRecord],
        bars: pd.DataFrame,
    ) -> list[dict[str, object]]:
        cost_spec = self._resolve_cost_spec(backtest)
        open_lots: dict[str, list[OpenLot]] = {"long": [], "short": []}
        rows: list[dict[str, object]] = []

        for trade in trades:
            offset = str(trade.offset).lower()
            direction = str(trade.direction).lower()
            if offset == "open":
                open_lots.setdefault(direction, []).append(
                    OpenLot(
                        trade_id=int(trade.id or 0),
                        symbol=str(trade.symbol),
                        direction=direction,
                        open_time=pd.Timestamp(trade.datetime).to_pydatetime(),
                        price=float(trade.price),
                        remaining=float(trade.quantity),
                        reason=str(trade.reason or ""),
                        decision_payload=_parse_decision_payload(trade.decision_payload_json),
                    )
                )
                continue

            position_direction = "long" if direction == "short" else "short"
            rows.extend(
                self._consume_lots(
                    backtest=backtest,
                    open_lots=open_lots.setdefault(position_direction, []),
                    close_trade=trade,
                    close_time=pd.Timestamp(trade.datetime).to_pydatetime(),
                    close_price=float(trade.price),
                    close_reason=str(trade.reason or ""),
                    close_trade_id=int(trade.id or 0),
                    position_direction=position_direction,
                    cost_spec=cost_spec,
                    forced_reason=None,
                    close_payload=_parse_decision_payload(trade.decision_payload_json),
                    bars=bars,
                )
            )

        if not bars.empty:
            last_bar = bars.iloc[-1]
            last_datetime = str(cast(object, last_bar.loc["datetime"]))
            last_close = str(cast(object, last_bar.loc["close"]))
            close_time = pd.Timestamp(last_datetime).to_pydatetime()
            close_price = float(last_close)
            for position_direction, lots in open_lots.items():
                rows.extend(
                    self._consume_lots(
                        backtest=backtest,
                        open_lots=lots,
                        close_trade=None,
                        close_time=close_time,
                        close_price=close_price,
                        close_reason="forced_close_at_backtest_end",
                        close_trade_id=None,
                        position_direction=position_direction,
                        cost_spec=cost_spec,
                        forced_reason="forced_close_at_backtest_end",
                        close_payload=None,
                        bars=bars,
                    )
                )

        if any(lot.remaining > 0 for lots in open_lots.values() for lot in lots):
            logger.warning("backtest_id={} 存在未清算持仓且无法强平", backtest.get("id"))
        return rows

    def _consume_lots(
        self,
        *,
        backtest: dict[str, object],
        open_lots: list[OpenLot],
        close_trade: TradeRecord | None,
        close_time: datetime,
        close_price: float,
        close_reason: str,
        close_trade_id: int | None,
        position_direction: str,
        cost_spec: CostSpec,
        forced_reason: str | None,
        close_payload: dict[str, object] | None = None,
        bars: pd.DataFrame | None = None,
    ) -> list[dict[str, object]]:
        remaining = float(close_trade.quantity) if close_trade is not None else sum(lot.remaining for lot in open_lots)

        rows: list[dict[str, object]] = []
        backtest_id = _int_field(backtest, "id")
        while remaining > 0 and open_lots:
            lot = open_lots[0]
            volume = min(remaining, lot.remaining)
            gross_pnl = self._gross_pnl(position_direction, lot.price, close_price, volume, cost_spec.size)
            commission = self._commission(lot.price, volume, cost_spec) + self._commission(
                close_price, volume, cost_spec
            )
            slippage_cost = self._slippage_cost(volume, cost_spec) * 2
            net_pnl = gross_pnl - commission - slippage_cost
            mae, mfe, holding_bars = self._price_excursion(
                bars, lot.open_time, close_time, lot.price, position_direction
            )
            diagnostics = self._collect_diagnostics(
                backtest_id=backtest_id,
                open_payload=lot.decision_payload,
                close_payload=close_payload,
                forced_reason=forced_reason,
            )
            rows.append(
                {
                    "backtest_id": backtest_id,
                    "run_id": backtest.get("run"),
                    "symbol": lot.symbol,
                    "open_trade_id": lot.trade_id or None,
                    "close_trade_id": close_trade_id,
                    "source_trade_ids": json.dumps(
                        [tid for tid in (lot.trade_id or None, close_trade_id) if tid is not None],
                        ensure_ascii=False,
                    ),
                    "direction": position_direction,
                    "volume": volume,
                    "open_time": lot.open_time,
                    "close_time": close_time,
                    "open_price": lot.price,
                    "close_price": close_price,
                    "contract_multiplier": cost_spec.size,
                    "price_tick": cost_spec.price_tick,
                    "gross_pnl": gross_pnl,
                    "commission": commission,
                    "slippage_cost": slippage_cost,
                    "net_pnl": net_pnl,
                    "open_reason": lot.reason,
                    "close_reason": close_reason,
                    "holding_seconds": (close_time - lot.open_time).total_seconds(),
                    "holding_bars": holding_bars,
                    "is_forced_close": forced_reason is not None,
                    "forced_close_reason": forced_reason,
                    "exit_reason": self._resolve_exit_reason(diagnostics, forced_reason),
                    "mae": mae,
                    "mfe": mfe,
                    "diagnostics_json": json.dumps(diagnostics, ensure_ascii=False) if diagnostics else None,
                    "created_at": datetime.now(),
                }
            )
            remaining -= volume
            lot.remaining -= volume
            if lot.remaining <= 0:
                open_lots.pop(0)

        if remaining > 0:
            logger.warning(
                "backtest_id={} 平仓有余量未配对 direction={} remaining={}",
                backtest.get("id"),
                position_direction,
                remaining,
            )
        return rows

    # 推荐字段：策略族应填的诊断字段，缺失时打 warning（见 strategies/core/diagnostics/*.py）。
    _RECOMMENDED_ALPHA: tuple[str, ...] = ("strict_failure_boundary", "expected_profit_boundary")
    _RECOMMENDED_RISK: tuple[str, ...] = ("strict_failure_distance", "raw_account_r_multiple")

    def _collect_diagnostics(
        self,
        *,
        backtest_id: int,
        open_payload: dict[str, object] | None,
        close_payload: dict[str, object] | None,
        forced_reason: str | None,
    ) -> dict[str, object]:
        """汇总开仓/平仓 decision_payload 的三层诊断，原样透传供报告层解析。

        alpha / risk 在开仓时决策，取开仓成交载荷；execution 在平仓时决策，取平仓
        成交载荷。缺推荐字段时打 warning（报告层假设策略已按推荐字段填充）。
        """
        open_diag = _payload_diagnostics(open_payload)
        close_diag = _payload_diagnostics(close_payload)
        alpha = _layer_dict(open_diag.get("alpha"))
        risk = _layer_dict(open_diag.get("risk"))
        execution = _layer_dict(close_diag.get("execution")) or _layer_dict(open_diag.get("execution"))

        if not _is_real(alpha) and forced_reason is None:
            logger.warning("backtest_id={} 清算成交缺 alpha 诊断（开仓未填结构候选）", backtest_id)
        if not _is_real(risk) and forced_reason is None:
            logger.warning("backtest_id={} 清算成交缺 risk 诊断（开仓未填风险预算）", backtest_id)
        self._warn_missing_fields(backtest_id, "alpha", alpha, self._RECOMMENDED_ALPHA, forced_reason)
        self._warn_missing_fields(backtest_id, "risk", risk, self._RECOMMENDED_RISK, forced_reason)

        diagnostics: dict[str, object] = {}
        if _is_real(alpha):
            diagnostics["alpha"] = alpha
        if _is_real(risk):
            diagnostics["risk"] = risk
        if _is_real(execution):
            diagnostics["execution"] = execution
        return diagnostics

    @staticmethod
    def _warn_missing_fields(
        backtest_id: int,
        layer: str,
        fields: dict[str, object],
        recommended: tuple[str, ...],
        forced_reason: str | None,
    ) -> None:
        if forced_reason is not None or not _is_real(fields):
            return
        missing = [name for name in recommended if name not in fields]
        if missing:
            logger.warning("backtest_id={} {} 诊断缺推荐字段: {}", backtest_id, layer, missing)

    @staticmethod
    def _resolve_exit_reason(diagnostics: dict[str, object], forced_reason: str | None) -> str | None:
        """退出原因枚举：优先 execution.exit_reason，其次强平标记。"""
        if forced_reason is not None:
            return "forced_close"
        execution = diagnostics.get("execution")
        if isinstance(execution, dict):
            value = execution.get("exit_reason")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _price_excursion(
        bars: pd.DataFrame | None,
        open_time: datetime,
        close_time: datetime,
        open_price: float,
        position_direction: str,
    ) -> tuple[float | None, float | None, int | None]:
        """从持仓区间 K 线派生 MAE / MFE（价格口径）与持仓 K 线数。

        MAE = 最大不利价格偏移（>=0），MFE = 最大有利价格偏移（>=0）。
        long 有利方向向上，short 有利方向向下。
        """
        if bars is None or bars.empty or "datetime" not in bars.columns:
            return None, None, None
        mask = (bars["datetime"] >= pd.Timestamp(open_time)) & (bars["datetime"] <= pd.Timestamp(close_time))
        window = bars.loc[mask]
        if window.empty:
            return None, None, 0
        highs = window["high"].astype(float) if "high" in window.columns else window["close"].astype(float)
        lows = window["low"].astype(float) if "low" in window.columns else window["close"].astype(float)
        max_high = float(highs.max())
        min_low = float(lows.min())
        if position_direction == "long":
            mfe = max(0.0, max_high - open_price)
            mae = max(0.0, open_price - min_low)
        else:
            mfe = max(0.0, open_price - min_low)
            mae = max(0.0, max_high - open_price)
        return mae, mfe, int(len(window))

    @staticmethod
    def _gross_pnl(direction: str, open_price: float, close_price: float, volume: float, size: float) -> float:
        price_diff = close_price - open_price
        if direction == "short":
            price_diff = -price_diff
        return price_diff * volume * size

    def _resolve_cost_spec(self, backtest: dict[str, object]) -> CostSpec:
        symbol = str(backtest["symbol"])
        spec = CONTRACT_SPECS.get_symbol(symbol)
        if spec is not None:
            return CostSpec(size=float(spec.size), price_tick=float(spec.tick), spec=spec)
        return CostSpec(
            size=_float_field(backtest, "contract_size", 1.0),
            price_tick=_float_field(backtest, "price_tick", 0.0),
            spec=None,
        )

    @staticmethod
    def _commission(price: float, volume: float, cost_spec: CostSpec) -> float:
        if cost_spec.spec is None:
            return 0.0
        lots = int(volume)
        return cost_spec.spec.total_commission(price=price, lots=lots, broker_addon=BROKER_ADDON_DFCF)

    @staticmethod
    def _slippage_cost(volume: float, cost_spec: CostSpec) -> float:
        if cost_spec.spec is not None:
            lots = int(volume)
            return float(cost_spec.spec.slippage(lots=lots))
        return volume * cost_spec.size * cost_spec.price_tick

    @staticmethod
    def _build_account_ledger(backtest: dict[str, object], rows: list[dict[str, object]]) -> list[dict[str, object]]:
        backtest_id = _int_field(backtest, "id")
        run_id = backtest.get("run")
        initial_capital = _float_field(backtest, "initial_capital", 0.0)
        event_time = _first_event_time(rows)
        ledger_rows: list[dict[str, object]] = [
            {
                "backtest_id": backtest_id,
                "run_id": run_id,
                "trade_id": None,
                "clearing_id": None,
                "source_type": "backtest",
                "source_id": backtest_id,
                "event_time": event_time,
                "event_type": "initial_balance",
                "symbol": None,
                "cash_delta": initial_capital,
                "realized_pnl_delta": 0.0,
                "unrealized_pnl_delta": 0.0,
                "commission_delta": 0.0,
                "slippage_delta": 0.0,
                "cash_balance": initial_capital,
                "realized_pnl_balance": 0.0,
                "unrealized_pnl_balance": 0.0,
                "equity": initial_capital,
                "margin": None,
                "metadata_json": None,
                "created_at": datetime.now(),
            }
        ]
        cash_balance = initial_capital
        realized_pnl_balance = 0.0
        for index, row in enumerate(rows):
            net_pnl = _float_row(row, "net_pnl")
            cash_balance += net_pnl
            realized_pnl_balance += net_pnl
            event_type = "forced_close_clearing" if bool(row.get("is_forced_close")) else "close_clearing"
            ledger_rows.append(
                {
                    "backtest_id": backtest_id,
                    "run_id": run_id,
                    "trade_id": row.get("close_trade_id"),
                    "clearing_id": None,
                    "clearing_index": index,
                    "source_type": "backtest",
                    "source_id": backtest_id,
                    "event_time": row["close_time"],
                    "event_type": event_type,
                    "symbol": row.get("symbol"),
                    "cash_delta": net_pnl,
                    "realized_pnl_delta": net_pnl,
                    "unrealized_pnl_delta": 0.0,
                    "commission_delta": -_float_row(row, "commission"),
                    "slippage_delta": -_float_row(row, "slippage_cost"),
                    "cash_balance": cash_balance,
                    "realized_pnl_balance": realized_pnl_balance,
                    "unrealized_pnl_balance": 0.0,
                    "equity": cash_balance,
                    "margin": None,
                    "metadata_json": None,
                    "created_at": datetime.now(),
                }
            )
        return ledger_rows

    @staticmethod
    def _build_position_ledger(
        backtest: dict[str, object],
        trades: list[TradeRecord],
        rows: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        backtest_id = _int_field(backtest, "id")
        run_id = backtest.get("run")
        events: list[tuple[datetime, int, dict[str, object]]] = []
        for trade in trades:
            if str(trade.offset).lower() != "open":
                continue
            events.append(
                (
                    pd.Timestamp(trade.datetime).to_pydatetime(),
                    0,
                    {"kind": "open", "trade": trade},
                )
            )
        for index, row in enumerate(rows):
            events.append(
                (
                    pd.Timestamp(str(row["close_time"])).to_pydatetime(),
                    1,
                    {"kind": "close", "row": row, "clearing_index": index},
                )
            )

        entries: list[dict[str, object]] = []
        position_state: dict[tuple[str, str], tuple[float, float]] = {}
        for _event_time, _priority, payload in sorted(events, key=lambda event: (event[0], event[1])):
            if payload["kind"] == "open":
                trade = cast(TradeRecord, payload["trade"])
                symbol = str(trade.symbol)
                direction = str(trade.direction).lower()
                key = (symbol, direction)
                old_volume, old_avg = position_state.get(key, (0.0, 0.0))
                volume = float(trade.quantity)
                new_volume = old_volume + volume
                new_avg = ((old_volume * old_avg) + (volume * float(trade.price))) / new_volume if new_volume else 0.0
                position_state[key] = (new_volume, new_avg)
                entries.append(
                    {
                        "backtest_id": backtest_id,
                        "run_id": run_id,
                        "open_trade_id": trade.id,
                        "close_trade_id": None,
                        "clearing_id": None,
                        "source_type": "backtest",
                        "source_id": backtest_id,
                        "event_time": pd.Timestamp(trade.datetime).to_pydatetime(),
                        "event_type": "open_fill",
                        "symbol": symbol,
                        "direction": direction,
                        "volume_delta": volume,
                        "position_volume": new_volume,
                        "avg_open_price": new_avg,
                        "realized_pnl_delta": 0.0,
                        "is_forced_close": False,
                        "metadata_json": None,
                        "created_at": datetime.now(),
                    }
                )
                continue

            row = cast(dict[str, object], payload["row"])
            symbol = str(row["symbol"])
            direction = str(row["direction"])
            key = (symbol, direction)
            old_volume, old_avg = position_state.get(key, (0.0, 0.0))
            volume = _float_row(row, "volume")
            new_volume = max(0.0, old_volume - volume)
            position_state[key] = (new_volume, old_avg if new_volume else 0.0)
            entries.append(
                {
                    "backtest_id": backtest_id,
                    "run_id": run_id,
                    "open_trade_id": row.get("open_trade_id"),
                    "close_trade_id": row.get("close_trade_id"),
                    "clearing_id": None,
                    "clearing_index": payload["clearing_index"],
                    "source_type": "backtest",
                    "source_id": backtest_id,
                    "event_time": row["close_time"],
                    "event_type": "forced_close_fifo_consumption"
                    if bool(row.get("is_forced_close"))
                    else "close_fifo_consumption",
                    "symbol": symbol,
                    "direction": direction,
                    "volume_delta": -volume,
                    "position_volume": new_volume,
                    "avg_open_price": old_avg if new_volume else 0.0,
                    "realized_pnl_delta": _float_row(row, "net_pnl"),
                    "is_forced_close": bool(row.get("is_forced_close")),
                    "metadata_json": None,
                    "created_at": datetime.now(),
                }
            )
        return entries

    @staticmethod
    def _build_summary(backtest: dict[str, object], rows: list[dict[str, object]]) -> dict[str, object]:
        net_values = [_float_row(row, "net_pnl") for row in rows]
        win_values = [value for value in net_values if value > 0]
        loss_values = [value for value in net_values if value < 0]
        win_trades = len(win_values)
        loss_trades = len(loss_values)
        avg_win = sum(win_values) / win_trades if win_trades else 0.0
        avg_loss = abs(sum(loss_values) / loss_trades) if loss_trades else 0.0
        total_closed = win_trades + loss_trades
        total_net_pnl = sum(net_values)
        initial_capital = _float_field(backtest, "initial_capital", 0.0)
        return {
            "total_net_pnl": total_net_pnl,
            "total_commission": sum(_float_row(row, "commission") for row in rows),
            "total_slippage": sum(_float_row(row, "slippage_cost") for row in rows),
            "win_trades": win_trades,
            "loss_trades": loss_trades,
            "win_rate": win_trades / total_closed if total_closed else 0.0,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": avg_win / avg_loss if avg_loss > 0 else 0.0,
            "max_consecutive_win": _max_consecutive(net_values, positive=True),
            "max_consecutive_loss": _max_consecutive(net_values, positive=False),
            "end_balance": initial_capital + total_net_pnl if initial_capital else backtest.get("end_balance"),
            "total_return": total_net_pnl / initial_capital * 100 if initial_capital else backtest.get("total_return"),
        }


def _parse_decision_payload(payload_json: str | None) -> dict[str, object] | None:
    """解析成交记录的 decision_payload_json。无效或为空返回 None。"""
    if not payload_json:
        return None
    try:
        data = json.loads(payload_json)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _payload_diagnostics(payload: dict[str, object] | None) -> dict[str, object]:
    """取 decision_payload 的 diagnostics 子树。"""
    if not payload:
        return {}
    diagnostics = payload.get("diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else {}


def _layer_dict(value: object) -> dict[str, object]:
    """取诊断层 dict，非 dict 归一为空 dict。"""
    return value if isinstance(value, dict) else {}


def _is_real(fields: object) -> bool:
    """判断诊断层是否为真实填充（非空且非占位）。"""
    if not isinstance(fields, dict) or not fields:
        return False
    return not (len(fields) == 1 and fields.get("placeholder") is True)


def _int_field(row: dict[str, object], key: str, default: int = 0) -> int:
    value = row.get(key)
    if value is None:
        return default
    return int(str(value))


def _float_field(row: dict[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    if value is None:
        return default
    return float(str(value))


def _float_row(row: dict[str, object], key: str) -> float:
    value = row[key]
    return float(str(value))


def _first_event_time(rows: list[dict[str, object]]) -> datetime:
    if rows:
        return pd.Timestamp(str(rows[0]["open_time"])).to_pydatetime()
    return datetime.now()


def _max_consecutive(values: list[float], *, positive: bool) -> int:
    best = 0
    current = 0
    for value in values:
        matched = value > 0 if positive else value < 0
        if matched:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best
