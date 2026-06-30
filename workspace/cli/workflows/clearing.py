"""Clearing workflow 入口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clearing.service import BacktestClearingService


@dataclass(frozen=True)
class ClearingRequest:
    run_id: int


class ClearingWorkflow:
    """调度 clearing 业务域。"""

    def __init__(self, dm: Any) -> None:
        self._dm = dm

    def run(self, request: ClearingRequest) -> None:
        BacktestClearingService(self._dm).clear_run(request.run_id)
