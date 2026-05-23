try:
    from .vnpy_gateway import VnpyMaStrategy
except ImportError:
    VnpyMaStrategy = None

try:
    from .tqsdk_gateway import TqsdkMaStrategy
except ImportError:
    TqsdkMaStrategy = None

__all__ = ['VnpyMaStrategy', 'TqsdkMaStrategy']