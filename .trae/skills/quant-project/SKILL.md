---
name: "quant-project"
description: "Provides quant project architecture, environment, symbol, path, and code style rules. Invoke when working anywhere in this quant repo."
---

# Quant Project

本 skill 记录 quant 仓库的基础项目规则。用于进入 `quant/` 仓库后的一般开发、阅读、修改和验证。

## 环境规则

本项目使用 **uv** 管理 Python 环境（`.venv` 在仓库根）。

所有 Python 命令必须以 `uv run` 开头：

| 正确 | 错误 |
|------|------|
| `uv run python script.py` | `python script.py` |
| `uv run pytest workspace/tests/ --tb=short` | `pytest workspace/tests/` |
| `uv run mypy workspace/` | `mypy workspace/` |
| `uv sync --all-groups` | `pip install ...` |

例外：`ruff` 是独立 CLI，可直接调用 `ruff check ...` / `ruff format ...`，也可 `uv run ruff ...`。

新机器一次性 setup：

```bash
brew install ta-lib
uv sync --all-groups
```

## 项目结构

```text
quant/
├── main.py                 # CLI 入口
├── workspace/
│   ├── config/             # TOML + Pydantic 配置管理
│   ├── data/               # 数据管理、SQLite、统一 project_data 路径
│   ├── backtest/           # 回测引擎、参数优化、Walk-Forward
│   ├── strategies/         # 策略模块（框架无关）
│   ├── report/             # React SPA 报告系统
│   ├── cli/                # 命令行接口
│   ├── common/             # 公共工具层
│   ├── packages/contracts/ # Report JSON schema
│   └── tests/              # 测试
├── docs/
│   ├── roadmap/            # 阶段规划、研究方向、评价标准
│   ├── workbench/          # 当前研究中的实验记录、临时结论，以及 AI 生成的临时研究脚本 / 策略 / 中间数据（详见 quant-research-layout skill）
│   ├── issues/             # 实验中发现的底层框架问题
│   └── archive/            # 已稳定、可长期引用的归档文档
├── scripts/
│   ├── analysis/           # 简单数据分析工具，从 csv / 输出数据快速得到结论
│   ├── test/               # 测试自动化内部模块，由 scripts/test.sh source
│   ├── test.sh             # 测试自动化统一入口，pre-commit / CI / 人工命令共用
│   └── tools/              # 用户简易使用脚本，偏长期保留
└── project_data/           # 本地数据、报告、日志、缓存（不提交）
```

## 符号格式

- 项目内：`EXCHANGE.SYMBOL`，如 `DCE.m2601`。
- vnpy：`SYMBOL.EXCHANGE`，如 `m2601.DCE`。
- 永远不要重新解析 vnpy 格式的字符串。

## 配置优先级

```text
CLI 参数 > workspace/config/conf.local.toml > workspace/config/conf.toml > Pydantic 默认值
```

代码中使用：

```text
value = cli_arg if cli_arg else config.field
```

CLI 固定参数回测：

```text
--strategy-params > --config / conf.local.toml > conf.toml > 策略 dataclass 默认值
```

## 本地数据目录

- CSV：`project_data/market_data/csv/`
- SQLite：`project_data/database/quant_shared.db`
- Reports：`project_data/reports/`
- Raw logs：`project_data/logs/`
- Caches：`project_data/cache/`
- Profile：`project_data/profiles/`
- Coverage：`project_data/coverage/`

**AI 生成的临时研究资产统一放到 `docs/workbench/`**（包括临时脚本、临时策略、临时中间数据/图表），不再使用 `scripts/ai_tmp/` 与 `project_data/ai_tmp/`。归档规则详见 `quant-research-layout` skill。

统一路径函数在 `workspace/data/output_paths.py` 与 `workspace/report/output_paths.py`。业务代码不要硬编码本地数据子路径。

## 归档文档引用规则（防止口号式误读）

`docs/research/archived-notes/**` 下的任何结论（尤其是章节末的加粗总结句）在被引用、传播或推广到新主题/新场景之前，**必须**先完成以下检查。这条规则来自"归档结论 + 加粗修辞 + RAG 局部检索"三重放大机制会让 AI 把观察级结论误读成全局命题的教训。

### 引用检查清单（4 步）

