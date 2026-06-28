# CLI 入口未自动暴露 workspace 包路径

> 类型：已知限制 / 回测链路  
> 状态：已确认  
> 发现日期：2026-06-28  
> 发现分支：`experiment/structural-alpha-r1-ib-reacceptance`  
> 发现基准 hash：`af09c3d`  
> 修复提交 hash：待补  
> 关联实验：[structural-alpha-r1：Initial Balance 假突破重新接受 / 拒绝](../workbench/structural-alpha-r1-ib-reacceptance.md)  
> 相关代码：[main.py](../../main.py)，[pyproject.toml](../../pyproject.toml)

## 背景

这是项目已知的短期规避项：当前源码布局把业务包放在 `workspace/` 下，研究和脚本长期通过 `PYTHONPATH=workspace` 暴露包路径。`structural-alpha-r1` 的 IB 重新接受实验中再次触发该现象，因此记录为已确认限制，而不是阻塞性框架缺陷。

在实验中，需要按项目文档和 CLI 规则运行：

```text
uv run python main.py backtest ...
uv run python main.py report ...
```

但当前分支上直接执行 `uv run python main.py ...` 无法导入 `workspace` 下的业务包。

## 现象

最小复现：

```text
uv run python main.py --help
```

实际结果：

```text
Traceback (most recent call last):
  File "/Users/gaolei/Library/Mobile Documents/com~apple~CloudDocs/Documents/src/quant/main.py", line 17, in <module>
    from cli.main import main
ModuleNotFoundError: No module named 'cli'
```

加入 `PYTHONPATH=workspace` 后可以运行：

```text
PYTHONPATH=workspace uv run python main.py backtest ...
```

## 影响

| 影响面 | 说明 |
| --- | --- |
| 实验复现 | 文档中的标准 `uv run python main.py ...` 命令不可直接复现 |
| CLI 入口 | `main.py` 直接依赖顶层包名 `cli`，但运行时未自动把 `workspace` 放入搜索路径 |
| 研究结论 | 不影响本轮已经加 `PYTHONPATH=workspace` 跑出的策略结果，但影响复现实验命令的可靠性 |
| 后续实验 | 所有 CLI 回测和报告命令都需要临时加 `PYTHONPATH=workspace` |

## 最小复现方向

运行：

```text
uv run python main.py --help
```

预期：

```text
显示 CLI 帮助。
```

实际：

```text
ModuleNotFoundError: No module named 'cli'
```

## 当前处理建议

当前继续采用既有短期规避方案：

```text
PYTHONPATH=workspace uv run python main.py ...
```

更好的长期修复方向不是在每个脚本里临时 `sys.path.insert`，而是统一项目入口：

1. 在 `pyproject.toml` 中明确包发现 / editable 安装策略，让 `uv sync` 后 `workspace` 下包可被解释器发现；
2. 增加统一 console script，例如 `quant = "cli.main:main"` 或等价包装入口，研究命令改为 `uv run quant ...`；
3. 保留 `PYTHONPATH=workspace` 作为脚本兼容方案，逐步把文档中的直接 `uv run python main.py ...` 迁移到统一入口。

不建议的修复：

```text
在 main.py 或各个 scripts 中散落 sys.path 修改。
```

原因：这会隐藏真实包安装边界，并让 CLI、测试、脚本、IDE 的导入路径继续分裂。

在统一入口修复前，workbench 复现命令需标注 `PYTHONPATH=workspace`。

## 修复记录

待补。

## 验证记录

待补。
