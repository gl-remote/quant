"""类型工具 — typing 兼容层

提供 pyright 友好的装饰器/类型包装，避免第三方库类型存根缺失导致的报错。
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    def check_types(f: Any) -> Any:  # type: ignore[no-untyped-def]
        """pyright 友好的 check_types 桩 — 签名保持原样，不报错"""
        return f
else:
    from pandera.typing import check_types  # noqa: F811