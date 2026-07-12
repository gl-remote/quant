"""
文件级元信息：
- 创建背景：阶段 4 · 12 格深化验证需要扩容数据 · 现有 14 个品种每个只有 2 合约
  需要补齐历史合约 · 让每品种 6-8 合约 · 独立日 45-90 / 类
- 用途：批量拉取历史合约的 5m bar 数据（tqsdk）
- 注意事项：单次运行约 2-3 小时 · 每合约 2-3 分钟 · 若某合约拉取失败继续下一个
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

# 扩容合约清单 · 60 个合约（每品种 4-5 个历史）
# 命名规则：CZCE.XX (3 位年月 · 如 405 = 2024-05) · DCE/SHFE (4 位年月 · 如 2405)
CONTRACTS_TO_EXPORT = [
    # ===== CZCE 品种（补历史） =====
    # CF · 棉花（已有 509 · 601）
    "CZCE.CF401", "CZCE.CF405", "CZCE.CF409", "CZCE.CF501", "CZCE.CF505",
    # FG · 玻璃（已有 509 · 601）
    "CZCE.FG401", "CZCE.FG405", "CZCE.FG409", "CZCE.FG501", "CZCE.FG505",
    # MA · 甲醇（已有 509 · 601）
    "CZCE.MA401", "CZCE.MA405", "CZCE.MA409", "CZCE.MA501", "CZCE.MA505",
    # OI · 菜油（已有 509 · 601）
    "CZCE.OI401", "CZCE.OI405", "CZCE.OI409", "CZCE.OI501", "CZCE.OI505",
    # RM · 菜粕（已有 509 · 601）
    "CZCE.RM401", "CZCE.RM405", "CZCE.RM409", "CZCE.RM501", "CZCE.RM505",
    # TA · PTA（已有 509 · 601）
    "CZCE.TA401", "CZCE.TA405", "CZCE.TA409", "CZCE.TA501", "CZCE.TA505",

    # ===== DCE 品种（补历史） =====
    # c · 玉米（已有 2601 · 2603 · 2605）
    "DCE.c2401", "DCE.c2405", "DCE.c2409", "DCE.c2501", "DCE.c2505", "DCE.c2509",
    # cs · 玉米淀粉（已有 2601 · 2603 · 2605）
    "DCE.cs2401", "DCE.cs2405", "DCE.cs2409", "DCE.cs2501", "DCE.cs2505", "DCE.cs2509",
    # i · 铁矿石（已有 2509 · 2601）
    "DCE.i2401", "DCE.i2405", "DCE.i2409", "DCE.i2501", "DCE.i2505",
    # y · 豆油（已有 2509 · 2601）
    "DCE.y2401", "DCE.y2405", "DCE.y2409", "DCE.y2501", "DCE.y2505",

    # ===== INE 品种（补历史） =====
    # sc · 原油（已有 2509 · 2512）
    "INE.sc2503", "INE.sc2506",

    # ===== SHFE 品种（补历史） =====
    # ag · 白银（已有 2509 · 2601）
    "SHFE.ag2401", "SHFE.ag2405", "SHFE.ag2412", "SHFE.ag2505",
    # al · 铝（已有 2509 · 2601）
    "SHFE.al2401", "SHFE.al2405", "SHFE.al2409", "SHFE.al2501", "SHFE.al2505",
    # au · 黄金（已有 2508 · 2512）
    "SHFE.au2404", "SHFE.au2408", "SHFE.au2412",
    # cu · 铜（已有 2509 · 2601）
    "SHFE.cu2401", "SHFE.cu2405", "SHFE.cu2409", "SHFE.cu2501", "SHFE.cu2505",
    # hc · 热轧卷板（已有 2505 · 2510）
    "SHFE.hc2401", "SHFE.hc2410", "SHFE.hc2601",
]


def export_contract(symbol: str) -> tuple[bool, str]:
    """拉取单个合约的 5m 数据 · 返回 (成功, 消息)."""
    try:
        result = subprocess.run(
            ["uv", "run", "python", "main.py", "export",
             "--env", "backtest",
             "--symbol", symbol,
             "--interval", "5m"],
            capture_output=True, text=True, timeout=300,
            cwd="/Users/gaolei/Documents/src/quant",
        )
        if result.returncode == 0 and "导出成功" in result.stdout:
            # 解析行数
            for line in result.stdout.split("\n"):
                if "导出完成" in line:
                    return True, line.split("|")[-1].strip()
            return True, "success"
        else:
            return False, result.stderr[-200:] if result.stderr else "unknown error"
    except subprocess.TimeoutExpired:
        return False, "timeout(5min)"
    except Exception as e:
        return False, str(e)


def main():
    csv_dir = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
    total = len(CONTRACTS_TO_EXPORT)

    print(f"=== 阶段 4 数据扩容 · 拉取 {total} 个历史合约 ===")
    print(f"预计时间：{total * 2.5 / 60:.1f} - {total * 3.0 / 60:.1f} 小时\n")

    start = time.time()
    stats = {"ok": 0, "skip": 0, "fail": 0}
    fails = []

    for i, symbol in enumerate(CONTRACTS_TO_EXPORT, 1):
        # 检查是否已存在
        existing = list(csv_dir.glob(f"{symbol}.tqsdk.5m.csv"))
        if existing:
            print(f"[{i:>3}/{total}] {symbol} · 已存在 · skip")
            stats["skip"] += 1
            continue

        t0 = time.time()
        ok, msg = export_contract(symbol)
        dt = time.time() - t0
        eta_min = (total - i) * dt / 60

        if ok:
            print(f"[{i:>3}/{total}] {symbol} · ✅ {msg[:80]} · {dt:.0f}s · ETA {eta_min:.0f}m")
            stats["ok"] += 1
        else:
            print(f"[{i:>3}/{total}] {symbol} · ❌ {msg[:80]} · {dt:.0f}s")
            stats["fail"] += 1
            fails.append((symbol, msg[:100]))

    elapsed = time.time() - start
    print(f"\n=== 完成 · {elapsed / 60:.1f} 分钟 ===")
    print(f"新增：{stats['ok']}  跳过：{stats['skip']}  失败：{stats['fail']}")
    if fails:
        print("\n失败明细：")
        for sym, msg in fails:
            print(f"  {sym}: {msg}")


if __name__ == "__main__":
    main()
