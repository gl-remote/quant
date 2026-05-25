"""report 模块内部工具函数"""


def _na_str(v) -> str:
    """将可能为 None 的值转为展示字符串"""
    return 'N/A' if v is None else str(v)


def _get_attr(obj, key, default=None):
    """获取对象属性值（兼容 dict 和 ORM model）"""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return obj.get(key, default) if isinstance(obj, dict) else default
