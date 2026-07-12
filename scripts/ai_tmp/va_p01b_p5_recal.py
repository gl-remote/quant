#!/usr/bin/env python3
"""
va-composite · P0.1 回溯重跑 · Phase 5 (dedup 扫描) 正确口径版

依赖 P0.1 产物 timeline_calA.parquet，复跑原 va_composite_p5_dedup.py 的 dedup 扫描
（Cap=5.0 定档）。旧脚本建立在缺陷口径上，故本 driver monkeypatch
P1.TIMELINE_PATH/OUT_DIR 后调用其 main，并修正 summary 头部口径标注。

运行: uv run python scripts/ai_tmp/va_p01b_p5_recal.py
输出: project_data/ai_tmp/p5_dedup_calA/ (dedup{h}.trades.parquet + summary.md)
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402
import va_composite_p5_dedup as P5  # noqa: E402

CALA = Path("project_data/ai_tmp/p0_calib/timeline_calA.parquet")
OUT_DIR = Path("project_data/ai_tmp/p5_dedup_calA")
OUT_DIR.mkdir(parents=True, exist_ok=True)

P1.TIMELINE_PATH = CALA
P5.OUT_DIR = OUT_DIR
P5.CAP = 5.0


def _fix_header(path: Path) -> None:
    if not path.exists():
        return
    txt = path.read_text(encoding="utf-8")
    txt = txt.replace(
        f"> Cap 定档 = {P5.CAP}。dedup 为 B 层执行参数（合约内去重窗口），approach A 下可直测。",
        f"> Cap 定档 = {P5.CAP}。dedup 为 B 层执行参数。**本 run 建立在正确口径 timeline_calA（P0.1）之上**，"
        "为缺陷口径 P5 的回溯重跑；旧口径数字见原 p5_dedup/summary.md。",
    )
    path.write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    print(">>> P0.1 回溯重跑 P5 (dedup 扫描) · 正确口径 timeline_calA <<<")
    P5.main()
    _fix_header(OUT_DIR / "summary.md")
    print(">>> summary 头部口径已修正为 calA <<<")
