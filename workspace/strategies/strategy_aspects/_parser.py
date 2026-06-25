"""字符串表达式解析器（Pratt Parser）— 装饰器 DSL 字符串化的核心。

将形如 ``"macd@1m > 0 && sma({sma_short})@5m > sma({sma_long})@5m"``
的字符串表达式解析为 ``_ParsedPredicate``，兼容 ``_Predicate`` Protocol，
供方向/风控装饰器统一使用。

用法::

    predicate = parse_expr("macd@1m > 0")
    predicate.metrics        # -> (MetricRef(period="1m", ...),)
    predicate.default_name   # -> "macd_1m_gt_0"
    predicate.evaluate(ctx, config)  # -> (True, {"macd": 12.5}) | None
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .primitives import MetricRef

# ── Token 定义 ─────────────────────────────────────────────

TokenType = Literal[
    "NUMBER",
    "IDENTIFIER",
    "PERIOD_ID",
    "LPAREN",
    "RPAREN",
    "COMMA",
    "LBRACE",
    "RBRACE",
    "AT",
    "OP",
    "AND",
    "OR",
    "EOF",
]


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    pos: int  # 在原字符串中的位置，用于错误报告


# ── 词法分析 ───────────────────────────────────────────────

_TOKEN_PATTERNS: list[tuple[str, TokenType]] = [
    (r"\d+[a-zA-Z]+", "PERIOD_ID"),  # 周期标识符如 1m, 5m, 15m（必须在 NUMBER 前）
    (r"\d+(?:\.\d+)?", "NUMBER"),
    (r"&&", "AND"),
    (r"\|\|", "OR"),
    (r"\band\b", "AND"),
    (r"\bor\b", "OR"),
    (r">=|<=|!=|==|>|<", "OP"),
    (r"@", "AT"),
    (r"\(", "LPAREN"),
    (r"\)", "RPAREN"),
    (r",", "COMMA"),
    (r"\{", "LBRACE"),
    (r"\}", "RBRACE"),
    (r"[a-zA-Z_][a-zA-Z0-9_]*", "IDENTIFIER"),
]

# 编译为正则（编号组，避免同名冲突）
_TOKEN_COMPILED = re.compile("|".join(f"({pattern})" for pattern, _ in _TOKEN_PATTERNS))


def _match_type(match: re.Match[str]) -> TokenType:
    """根据匹配到的组序号返回对应 TokenType。"""
    for i, (_, type_) in enumerate(_TOKEN_PATTERNS):
        if match.group(i + 1) is not None:
            return type_
    return "IDENTIFIER"  # fallback，不应走到


def tokenize(source: str) -> list[Token]:
    """将 DSL 字符串拆分为 Token 列表。"""
    tokens: list[Token] = []
    for match in _TOKEN_COMPILED.finditer(source):
        tokens.append(Token(type=_match_type(match), value=match.group(), pos=match.start()))
    tokens.append(Token(type="EOF", value="", pos=len(source)))
    return tokens


# ── 表达式 AST 节点 ─────────────────────────────────────────


@dataclass(frozen=True)
class NumberExpr:
    value: float


@dataclass(frozen=True)
class ConfigRefExpr:
    """{identifier} — 从 config 读取字段值"""

    key: str


@dataclass(frozen=True)
class FuncCallExpr:
    """内置函数调用，如 cooldown(), profit_abs() 等"""

    name: str


@dataclass(frozen=True)
class MetricRefExpr:
    """带参或裸指标 + 周期绑定，如 sma({sma_short})@5m, macd@1m"""

    indicator_name: str
    params: tuple[str | float, ...] = field(default_factory=tuple)
    period: str = ""


@dataclass(frozen=True)
class CompareExpr:
    left: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr
    op: str
    right: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr


@dataclass(frozen=True)
class BoolOpExpr:
    op: Literal["and", "or"]
    left: Expr
    right: Expr


Expr = NumberExpr | ConfigRefExpr | FuncCallExpr | MetricRefExpr | CompareExpr | BoolOpExpr


# ── Pratt Parser ───────────────────────────────────────────


# binding power 表：值越大优先级越高
_PRECEDENCE: dict[str, int] = {
    "||": 10,
    "or": 10,
    "&&": 20,
    "and": 20,
    ">": 30,
    "<": 30,
    ">=": 30,
    "<=": 30,
    "==": 30,
    "!=": 30,
    "@": 50,
}


def _bp_of(token: Token) -> int:
    return _PRECEDENCE.get(token.value, 0)


class _PrattParser:
    """Pratt 解析器，处理纯表达式语法"""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, type: TokenType, value: str | None = None) -> Token:
        token = self._peek()
        if token.type != type or (value is not None and token.value != value):
            raise SyntaxError(f"位置 {token.pos}：期望 {value or type}，实际得到 '{token.value}'")
        return self._advance()

    def parse(self, min_bp: int = 0) -> Expr:
        """Pratt 主循环"""
        token = self._advance()
        left = self._prefix(token)
        if left is None:
            raise SyntaxError(f"位置 {token.pos}：意外的 token '{token.value}'")

        while self._peek().type != "EOF" and _bp_of(self._peek()) > min_bp:
            op_token = self._advance()
            left = self._infix(left, op_token)

        return left

    def _prefix(self, token: Token) -> Expr | None:
        """处理前缀表达式"""
        if token.type == "NUMBER":
            return NumberExpr(value=float(token.value))

        if token.type == "LBRACE":
            id_token = self._expect("IDENTIFIER")
            self._expect("RBRACE")
            return ConfigRefExpr(key=id_token.value)

        if token.type == "IDENTIFIER":
            return self._parse_call_or_metric(token)

        if token.type == "LPAREN":
            expr = self.parse(0)
            self._expect("RPAREN")
            return expr

        return None

    def _infix(self, left: Expr, token: Token) -> Expr:
        """处理中缀表达式"""
        if token.type == "AT":
            period_token = self._expect("PERIOD_ID")
            if not isinstance(left, MetricRefExpr):
                # left 可能来自 "()" 或单独的 identifier，包装为 MetricRefExpr
                if isinstance(left, FuncCallExpr):
                    left = MetricRefExpr(
                        indicator_name=left.name,
                        params=tuple(),
                        period=period_token.value,
                    )
                else:
                    raise SyntaxError(f"位置 {token.pos}：'@' 左侧必须是指标名或函数调用")
            else:
                object.__setattr__(left, "period", period_token.value)
            return left

        if token.type == "OP":
            right = self.parse(_bp_of(token))
            return CompareExpr(left=left, op=token.value, right=right)  # type: ignore[arg-type]

        if token.type == "AND":
            right = self.parse(_bp_of(token))
            return BoolOpExpr(op="and", left=left, right=right)

        if token.type == "OR":
            right = self.parse(_bp_of(token))
            return BoolOpExpr(op="or", left=left, right=right)

        raise SyntaxError(f"位置 {token.pos}：未知运算符 '{token.value}'")

    def _parse_call_or_metric(self, token: Token) -> MetricRefExpr | FuncCallExpr:
        """解析 identifier 或 identifier(...) 构成调用或指标引用"""
        name = token.value

        # 函数调用：identifier(...)
        if self._peek().type == "LPAREN":
            self._advance()  # 消耗 (
            params: list[str | float] = []
            if self._peek().type != "RPAREN":
                params.append(self._parse_param())
                while self._peek().type == "COMMA":
                    self._advance()
                    params.append(self._parse_param())
            self._expect("RPAREN")

            # 后面紧跟 @period → 带参指标
            if self._peek().type == "AT":
                self._advance()  # 消耗 @
                period = self._expect("PERIOD_ID").value
                return MetricRefExpr(
                    indicator_name=name,
                    params=tuple(params),
                    period=period,
                )

            # 无 @period → 内置函数
            if not params:
                return FuncCallExpr(name=name)

            # 带参但无 @period → 语法错误
            raise SyntaxError(f"位置 {token.pos}：'{name}(...)' 带参调用需要 '@period' 绑定 K 线周期")

        # 裸 identifier，看后面是否紧跟 @period
        if self._peek().type == "AT":
            self._advance()  # 消耗 @
            period = self._expect("PERIOD_ID").value
            return MetricRefExpr(
                indicator_name=name,
                params=tuple(),
                period=period,
            )

        # 裸 identifier 无 @ → 尝试作为常量名（如配置中的特殊常量）
        # 这种情况在 DSL 中不应出现，报错提示
        raise SyntaxError(f"位置 {token.pos}：裸标识符 '{name}' 无效 — 指标需要 '@period'，函数需要 '()'")

    def _parse_param(self) -> str | float:
        """解析函数参数： 数值 或 {config_ref}"""
        token = self._peek()
        if token.type == "NUMBER":
            self._advance()
            return float(token.value)
        if token.type == "LBRACE":
            self._advance()
            id_token = self._expect("IDENTIFIER")
            self._expect("RBRACE")
            return f"{{{id_token.value}}}"
        if token.type == "IDENTIFIER":
            # 无大括号包裹的 identifier 也视为配置引用模板
            self._advance()
            return f"{{{token.value}}}"
        raise SyntaxError(f"位置 {token.pos}：无效的参数 '{token.value}'")


# ── 公开函数 ────────────────────────────────────────────────


def parse_expr(source: str) -> _ParsedPredicate:
    """解析 DSL 字符串表达式为 ``_ParsedPredicate``。

    :param source: DSL 表达式字符串，如 ``"macd@1m > 0"``
    :returns: 满足 ``_Predicate`` Protocol 的可求值谓词对象
    :raises SyntaxError: 语法错误时抛出，含位置信息
    """
    tokens = tokenize(source)
    parser = _PrattParser(tokens)
    expr = parser.parse()
    return _ParsedPredicate(expr)


# ── 谓词包装 ────────────────────────────────────────────────


class _ParsedPredicate:
    """将解析后的表达式树包装为 ``_Predicate`` Protocol。

    由 ``parse_expr`` 返回，不直接构造。
    """

    def __init__(self, expr: Expr) -> None:
        self._expr = expr

    # ── _Predicate Protocol ──

    @property
    def metrics(self) -> tuple[MetricRef, ...]:
        return _collect_metrics(self._expr)

    @property
    def default_name(self) -> str:
        return _default_name(self._expr)

    def evaluate(self, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
        """评估表达式树；数据不可用时返回 None（空安全）。"""
        return _evaluate_expr(self._expr, ctx, config)

    def __repr__(self) -> str:
        return f"<ParsedPredicate: {self._expr}>"


# ── 表达式求值 ──────────────────────────────────────────────


def _evaluate_expr(expr: Expr, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
    """表达式树入口求值器"""
    if isinstance(expr, BoolOpExpr):
        return _evaluate_bool_op(expr, ctx, config)
    if isinstance(expr, CompareExpr):
        return _evaluate_compare(expr, ctx, config)
    # 不应走到的分支
    raise TypeError(f"表达式树根节点必须是布尔或比较表达式，实际为 {type(expr).__name__}")


def _evaluate_bool_op(expr: BoolOpExpr, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
    left = _evaluate_expr(expr.left, ctx, config)
    right = _evaluate_expr(expr.right, ctx, config)

    if left is None or right is None:
        return None

    satisfied = left[0] and right[0] if expr.op == "and" else left[0] or right[0]  # noqa: SIM108
    return satisfied, {**left[1], **right[1]}


def _evaluate_compare(expr: CompareExpr, ctx: Any, config: Any) -> tuple[bool, dict[str, Any]] | None:
    left_val = _resolve_value(expr.left, ctx, config)
    right_val = _resolve_value(expr.right, ctx, config)

    if left_val is None or right_val is None:
        return None

    if expr.op == ">":
        satisfied = left_val > right_val
    elif expr.op == "<":
        satisfied = left_val < right_val
    elif expr.op == ">=":
        satisfied = left_val >= right_val
    elif expr.op == "<=":
        satisfied = left_val <= right_val
    elif expr.op == "==":
        satisfied = abs(left_val - right_val) < 1e-9
    elif expr.op == "!=":
        satisfied = abs(left_val - right_val) >= 1e-9
    else:
        raise ValueError(f"未知比较运算符 '{expr.op}'")

    detail: dict[str, Any] = {
        "left_value": left_val,
        "right_value": right_val,
        "op": expr.op,
    }
    return satisfied, detail


def _resolve_value(
    expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr,
    ctx: Any,
    config: Any,
) -> float | None:
    """将值表达式解析为数值；数据不可用时返回 None。"""
    if isinstance(expr, NumberExpr):
        return expr.value

    if isinstance(expr, ConfigRefExpr):
        return float(getattr(config, expr.key, 0.0))

    if isinstance(expr, MetricRefExpr):
        return _read_metric(expr, ctx, config)

    if isinstance(expr, FuncCallExpr):
        return _call_builtin(expr.name, ctx, config)

    return None


# ── 指标读取 ────────────────────────────────────────────────


def _read_metric(expr: MetricRefExpr, ctx: Any, config: Any) -> float | None:
    """从 ctx.multi[period] 读取指标值；数据未就绪时返回 None。"""
    from .direction._core import _read_metric as _core_read_metric

    # 构造 MetricRef
    from .indicators import KDJ, MACD, SMA

    _indicator_map: dict[str, Any] = {
        "macd": MACD,
        "kdj": KDJ,
        "sma": SMA,
        "atr": None,  # 特殊处理
    }

    if expr.indicator_name == "atr":
        # ATR 列名由 generate_indicator_column_name 生成
        from ..core.indicators import generate_indicator_column_name

        view = ctx.multi.get(expr.period)
        if view is None:
            return None
        atr_period = getattr(config, "atr_period", 14)
        col = generate_indicator_column_name("atr", {"period": atr_period}, period=expr.period)
        return view.indicator(col, -1)  # type: ignore[no-any-return]

    indicator_factory = _indicator_map.get(expr.indicator_name)
    if indicator_factory is None:
        return None

    if callable(indicator_factory):
        if expr.params:
            resolved_params = []
            for p in expr.params:
                if isinstance(p, str) and p.startswith("{") and p.endswith("}"):
                    resolved_params.append(getattr(config, p[1:-1], p))
                else:
                    resolved_params.append(p)
            indicator = indicator_factory(*resolved_params)
        else:
            indicator = indicator_factory()
    else:
        return None

    metric_ref = MetricRef(period=expr.period, indicator=indicator)
    return _core_read_metric(ctx, metric_ref, config)  # type: ignore[no-any-return]


# ── 内置函数求值 ────────────────────────────────────────────


def _call_builtin(name: str, ctx: Any, config: Any) -> float | None:
    """调用内置函数（profit_abs, cooldown 等）；数据不足时返回 None。"""
    # 这些函数需要 state 中的持仓/成交数据，仅在风控场景下有效
    # 方向切面在空仓时调用会返回 None（由空安全机制静默跳过）
    try:
        if name == "cooldown":
            return _builtin_cooldown(ctx, config)
        if name == "profit_abs":
            return _builtin_profit_abs(ctx, config)
        if name == "profit_pct":
            return _builtin_profit_pct(ctx, config)
        if name == "peak_profit":
            return _builtin_peak_profit(ctx, config)
        if name == "drawdown_pct":
            return _builtin_drawdown_pct(ctx, config)
        return None
    except (AttributeError, TypeError):
        return None


def _builtin_cooldown(ctx: Any, config: Any) -> float | None:
    """自上次匹配风控角色的成交以来的冷却分钟数。"""
    fills = ctx.state.fills if hasattr(ctx, "state") else []
    if not fills:
        return None
    last_fill = fills[-1]

    # 角色过滤：只匹配当前风控角色对应的成交
    risk_role = getattr(ctx, "risk_role", None)
    if risk_role == "take_profit":
        if "TAKE_PROFIT" not in last_fill.reason:
            return None
    elif risk_role == "stop_loss":
        if "TAKE_PROFIT" in last_fill.reason:
            return None

    now = ctx.bar.timestamp if hasattr(ctx.bar, "timestamp") else 0
    elapsed_minutes = (now - last_fill.timestamp) / 60_000  # type: ignore[operator]
    return elapsed_minutes  # type: ignore[no-any-return]


def _builtin_profit_abs(ctx: Any, config: Any) -> float | None:
    """绝对盈亏 |close - entry_price|"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction:
        return None
    return abs(ctx.bar.close - pos.entry_price)  # type: ignore[no-any-return]


