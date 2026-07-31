"""
文件级元信息：
- 创建背景：time-barrier-selection 主题 Stage 1 形态归类。读取
  market_strength_scan.py 输出的 CSV, 对每条 (contract, T) 序列做形态归类。
- 用途：把扫描结果按实验计划 §2.5 的四类形态（单调衰减 / 平台+衰减 /
  先升后降 / 震荡）做归类, 输出一份形态汇总表 + 每合约的形态标签。
- 关键注意事项：
  - 不做 H0/H1 检验, 只按规则归类;
  - 仅用 s_abs_hat 做归类（不依赖 CI 方向判定, 避免双侧比较模糊带）;
  - T=∞ 行不进形态判定, 只作参考基线.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = REPO_ROOT / "docs" / "workbench" / "time-barrier-selection" / "outputs"


@dataclass(frozen=True)
class Morphology:
    contract: str
    label: str
    details: str

    def to_row(self) -> dict:
        return {"contract": self.contract, "label": self.label, "details": self.details}


def loglog_slope_r2(T: np.ndarray, s: np.ndarray) -> tuple[float, float]:
    """
    对 (T, s_abs) 在 log-log 坐标做线性回归, 返回 (alpha, R^2).
    斜率应为 -alpha (按实验计划形态 A 的定义).
    """
    mask = (s > 0) & np.isfinite(s) & np.isfinite(T)
    if mask.sum() < 2:
        return math.nan, math.nan
    x = np.log(T[mask])
    y = np.log(s[mask])
    if x.std() < 1e-12:
        return math.nan, math.nan
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    alpha = -slope
    return float(alpha), float(r2)


def detect_local_peak(T: np.ndarray, s: np.ndarray) -> int | None:
    """在内部点上找 s_abs 局部极大值的索引; 若多个则取 s 最大的那个."""
    if len(s) < 3:
        return None
    diff = np.diff(s)
    sign_changes = np.where(np.diff(np.sign(diff)) < 0)[0] + 1
    if len(sign_changes) == 0:
        return None
    candidates = [i for i in sign_changes if 0 < i < len(s) - 1]
    if not candidates:
        return None
    return int(max(candidates, key=lambda i: s[i]))


def detect_plateau_then_decay(T: np.ndarray, s: np.ndarray, eps: float = 0.1) -> int | None:
    """
    找"小 T 段平台 -> 之后衰减"形态: 存在 i, 满足
    - s[0..i] 段最大值-最小值 <= eps * s[0]
    - s[i+1..] 段严格单调递减
    """
    if len(s) < 3:
        return None
    for i in range(1, len(s) - 1):
        head = s[: i + 1]
        head_range = (head.max() - head.min()) / max(head.mean(), 1e-12)
        if head_range > eps:
            continue
        tail = s[i + 1 :]
        if len(tail) < 2:
            continue
        diffs = np.diff(tail)
        if np.all(diffs < 0):
            return i
    return None


def classify_series(T: np.ndarray, s: np.ndarray) -> tuple[str, str]:
    """
    对单合约的 (T, s_abs) 序列做形态归类.
    优先级: A 单调衰减 > B 平台+衰减 > C 先升后降 > D 其他.
    """
    # 排除 T=∞ 行 (既可能是 str 'inf', 也可能是 float inf)
    T = np.array(T)
    s = np.array(s)
    not_inf = np.array(
        [not (isinstance(t, str) and t == "inf")
         and not (isinstance(t, float) and not math.isfinite(t))
         for t in T],
        dtype=bool,
    )
    T = T[not_inf]
    s = s[not_inf]
    T = T.astype(float)
    s = s.astype(float)
    finite = np.isfinite(s) & np.isfinite(T) & (s > 0)
    T = T[finite]
    s = s[finite]
    if len(s) < 3:
        return "D", "样本不足"

    # A 单调衰减: log-log 线性 R^2 >= 0.8 且 alpha ∈ (0, 1)
    alpha, r2 = loglog_slope_r2(T, s)
    if math.isfinite(alpha) and math.isfinite(r2) and r2 >= 0.8 and 0.0 < alpha < 1.0:
        return "A", f"alpha={alpha:.3f}, R^2={r2:.3f}"

    # B 平台 + 衰减
    plateau_idx = detect_plateau_then_decay(T, s)
    if plateau_idx is not None:
        T_plateau = int(T[plateau_idx])
        return "B", f"T_plateau={T_plateau}"

    # C 先升后降
    peak_idx = detect_local_peak(T, s)
    if peak_idx is not None and 0 < peak_idx < len(s) - 1:
        left = s[:peak_idx]
        right = s[peak_idx + 1 :]
        if len(left) > 0 and len(right) > 0:
            side_drop = min(s[peak_idx] - left.min(), s[peak_idx] - right.min())
            if side_drop > 0 and side_drop / s[peak_idx] > 0.05:
                T_dagger = int(T[peak_idx])
                return "C", f"T_dagger={T_dagger}"

    return "D", "未匹配 A/B/C"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-prefix", default="stage1")
    args = parser.parse_args()

    csv_path = OUTPUT_DIR / f"{args.in_prefix}_scan.csv"
    if not csv_path.exists():
        print(f"[err] missing {csv_path}")
        return 1
    df = pd.read_csv(csv_path)
    # T 列: 数字 OR 字符串 'inf'
    df["T_raw"] = df["T"]
    df["T_disp"] = df["T"].astype(object)

    out_rows: list[dict] = []
    for contract, sub in df.groupby("contract"):
        sub = sub.copy()
        # 把 inf 行放最后; 其他按 int 升序
        sub["_sort_key"] = sub["T_raw"].apply(
            lambda x: (1, 0, 0) if x == "inf" or (isinstance(x, float) and not math.isfinite(x))
            else (0, 0, int(x))
        )
        sub = sub.sort_values("_sort_key")
        T_arr = sub["T_disp"].to_numpy()
        s_arr = sub["s_abs_hat"].to_numpy()
        label, details = classify_series(T_arr, s_arr)
        out_rows.append({"contract": contract, "label": label, "details": details})

    out_df = pd.DataFrame(out_rows)
    out_csv = OUTPUT_DIR / f"{args.in_prefix}_morphology.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"[done] wrote {out_csv}")
    print(out_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
