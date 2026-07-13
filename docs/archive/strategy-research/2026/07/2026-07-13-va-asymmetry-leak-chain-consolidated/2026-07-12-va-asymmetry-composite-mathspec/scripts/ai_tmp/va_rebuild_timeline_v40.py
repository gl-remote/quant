"""
文件级元信息：
- 创建背景：va-asymmetry-composite spec §1.3 六阵营命名与旧 stage4 timeline (UP*/DN*)
  不匹配；B 层策略需要读取按新分类器输出的 (contract, date) → tier 表格才能开仓。
- 用途：一次性脚本——读取 dataset_full.parquet 里已计算好的 A3_skew / daily_atr_10_bps /
  trend_ret_10d，喂给 workspace.strategies.classifiers.poc_va.evaluate_dataset，
  产出 spec §1.3 六阵营命名的 timeline parquet，供 vnpy 回测策略消费。
- 注意事项：临时脚本，仅用于打通端到端回测口径；A 层生产管线的正式迁移由 stage4
  管线负责，不在本脚本范围内。输出落到 project_data/ai_tmp/，可随时清理。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from workspace.strategies.classifiers.poc_va import (  # noqa: E402
    ClassifierConfig,
    evaluate_dataset,
)

SRC = REPO_ROOT / "project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"
OUT_DIR = REPO_ROOT / "project_data/ai_tmp"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "va_timeline_v40.parquet"


def main() -> None:
    df = pd.read_parquet(SRC)
    # dataset_full 已含 A3_skew / daily_atr_10_bps / trend_ret_10d，
    # 直接映射到 evaluate_dataset 期望的列名。
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df = df.rename(
        columns={
            "daily_atr_10_bps": "daily_atr",
            "trend_ret_10d": "trend_ret_M",
        }
    )
    out = evaluate_dataset(df, ClassifierConfig())
    print("tier 分布：")
    print(out["tier"].value_counts(dropna=False))

    # 只保留策略消费需要的列
    keep = ["contract", "event_time", "tier", "direction"]
    if "daily_atr" in out.columns:
        keep.append("daily_atr")
    slim = out.loc[out["tier"].notna(), keep].copy()
    # 用 daily_atr_10_bps 命名回写（策略 _load_a_table 兼容读该名）
    if "daily_atr" in slim.columns:
        slim = slim.rename(columns={"daily_atr": "daily_atr_10_bps"})
    slim.to_parquet(OUT, index=False)
    print(f"written: {OUT}  rows={len(slim)}")


if __name__ == "__main__":
    main()