def _builtin_profit_pct(ctx: Any, config: Any) -> float | None:
    """盈亏比例 |close - entry_price| / entry_price"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction or pos.entry_price == 0:
        return None
    return abs(ctx.bar.close - pos.entry_price) / pos.entry_price  # type: ignore[no-any-return]


def _builtin_peak_profit(ctx: Any, config: Any) -> float | None:
    """峰值收益 |highest_price - entry_price|"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction:
        return None
    return abs(pos.highest_price - pos.entry_price)  # type: ignore[no-any-return]


def _builtin_drawdown_pct(ctx: Any, config: Any) -> float | None:
    """回撤比例 |highest_price - close| / highest_price"""
    pos = ctx.state.position if hasattr(ctx, "state") else None
    if pos is None or not pos.direction or pos.highest_price == 0:
        return None
    return abs(pos.highest_price - ctx.bar.close) / pos.highest_price  # type: ignore[no-any-return]


# ── 工具函数 ────────────────────────────────────────────────


def _collect_metrics(expr: Expr) -> tuple[MetricRef, ...]:
    """递归收集表达式树中所有 MetricRef。"""
    if isinstance(expr, MetricRefExpr):
        from .indicators import ATR, KDJ, MACD, SMA, IndicatorSpec

        _indicator_map: dict[str, Any] = {
            "macd": MACD,
            "kdj": KDJ,
            "sma": SMA,
            "atr": ATR,
        }
        factory = _indicator_map.get(expr.indicator_name)
        if factory is None:
            return ()
        if callable(factory) and not isinstance(factory, IndicatorSpec):
            indicator = factory(*expr.params) if expr.params else factory()
        else:
            indicator = factory
        return (MetricRef(period=expr.period, indicator=indicator),)

    if isinstance(expr, CompareExpr):
        return _collect_value_metrics(expr.left) + _collect_value_metrics(expr.right)

    if isinstance(expr, BoolOpExpr):
        return _collect_metrics(expr.left) + _collect_metrics(expr.right)

    return ()


