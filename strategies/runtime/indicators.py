"""模块级指标计算函数注册体系

包含：IndicatorCalcMode 枚举、IndicatorFuncInfo 数据类、全局注册字典、注册函数、列名生成工具。
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray


class IndicatorCalcMode(Enum):
    """指标计算模式"""

    BATCH = "batch"  # 一次性计算所有数据（默认）
    INCREMENTAL = "incremental"  # 逐行/增量式计算，适合 update_bar 时触发


@dataclass
class IndicatorFuncInfo:
    """指标函数信息，保存已注册的指标函数元数据"""

    func: Callable[..., NDArray[np.float64]]
    calc_mode: IndicatorCalcMode
    name: str
    description: str | None = None


# 全局已注册指标函数字典：指标名称 -> 信息
REGISTERED_INDICATOR_FUNCS: dict[str, IndicatorFuncInfo] = {}


def register_indicator_func(
    name: str,
    func: Callable[..., NDArray[np.float64]],
    calc_mode: IndicatorCalcMode = IndicatorCalcMode.BATCH,
    description: str | None = None,
) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> NDArray[np.float64]

    【指标列名生成规则】
    - 列名格式：{indicator_name}_{param1_value}_{param2_value}_...
    - 参数按参数名称排序，确保参数顺序不影响列名生成
    - 示例：
      - 假设函数定义为 def sma(df, period): ...
        - sma(period=10) → sma_10
      - 假设函数定义为 def bbands(df, period, std): ...
        - bbands(period=20, std=2) → bbands_20_2
        - bbands(std=2, period=20) → bbands_20_2（同样按参数名称排序）

    :param name: 指标名称
    :param func: 计算函数
    :param calc_mode: 计算模式，BATCH（默认）一次性全量计算，INCREMENTAL适合实时增量
    :param description: 指标描述（可选）
    """
    REGISTERED_INDICATOR_FUNCS[name] = IndicatorFuncInfo(
        func=func, calc_mode=calc_mode, name=name, description=description
    )


def generate_indicator_column_name(name: str, params: dict[str, Any]) -> str:
    """生成指标列名

    【参数顺序】
    - 按参数名称排序，确保参数顺序不影响列名生成
    """
    sorted_params = sorted(params.items())
    param_parts = [f"{value}" for _, value in sorted_params]
    if param_parts:
        return f"{name}_{'_'.join(param_parts)}"
    return name
