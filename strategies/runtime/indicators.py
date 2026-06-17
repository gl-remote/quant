"""指标列名生成工具"""

from typing import Any


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
