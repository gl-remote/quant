#!/usr/bin/env python3
"""
va-composite · P0.1 回溯重跑 · Phase 1 (Cap 扫描) 正确口径版

依赖 P0.1 产物 timeline_calA.parquet（drop_duplicates 后按天滚动的正确口径双轨之 A 轨，
即修正版 B0），复跑原 va_composite_p1_cap.py 的 Cap 扫描。
旧脚本头部明示「旧口径不动」，故本 driver 仅 monkeypatch TIMELINE_PATH/OUT_DIR 后调用其 main，
并修正 summary 头部口径标注，不改动其回测引擎逻辑。

运行: uv run python scripts/ai_tmp/va_p01b_p1_recal.py
输出: project_data/ai_tmp/p1_cap_calA/ (cap{K}.trades.parquet + summary.md)
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

CALA = Path("project_data/ai_tmp/p0_calib/timeline_calA.parquet")
OUT_DIR = Path("project_data/ai_tmp/p1_cap_calA")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P1.TIMELINE_PATH = CALA
P1.OUT_DIR = OUT_DIR


def _fix_header(path: Path) -> None:
    """把原脚本写死的『旧口径』标注改为正确口径 calA，避免留下误导 artifact。"""
    if not path.exists():
        return
    txt = path.read_text(encoding="utf-8")
    txt = txt.replace(
        "> 基线: 冻结 B0（旧口径 timeline，Cap=1.0）。本 Phase 不重跑上游管线修正（走 A 方案）。",
        "> 基线: 正确口径 timeline_calA.parquet（P0.1 drop_duplicates 后按天滚动重建，Cap=1.0=B0 修正版）。本次为口径回溯重跑。",
    )
    txt = txt.replace(
        "## 1. 各 Cap 主指标",
        "## 1. 各 Cap 主指标（正确口径 calA · 旧口径数字见原 p1_cap/summary.md）",
    )
    path.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    print(">>> P0.1 回溯重跑 P1 (Cap 扫描) · 正确口径 timeline_calA <<<")
    P1.main()
    _fix_header(OUT_DIR / "summary.md")
    print(">>> summary 头部口径已修正为 calA <<<")
