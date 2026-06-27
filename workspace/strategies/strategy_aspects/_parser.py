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

from .builtins import call_builtin
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
    "MUL",
    "DIV",
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
    (r"\*", "MUL"),
    (r"/", "DIV"),
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


def _resolve_template_value(value: Any, config: Any) -> Any:
    """解析模板值，支持完整模板和部分模板。"""
    if not isinstance(value, str):
        return value
    full_match = re.match(r"^\{(\w+)\}$", value)
    if full_match:
        return getattr(config, full_match.group(1), value)
    if "{" in value:

        def _replace(m: re.Match[str]) -> str:
            return str(getattr(config, m.group(1)))

        return re.sub(r"\{(\w+)\}", _replace, value)
    return value


def _as_indicator_params(params: list[Any]) -> tuple[float | int | str, ...] | None:
    result: list[float | int | str] = []
    for value in params:
        if not isinstance(value, (float, int, str)):
            return None
        result.append(value)
    return tuple(result)


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
    """比较表达式，如 ``macd@1m > 0``、``loss_pct() >= {stop_loss_ratio}``"""

    left: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr
    op: str
    right: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr


@dataclass(frozen=True)
class ArithExpr:
    """算术表达式，如 atr@15m * {multiplier}"""

    op: Literal["*", "/"]
    left: ExprValue
    right: ExprValue


@dataclass(frozen=True)
class BoolOpExpr:
    """布尔组合表达式，支持 ``&&``/``and`` 和 ``||``/``or``，优先级 ``&& > ||``"""

    op: Literal["and", "or"]
    left: Expr
    right: Expr


ExprValue = MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr
Expr = ExprValue | CompareExpr | BoolOpExpr


# ── Pratt Parser ───────────────────────────────────────────


# binding power 表：值越大优先级越高
_PRECEDENCE: dict[str, int] = {
    "||": 10,
    "or": 10,
    "&&": 20,
    "and": 20,
    "*": 40,
    "/": 40,
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


def _as_value_expr(expr: Expr, token: Token) -> ExprValue:
    if isinstance(expr, (MetricRefExpr, FuncCallExpr, ConfigRefExpr, NumberExpr, ArithExpr)):
        return expr
    raise SyntaxError(f"位置 {token.pos}：运算符 '{token.value}' 两侧必须是值表达式")


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
        """Pratt 主循环：先解析前缀表达式，然后反复消费高优先级的中缀运算符。

        Pratt Parser 的核心思想是每个 token 关联 prefix 和 infix 处理函数，
        运算符优先级由 binding power 表 (``_PRECEDENCE``) 声明式管理，
        无需手写 EBNF 层级嵌套。
        """
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
        """处理中缀运算符：``@`` 绑定周期，``*/`` 算术，``OP`` 比较，``AND/OR`` 布尔组合"""
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
                # frozen dataclass，通过 object.__setattr__ 变通赋值
                object.__setattr__(left, "period", period_token.value)
            return left

        if token.type in ("MUL", "DIV"):
            right = self.parse(_bp_of(token))
            op: Literal["*", "/"] = "*" if token.type == "MUL" else "/"
            return ArithExpr(op=op, left=_as_value_expr(left, token), right=_as_value_expr(right, token))

        if token.type == "OP":
            right = self.parse(_bp_of(token))
            return CompareExpr(left=_as_value_expr(left, token), op=token.value, right=_as_value_expr(right, token))

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

    # 写入 diagnostics
    if _is_named(expr.left):
        ctx.aspects.diagnostics[_default_name(expr)] = left_val
    if _is_named(expr.right):
        ctx.aspects.diagnostics[_default_name(expr.right)] = right_val

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
    expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr,
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
        return call_builtin(expr.name, ctx, config)

    if isinstance(expr, ArithExpr):
        left_val = _resolve_value(expr.left, ctx, config)
        right_val = _resolve_value(expr.right, ctx, config)
        if left_val is None or right_val is None:
            return None
        if expr.op == "*":
            return left_val * right_val
        if expr.op == "/":
            if right_val == 0:
                return None
            return left_val / right_val
        return None

    return None


# ── 指标读取 ────────────────────────────────────────────────


def _read_indicator_value(ctx: Any, metric: MetricRef, config: Any) -> Any:
    """读取某个 MetricRef 在当前 bar(-1) 上的指标值，周期缺失则返回 None。"""
    from ..core.indicators import generate_indicator_column_name

    view = ctx.multi.get(metric.period)
    if view is None:
        return None
    col = generate_indicator_column_name(metric.indicator.name, metric.indicator.params, period=metric.period)
    resolved_col = _resolve_template_value(col, config)
    return view.indicator(resolved_col, -1)


def _read_metric(expr: MetricRefExpr, ctx: Any, config: Any) -> float | None:
    """从 ctx.multi[period] 读取指标值；数据未就绪时返回 None。"""
    from .indicators import build_indicator

    resolved_params = _as_indicator_params([_resolve_template_value(p, config) for p in expr.params])
    if resolved_params is None:
        return None
    indicator = build_indicator(expr.indicator_name, resolved_params)
    if indicator is None:
        return None

    metric_ref = MetricRef(period=expr.period, indicator=indicator)
    value = _read_indicator_value(ctx, metric_ref, config)
    if value == 0.0 and expr.indicator_name == "atr":
        return None
    return value  # type: ignore[no-any-return]


# ── 工具函数 ────────────────────────────────────────────────


def _collect_metrics(expr: Expr) -> tuple[MetricRef, ...]:
    """递归收集表达式树中所有 MetricRef。"""
    if isinstance(expr, MetricRefExpr):
        from .indicators import build_indicator

        indicator = build_indicator(expr.indicator_name, expr.params)
        if indicator is None:
            return ()
        return (MetricRef(period=expr.period, indicator=indicator),)

    if isinstance(expr, CompareExpr):
        return _collect_value_metrics(expr.left) + _collect_value_metrics(expr.right)

    if isinstance(expr, BoolOpExpr):
        return _collect_metrics(expr.left) + _collect_metrics(expr.right)

    return ()


def _collect_value_metrics(
    expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr,
) -> tuple[MetricRef, ...]:
    if isinstance(expr, MetricRefExpr):
        return _collect_metrics(expr)
    if isinstance(expr, ArithExpr):
        return _collect_value_metrics(expr.left) + _collect_value_metrics(expr.right)
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

    if isinstance(expr, ArithExpr):
        left_name = _value_name(expr.left)
        right_name = _value_name(expr.right)
        op_str = "times" if expr.op == "*" else "div"
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


def _value_name(expr: MetricRefExpr | FuncCallExpr | ConfigRefExpr | NumberExpr | ArithExpr) -> str:
    if isinstance(expr, NumberExpr):
        v = expr.value
        # 整数浮点数（如 0.0 → "0"）不转为 "0_0"，
        # 非整数（如 3.14 → "3_14"）转下划线形式
        if v == int(v):
            return str(int(v))
        return str(v).replace(".", "_")
    if isinstance(expr, ConfigRefExpr):
        return expr.key
    if isinstance(expr, FuncCallExpr):
        return expr.name
    if isinstance(expr, MetricRefExpr):
        return _default_name(expr)
    if isinstance(expr, ArithExpr):
        left_name = _value_name(expr.left)
        right_name = _value_name(expr.right)
        op_str = "times" if expr.op == "*" else "div"
        return f"{left_name}_{op_str}_{right_name}"
    return "unknown"


def _is_named(expr: Expr) -> bool:
    return isinstance(expr, (MetricRefExpr, FuncCallExpr, ConfigRefExpr, CompareExpr, ArithExpr, BoolOpExpr))
