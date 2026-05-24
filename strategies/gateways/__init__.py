try:
    from .vnpy_gateway import VnpyStrategyGateway
except ImportError:
    VnpyStrategyGateway = None

try:
    from .tqsdk_gateway import TqsdkStrategyGateway
except ImportError:
    TqsdkStrategyGateway = None

__all__ = ['VnpyStrategyGateway', 'TqsdkStrategyGateway']