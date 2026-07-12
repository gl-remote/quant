# raw-outputs：structural-shaping-alpha 阶段 1 实验输出归档

> 类型：Archive / 原始实验输出数据  
> 状态：已归档  
> 所属阶段：structural-shaping-alpha 阶段 1 gatekeeper（2026-07-06）  
> 批次入口：[../README.md](../README.md) · [../stage1-gatekeeper-report.md](../stage1-gatekeeper-report.md)

## 1. 目录用途

本目录保存 structural-shaping-alpha 阶段 1 gatekeeper 与 First-Passage Designer 生成的原始实验输出（JSON 汇总 + CSV 明细 + 表数据）。

这些数据是 [stage1-gatekeeper-report.md](../stage1-gatekeeper-report.md) 表格的来源，也是 [compare_cost_models.py](../raw-scripts/compare_cost_models.py) 对比脚本读取的输入。

## 2. 子目录说明

| 子目录 | 内容 | 数量 | 来源脚本 |
|:---|:---|:---:|:---|
| `gatekeeper-results/` | gatekeeper 全部 37 个输出（JSON 汇总 + CSV 明细），含 3 档 SCALE × flat/real-cost × barrier / gatekeeper / regime_split | 37 个文件 | `raw-scripts/structural_shaping_gatekeeper.py` · `barrier_geometry_baseline.py` · `regime_split_er.py` |
| `first-passage-lookup/` | First-Passage Designer v1 生成的 5 张对照表的原始 CSV（表 1~5 × 3 次运行时间戳） | 16 个 CSV | `raw-scripts/first_passage_designer.py` 的 `tables` 子命令 |

### gatekeeper-results/ 命名约定

```
<脚本名>_<分组_tag>_<YYYYMMDD>_<HHMMSS>.{json,csv}
```

- **脚本名**：`structural_shaping_gatekeeper` · `barrier_geometry_baseline` · `regime_split_er20`
- **分组_tag**：
  - 无后缀 = scale1 默认首次
  - `scale{1,3,5}` = KF-6 的 3 档 K 距离倍率
  - `realcost` = KF-5 真实成本模型（对比 flat 低估 4.5 倍）

## 3. 脚本旧路径引用说明（关于 compare_cost_models.py）

归档脚本 [compare_cost_models.py](../raw-scripts/compare_cost_models.py) 中：

```python
ROOT = Path(__file__).resolve().parents[2] / "project_data" / "research" / "structural_shaping_gatekeeper"
```

**写入的是归档时的真实路径，作为历史记录保留**。搬入本目录后，若需要再次运行该脚本，应将 `ROOT` 改写为：

```python
ROOT = Path(__file__).resolve().parent.parent / "raw-outputs" / "gatekeeper-results"
```

## 4. 与阶段报告的对应关系

- `gatekeeper-results/structural_shaping_gatekeeper_{20260706_154518,20260706_160437}.{csv,json}`  
  → `stage1-gatekeeper-report.md` §2 主 gatekeeper 结果
- `gatekeeper-results/structural_shaping_gatekeeper_scale{1,3,5}_{flat,realcost}_*`  
  → KF-5（成本模型低估 4.5 倍）× KF-6（近距/远距边界）
- `gatekeeper-results/barrier_geometry_baseline_scale{1,3,5}_*`  
  → §8.2 几何 baseline 参照
- `gatekeeper-results/regime_split_er20_*`  
  → §8.5 regime 拆分 ER 结构
- `first-passage-lookup/table{1..5}_*`  
  → [first-passage-lookup-tables.md](../first-passage-lookup-tables.md) 对应 5 张表的原始数据
