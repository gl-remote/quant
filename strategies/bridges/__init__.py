try:
    from .vnpy_bridge import VnpyStrategyBridge
except ImportError:
    VnpyStrategyBridge = None  # type: ignore[assignment, misc]

try:
    from .tqsdk_bridge import TqsdkStrategyBridge
except ImportError:
    TqsdkStrategyBridge = None  # type: ignore[assignment, misc]

__all__ = ['VnpyStrategyBridge', 'TqsdkStrategyBridge']
