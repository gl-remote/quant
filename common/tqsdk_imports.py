"""天勤 SDK 延迟导入管理器

统一管理 tqsdk 的延迟导入，避免各处重复写 from tqsdk import ...。
如果 tqsdk 版本升级导致 API 变动，只需更新此文件。
"""

from loguru import logger
from typing import Any

class TqsdkImports:
    """天勤 SDK 延迟导入管理器 — 单例使用

    用法:
tqsdk = TqsdkImports()
        if tqsdk.ensure():
            api = tqsdk.TqApi(...)
    """

    def __init__(self) -> None:
        self._loaded: bool = False
        self.TqApi: Any = None
        self.TqAuth: Any = None
        self.TargetPosTask: Any = None
        self.TqBacktest: Any = None
        self.BacktestFinished: Any = None

    def ensure(self) -> bool:
        if self._loaded:
            return True
        try:
            from tqsdk import TqApi, TqAuth, TargetPosTask, TqBacktest
            from tqsdk.exceptions import BacktestFinished
            self.TqApi = TqApi
            self.TqAuth = TqAuth
            self.TargetPosTask = TargetPosTask
            self.TqBacktest = TqBacktest
            self.BacktestFinished = BacktestFinished
            self._loaded = True
            return True
        except ImportError:
            logger.error("tqsdk 未安装，请 pip install tqsdk")
            return False


tqsdk = TqsdkImports()