#!/usr/bin/env python3
"""
va-composite · P0.1（干净版）· 三路 A/B 回测分解

目的: 把之前被混淆的「口径修复」拆成两个独立效应，干净归因：
  - 效应① 分类器漂移: 冻结 tier vs 当前分类器(在冻结秩上重算) 的回测差异
  - 效应② skew 去重:   当前分类器在「去重 skew 秩」vs「冻结 skew 秩」上的回测差异

三路 timeline（同一回测引擎 va_composite_p1_cap / va_composite_p5_dedup）:
  F = classifier_v31_timeline.parquet        (冻结 tier，历史 B0 基线)
  C = timeline_ctrl.parquet                  (当前分类器 + 冻结秩 -> 应==F)
  M = timeline_calA_min.parquet              (当前分类器 + 去重 skew 秩 -> 唯一修复)

对每路跑:
  P1: B0(Cap=1.0) + Cap 扫描 [1.0,1.2,2.0,4.0,5.0]，dedup=8h
  P5: dedup 扫描 [4h,8h,12h]，Cap=5.0 定档

输出: project_data/ai_tmp/p0_calib/ab_compare.md
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402
import va_composite_p5_dedup as P5  # noqa: E402

FROZEN = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
CTRL = Path("project_data/ai_tmp/p0_calib/timeline_ctrl.parquet")
MIN = Path("project_data/ai_tmp/p0_calib/timeline_calA_min.parquet")
OUT = Path("project_data/ai_tmp/p0_calib")
OUT.mkdir(parents=True, exist_ok=True)

CAPS = [1.0, 1.2, 2.0, 4.0, 5.0]
DEDUP_SWEEP = [4, 8, 12]


def run_p1(tl: Path, tag: str) -> dict:
    P1.TIMELINE_PATH = tl
    P1.OUT_DIR = OUT / f"ab_{tag}_p1"
    P1.OUT_DIR.mkdir(parents=True, exist_ok=True)
    P1.CAPS = CAPS
    P1.DEDUP_HOURS = 8
    P1.main()
    # 重新读取刚写出的 metrics：直接复用模块内逻辑不可得，改为从 summary 解析不便，
    # 故在 main 内已打印；这里返回 None，由下方统一打印 summary 文本。
    return None


def run_p5(tl: Path, tag: str) -> None:
    P1.TIMELINE_PATH = tl          # P5 复用 P1 的 load_events/simulate
    P5.OUT_DIR = OUT / f"ab_{tag}_p5"
    P5.OUT_DIR.mkdir(parents=True, exist_ok=True)
    P5.CAP = 5.0
    P5.main()


def main() -> None:
    print("=" * 70)
    print("va-composite · P0.1（干净版）· 三路 A/B 分解")
    print("=" * 70)
    for tl, tag in [(FROZEN, "F"), (CTRL, "C"), (MIN, "M")]:
        print(f"\n########## 路 {tag}: {tl.name} ##########")
        print(f"----- P1 (B0 + Cap 扫描, dedup=8h) -----")
        run_p1(tl, tag)
        print(f"----- P5 (dedup 扫描, Cap=5.0) -----")
        run_p5(tl, tag)
    print("\n[完成] 三路 A/B 已分别写出 ab_F*/ab_C*/ab_M* 子目录。")


if __name__ == "__main__":
    main()