1. **回溯适用域**：读原主题的 §1（假设章节）+ `README.md` + `freeze-summary.md`，明确以下五项：
   - **时间尺度**（5m / 15m / 1h / daily / …）
   - **barrier / 度量方式**（ATR 加性 / 百分比 / 对数收益 / …）
   - **仓位管理**（固定名义规模 / 凯利 / 百分比净值 / …）
   - **样本容量与 SE**（n、SE_FPT、显著性阈值）
   - **有效 combo 区间**（如 K_S ∈ [0.75, 2.5]、time_exit% < 5%）
2. **判定域内 / 域外**：
   - **域内引用**（当前场景完全落在上述五项之内）→ 允许直接引用原文数值 / 结论；
   - **域外引用**（任一项被推广，例如从 1h 推广到 daily、从固定名义规模改成凯利、从单笔推广到组合复利）→ **禁止直接引用**，必须回到 raw-scripts / raw-outputs 重跑一次 null 验证，或在下游文档明确标注"未在原适用域内验证"。
3. **加粗结论警告**：archived 文档章节末的加粗金句（形如"**X 精确成立**"、"**Y 收敛到 Z**"）是修辞压缩产物，**不得单独作为证据**。引用时必须同时携带本节的：数据表格 + SE / p-value + 适用域限定。
4. **引用链深度**：优先引用原始主题的具体命题 / 表格，不要从综述性摘要（如 `freeze-summary.md` 或 `research-status.md` 的一句总结）二手引用；二手引用需在引用处显式标注"转引自 XX"。

### 不允许的引用模式

- ❌ 仅凭"XX 主题证明了 Y"作为下游工作的假设基础，而不列举 XX 的操作框架；
- ❌ 不检查 SE / 显著性 / 适用域，直接把 P_win / RR / K_S 数值套用到新品种或新周期；
- ❌ 跨主题传播加粗金句而不同时携带原文假设列表；
- ❌ 把观察级归约（如"ν_implied ≈ 0"）等同于全分布断言（如"log S 是 martingale"）——两者不等价。

### 与其他 skill 的分工

- 归档目录布局与批次内容边界：`quant-research-layout`；
- 实验设计与证据门槛：`quant-research-methodology`；
- 本节只管"**读旧结论 → 用到新场景**"这一步的护栏，与上述两条 skill 交叉引用。

## 代码风格

- 行宽 ≤ 120。
- 双引号字符串。
- Import 顺序：stdlib → third-party → internal。
- mypy strict mode + 全类型标注。
- Ruff lint：E, W, F, I, N, UP, B, SIM。

常用检查：

```bash
ruff check workspace/ scripts/ main.py
ruff format --check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

## 源文件创建规则

创建任何新的源文件时，必须在尽可能靠近文件头的位置添加文件级别注释块，作为源代码级别的元信息。

要求：

- 适用范围：`.py`、`.ts`、`.tsx`、`.js`、`.sh`、`.sql` 等源代码/脚本文件；普通研究文档和 README 不适用。
- 位置：放在 shebang、encoding 声明、future import 等语言强制头部内容之后，常规 import / 业务代码之前。
- 内容必须说明：
  - 创建背景：为什么需要新增这个文件；
  - 用途：这个文件在项目中的职责；
  - 关键注意事项：运行口径、依赖假设、实验性质、是否长期保留、不要误用的边界。
- 注释块是文件级元信息，不替代函数/类文档，也不要写成变更日志。
- 内容要简洁，避免过程性流水账；如果文件是临时实验脚本，必须明确临时性和清理/归档边界。

Python 示例：

```python
"""
文件级元信息：
- 创建背景：用于补充 VA 回归分支验证，避免复用 CLI 报告链路造成批量实验过慢。
- 用途：执行轻量回测并输出结构诊断指标。
- 注意事项：仅用于同一 runner 下的相对比较，不直接替代清算口径结果。
"""
```

TypeScript 示例：

```ts
/**
 * 文件级元信息：
 * - 创建背景：为回测报告新增结构诊断展示入口。
 * - 用途：渲染结构诊断指标表格。
 * - 注意事项：只消费已生成的 report JSON，不在前端重新计算交易指标。
 */
```

## 调试提示

- `unrecognized arguments`：检查 CLI 参数注册与 workflow request 字段。
- `--mode single` 不存在或 `--strategy-params` 不识别：检查是否在包含 single backtest parameter overrides 的提交之后。
- `--strategy-params` JSON 报错：检查 shell 引号，推荐外层单引号、内部双引号。
- `not a valid Exchange`：检查项目格式 `EXCHANGE.SYMBOL` 与 vnpy 格式 `SYMBOL.EXCHANGE` 是否混用。
- `no such table`：检查 `project_data/database/quant_shared.db` 是否存在、迁移是否完成。