def _collect_value_metrics(
    expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr,
) -> tuple[MetricRef, ...]:
    if isinstance(expr, MetricRefExpr):
        return _collect_metrics(expr)
    return ()


def _default_name(expr: Expr) -> str:
    """从表达式树生成默认理由名"""
    if isinstance(expr, MetricRefExpr):
        base = expr.indicator_name
        if expr.params:
            param_str = "_".join(str(p).strip("{}") for p in expr.params)
            base = f"{base}_{param_str}"
        return f"{base}_{expr.period}"

    if isinstance(expr, CompareExpr):
        left_name = _default_name(expr.left) if _is_named(expr.left) else _value_name(expr.left)
        right_name = _default_name(expr.right) if _is_named(expr.right) else _value_name(expr.right)
        op_map = {">": "gt", "<": "lt", ">=": "gte", "<=": "lte", "==": "eq", "!=": "ne"}
        op_str = op_map.get(expr.op, expr.op)
        return f"{left_name}_{op_str}_{right_name}"

    if isinstance(expr, BoolOpExpr):
        left_name = _default_name(expr.left)
        right_name = _default_name(expr.right)
        return f"{left_name}_{expr.op}_{right_name}"

    if isinstance(expr, FuncCallExpr):
        return expr.name

    if isinstance(expr, ConfigRefExpr):
        return expr.key

    if isinstance(expr, NumberExpr):
        return str(expr.value).replace(".", "_")

    return "unknown"


def _value_name(expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr) -> str:
    if isinstance(expr, NumberExpr):
        return str(expr.value).replace(".", "_")
    if isinstance(expr, ConfigRefExpr):
        return expr.key
    if isinstance(expr, FuncCallExpr):
        return expr.name
    if isinstance(expr, MetricRefExpr):
        return _default_name(expr)
    return "unknown"


def _is_named(expr: Expr) -> bool:
    return isinstance(expr, (MetricRefExpr, FuncCallExpr, ConfigRefExpr, CompareExpr, BoolOpExpr))
