# AI 行为规范约束

> 版本: 0.2.0-dev | 更新日期: 2026-05-25

---

## 一、环境与运行

### 规则 1.1: Python 环境（强制执行）

执行任何 Python 命令前，必须确保处于 `quant_trading` Conda 环境：

```bash
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading
# 或
./activate_env.sh
```

验证环境正确后继续：

```bash
which python  # 应指向 quant_trading 环境
python --version
```

### 规则 1.2: 工作目录

所有命令必须在项目根目录 `/Users/REDACTED_API_KEY/Documents/src/quant` 下执行，除非明确指定 `cwd`。

### 规则 1.3: 依赖安装

执行前确保依赖已安装：

```bash
pip install -r requirements.txt
```
vn.py 和 tqsdk 为强制依赖，不再支持降级模式。

---

## 二、项目结构

> 完整模块架构见 `plan.md` §1.2（唯一权威源）。以下为**文件修改速查表**——AI 需修改某功能时定位对应文件。

| 需求 | 应修改的文件 |
|------|------------|
| 新增策略 | `strategies/xxx.py` + `strategies/__init__.py` |
| 新增 CLI 命令 | `cli/commands/xxx.py` |
| 新增量化公式 | `common/formulas.py` + `tests/test_common.py` |
| 新增常量 | `common/constants.py` |
| 新增 Schema | `common/schemas.py` |
| 修改数据库表 | `data/models.py` + `data/store.py` |
| 修改报告格式 | `report/xxx.py` |
| 修改配置项 | `common/constants.py` (默认值) + `config/conf.yaml` |
| 修改回测引擎 | `backtest/vnpy_backtest_engine.py` |
| 新增桥接器 | `strategies/bridges/xxx.py` |

---

## 三、CLI 命令

系统使用**子命令模式**（非 `--mode` 参数），命令格式为：

```
python main.py <子命令> [参数]
```

| 子命令 | 用途 | 示例 |
|--------|------|------|
| `export` | 从天勤导出历史 K 线 CSV | `python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01` |
| `test` | 离线策略逻辑验证（不联网） | `python main.py test --strategy ma` |
| `backtest` | vn.py 三阶段回测 | `python main.py backtest --symbol DCE.m2509 --strategy ma` |
| `tq-backtest` | 天勤 SDK 回测（旧版兼容） | `python main.py tq-backtest --symbol DCE.m2109 --gui --strategy ma` |
| `live` | 实盘/模拟交易 | `python main.py live --symbol DCE.m2509 --gui --strategy ma` |

`--strategy` 参数支持三种传入方式:
- 简化名: `ma` → 找 `strategies/ma_strategy.py`
- 完整名: `ma_strategy` → 找 `strategies/ma_strategy.py`
- 带扩展名: `ma_strategy.py` → 找 `strategies/ma_strategy.py`

不指定 `--strategy` 时默认使用 ma 策略。

> **禁止**使用旧版 `--mode backtest` 格式，该格式已废弃。

---

## 四、编码规范

### 规则 4.1: 架构约束

**核心+桥接器模式是强制性架构约束。** 所有策略必须继承 `strategies.core.base.Strategy` 接口，策略文件放 `strategies/` 顶层。框架集成代码仅允许存在于 `strategies/bridges/`。

```
strategies/core/base.py              ← 策略抽象接口 (Strategy ABC)
strategies/ma_strategy.py            ← 均线策略实现 (继承 Strategy)
strategies/bridges/vnpy_bridge.py    ← vn.py 桥接器 (接收 Strategy 实例)
strategies/bridges/tqsdk_bridge.py   ← 天勤桥接器 (接收 Strategy 实例)
```

新增策略时：继承 `Strategy` → 实现全部抽象方法。新增桥接器时：接收 `Strategy` 实例 → 转换数据格式 → 委托调用核心方法。

### 规则 4.2: 核心策略复用（强制执行）

任何需要执行 SMA 计算、金叉/死叉检测、止盈止损判断的代码，**必须**通过 `MaStrategyCore` 或 `TradingConfig` 调用，严禁手动实现等效逻辑。

```
✅ core.calculate_sma(closes, period)        # 使用核心方法
✅ core.check_crossover(short, long, p1, p2) # 使用核心方法
❌ sum(closes[-period:]) / period            # 禁止手写 SMA
❌ prev_short <= prev_long and short > long  # 禁止手写信号检测
```

### 规则 4.3: 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件名 | `snake_case` | `data_loader.py`, `config_manager.py` |
| 类名 | `PascalCase` | `VnpyBacktestEngine`, `MaStrategyCore`, `TqsdkImports` |
| 函数/方法 | `snake_case` | `run_full_pipeline`, `parse_symbol_exchange` |
| 私有方法 | `_` 前缀 | `_run_single_backtest`, `_calc_max_drawdown` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |

### 规则 4.4: 代码风格

- **禁止**添加注释，除非用户明确要求
- 缩进：4 空格
- 文档字符串：保持现有风格一致
- 导入顺序：标准库 → 第三方库 → 项目内部模块
- 类型注解：所有公开方法必须标注参数和返回值类型

### 规则 4.5: 配置管理

- API 密钥、密码等敏感信息**必须**写入 `conf.local.yaml`，严禁写入 `conf.yaml`
- `conf.local.yaml` 已通过 `.gitignore` 排除，严禁手动 `git add`
- 新增配置参数应提供默认值，遵循 `.get(key, default)` 模式

### 规则 4.6: 构造函数输入校验

所有接收外部配置的构造函数（特别是引擎类）**必须**在初始化阶段校验参数合法性：

```python
class VnpyBacktestEngine:
    def __init__(self, config):
        self.initial_capital = float(config.get('initial_capital', 100000.0))
        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital 必须大于 0")
        # ... 其他参数同理
```

### 规则 4.7: 模块状态管理

**禁止**使用模块级可变字典或列表管理全局状态。改用类封装：

```python
# ❌ 禁止
_tq_imports = {}
def _import_tqsdk():
    if _tq_imports:
        return True
    _tq_imports.update(...)

# ✅ 允许
class TqsdkImports:
    def __init__(self):
        self._loaded = False
        self.TqApi = None
    def ensure(self) -> bool:
        ...
```

### 规则 4.8: 工具函数抽象

跨模块复用的解析逻辑**必须**提取为独立函数，禁止内联重复实现：

```python
# ✅ 统一入口：backtest/data_loader.py
def parse_symbol_exchange(symbol: str):
    ...
```

`data_loader.py` 和 `backtest_engine.py` 均通过此函数解析品种代码与交易所。

### 规则 4.9: 全局常量字典（强制执行）

项目内所有硬编码的业务字符串、魔术数字、状态码、标识符**必须**使用 `common/constants.py` 中定义的统一常量，严禁散落硬编码字面量。

```python
# ✅ 正确：使用统一常量
from common.constants import TRADE_ACTION_BUY, STATUS_SUCCESS, DEFAULT_INITIAL_CAPITAL
signal = Signal(action=TRADE_ACTION_BUY, reason=SIGNAL_GOLDEN_CROSS)
capital = bc.get('initial_capital', DEFAULT_INITIAL_CAPITAL)

# ❌ 禁止：硬编码魔术字符串/数字
signal = Signal(action='buy', reason='golden_cross')
capital = bc.get('initial_capital', 100000.0)
```

覆盖范围：
- 交易方向/动作（TRADE_ACTION_BUY/SELL, TRADE_DIRECTION_LONG/SHORT）
- 开平仓标识（TRADE_OFFSET_OPEN/CLOSE）
- 信号原因（SIGNAL_STOP_LOSS/TAKE_PROFIT/DEATH_CROSS/GOLDEN_CROSS）
- 状态码（STATUS_SUCCESS/FAILED, LOG_STATUS_*）
- CLI 命令名（CMD_EXPORT/BACKTEST/TQ_BACKTEST/TEST/LIVE/REPORT）
- 回测运行模式（MODE_SINGLE/BATCH/MULTI）
- 策略标识名（STRATEGY_MA）
- 所有配置默认值（DEFAULT_* 系列）
- 量化金融常数（TRADING_DAYS_PER_YEAR=252）
- 格式化字符串（FMT_*）

新增业务常量时：先评估是否已有适用的常量 → 若无，在 `constants.py` 中新增 → 全局替换。

### 规则 4.10: 统一计算公式库（强制执行）

项目内所有量化统计、交易指标、风控测算的计算**必须**使用 `common/formulas.py` 中定义的统一函数，严禁内联重复实现计算公式。

```python
# ✅ 正确：使用公式库
from common.formulas import total_return, win_rate, position_size
ret = total_return(initial_capital, final_equity, total_trades=total_trades)
wr = win_rate(win_trades, total_trades)
vol = position_size(capital, position_ratio, price, contract_size)

# ❌ 禁止：内联重复计算
ret = (final_equity - initial_capital) / initial_capital
wr = win_trades / max(total_trades, 1)
vol = capital * 0.1 / (price * 10)
```

已封装的公式（20+ 函数）：
- **收益类**: total_return(), annualized_return()
- **胜率盈亏比**: win_rate(), profit_factor()
- **交易成本**: trade_cost()
- **仓位计算**: position_size()
- **均线**: simple_moving_average()
- **交叉检测**: golden_cross(), death_cross()
- **止损止盈**: stop_loss_triggered(), take_profit_triggered()
- **持仓均价**: average_entry_price()
- **回撤**: drawdown_at_point()
- **统计**: avg_trades_per_day(), profitable_ratio(), convert_annual_factor()

新增公式时：先确认公式库中无等价的函数 → 在 `formulas.py` 中实现（纯函数、零依赖）→ 补充单元测试于 `tests/test_common.py` → 全局替换。

---

## 五、回测流水线

五阶段流水线顺序**不可更改**：

```
1. load_csv_data()        → 加载 CSV
2. split_datasets()       → 划分 train/val/test (60/20/20)
3. _run_single_backtest() ×3  → 三阶段独立回测
4. generate_dataset_report() ×3 → 生成 JSON 报告
5. compare_datasets()     → 过拟合评估 + 稳定性分析
```

修改任一步骤前，必须确认对下游步骤的影响。

---

## 六、错误处理

| 规则 | 说明 |
|------|------|
| 关键错误 | 使用 `raise` 抛出明确异常，附带描述信息 |
| 可恢复错误 | 使用 `logger.error()` + 返回 `None` 或错误字典 |
| 堆栈记录 | 所有 try/except 中使用 `logger.error("msg", exc_info=True)` |
| 禁止模式 | 禁止 `import traceback; traceback.print_exc()` |

---

## 七、Git 工作流

| 规则 | 说明 |
|------|------|
| 提交粒度 | 逻辑相关的修改合并为一次提交 |
| 提交信息 | `类型: 简述` 格式（如 `docs:`, `fix:`, `feat:`, `refactor:`） |
| 禁止提交 | `conf.local.yaml`、`*.csv`、`*.log`、`__pycache__/` |
| 提交前检查 | 确保代码可运行，基本功能无回归 |
| 版本变动 | **仅在合并到 main 分支时**更新版本号（pyproject.toml、AI_BEHAVIOR_RULES.md、plan.md），日常开发提交不改变版本号 |

---

## 八、测试要求

| 规则 | 说明 |
|------|------|
| 新功能 | 必须附带对应单元测试 |
| 修复 Bug | 必须附带回归测试 |
| 测试框架 | pytest |
| 测试位置 | `tests/` 目录，镜像源码结构 |
| 核心模块 | `MaStrategyCore`、`BacktestEngine`、`ConfigManager` 覆盖率目标 60%+ |

---

## 九、文档规范

| 文档 | 更新触发条件 |
|------|------------|
| `README.md` | CLI 变更、新增/删除功能 |
| `CHANGELOG.md` | Bug 修复、新增模块/功能、架构调整、删除功能 |
| `doc/*.md` | API 变更、配置参数增删、架构调整 |
| `AI_BEHAVIOR_RULES.md` | 编码规范变更、新操作规则 |
| `.memory_rules.md` | Knowledge Graph 实体/关系类型变更 |
| `plan.md` | 行动项完成 → 重新规划；新问题发现；里程碑推进；风险评估变更 |

### 规则 9.1: 文档职能边界（防止走形）

三份核心文档各自独占职责，**严禁内容越界**。修改任一文件时，必须遵守以下边界：

| 文件 | 独占职责（唯一权威源） | 严禁出现的内容 |
|------|----------------------|--------------|
| `plan.md` | 项目现状（代码行数/测试/覆盖率）、模块架构图、ADR 决策、缺陷清单（Bug/存量/架构发现）、路线图、风险评估、衡量指标 | ❌ 编码规范、CLI 命令格式、Git 工作流、KG 实体/关系类型定义 |
| `AI_BEHAVIOR_RULES.md` | 环境与运行命令、CLI 命令参考、编码规范（架构约束/命名/常量/公式库）、回测流水线、错误处理、Git 工作流、测试要求、文档更新触发条件、规划行为模式、**文件修改速查表**（§二） | ❌ 项目现状数据（行数/覆盖率）、缺陷清单详情、ADR 详情、KG 实体/关系类型表 |
| `.memory_rules.md` | KG 实体类型定义、关系类型定义、写入时机规则、命名约定 | ❌ 项目架构/模块清单副本、缺陷详情副本、ADR 副本、文档清单硬编码 |

**权威信息引用链**：
- 需要项目架构/缺陷/ADR → 查阅 `plan.md`（不动 `.memory_rules.md`）
- 需要 KG schema 定义 → 查阅 `.memory_rules.md`（不在 `AI_BEHAVIOR_RULES.md` 中重复实体/关系表）
- 需要编码/操作规则 → 查阅 `AI_BEHAVIOR_RULES.md`（不动 `plan.md`）

**修改检查清单**（提交前三文件前逐项确认）：
1. 新增内容是否只有一个文件作为权威源？
2. 是否在另一文件中有重复副本？→ 必须删除
3. plan.md 的架构图变更后，是否同步了 AI_BEHAVIOR_RULES.md 的速查表？→ 仅速查表需同步，架构图本身不复制
4. `.memory_rules.md` 是否混入了 plan.md 的内容？→ 应是纯 KG schema

**各信息类别的权威来源映射**：

| 需要查什么 | 去哪个文件（哪一节） |
|-----------|-------------------|
| 项目代码行数/测试数/覆盖率 | `plan.md` §1.1 |
| 模块架构图 | `plan.md` §1.2 |
| 架构决策记录 (ADR) | `plan.md` §1.3 |
| Bug 列表（含根因/修复/提交） | `plan.md` §3.1 |
| 缺陷清单（含严重度/说明） | `plan.md` §3.2-3.4 |
| 路线图/行动项 | `plan.md` §二 |
| 风险评估 | `plan.md` §四 |
| 衡量指标 | `plan.md` §五 |
| KG 实体/关系/写入规则 | `.memory_rules.md` §一~§五 |
| 编码规范/CLI/Git/测试规则 | `AI_BEHAVIOR_RULES.md` §四~§八 |
| 提交级变更记录 | `CHANGELOG.md` |

---

### 规则 9.2: 统一文档版本号（触发式同步）

**唯一版本号来源**：`pyproject.toml` 的 `version` 字段是项目所有文档版本的唯一权威源。

**版本标注格式**：所有文档在文件头第 3 行统一使用：
```
> 版本: X.Y.Z | 更新日期: YYYY-MM-DD
```
（`README.md` 用 Shields.io 徽章、`CHANGELOG.md` 用 Keep a Changelog H2 标题，其余全部使用此行格式）

**同步策略——触发式（Lazy Sync）**：
- **不**全量扫描、不主动巡检。仅在 AI 打开/修改/读取某文档时，检查其版本号是否与 `pyproject.toml` 一致。
- 不一致 → 立即修正文件头版本号（仅修版本号，不强制同步内容）。
- 内容同步遵循规则 9 的更新触发条件（API 变更才改 api-reference.md，配置变更才改 configuration.md，等等）。

**同步检查流**：
```
打开文档 → 读文件头第 3 行 → 版本号 == pyproject.toml version?
  ├─ 是 → 继续
  └─ 否 → 自动修正为当前版本，更新日期为今天
```

**pyproject.toml 版本变更时**：不需要在 CHANGELOG 之外另行批量改文档。下次 AI 碰到哪个文档就会自动对齐。

---

## 十、变更日志

**重要改动统一记录在 `CHANGELOG.md`**，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

| 场景 | 必须更新 |
|------|---------|
| Bug 修复（影响功能） | CHANGELOG.md `修复` 段 |
| 新增模块/功能 | CHANGELOG.md `新增` 段 |
| 架构调整/参数变更 | CHANGELOG.md `变更` 段 |
| 删除功能 | CHANGELOG.md `移除` 段 |

`plan.md` 也参照 CHANGELOG.md 记录改动，但仅记录里程碑级别的重要版本变更。

禁止再使用 `.plan/*.log.md` 归档方式。

---

## 十一、Knowledge Graph Memory

### 规则 11.1: 知识图谱持久化

项目使用 Knowledge Graph Memory 跨会话保持关键信息。**实体类型、关系类型、写入时机、命名约定**的完整定义见 [`.memory_rules.md`](file:///Users/REDACTED_API_KEY/Documents/src/quant/.memory_rules.md)（唯一权威源），本文件不重复。

项目现状数据（架构/缺陷/ADR/风险等）的权威来源为 [`plan.md`](file:///Users/REDACTED_API_KEY/Documents/src/quant/plan.md)，KG 实体通过 `found_in`/`resolved_by` 关系关联至其 issue_id。

---

## 十二、规划行为模式

### 规则 12.1: plan.md 是干净的行动指南

`plan.md` 是项目的**唯一规划权威文档**，只包含当前待处理的内容。已修复问题移入 CHANGELOG.md，不在 plan.md 中保留。

**plan.md 中不应出现**：已完成标记、~~删除线~~、"已完成/已修复"的章节或表格、已关闭的风险项、已完成的行动项。

### 规则 12.2: 工作前必须审阅 plan.md

每次开始重要工作会话时，**必须**先阅读 `plan.md`：当前版本号/阶段、待解决问题及优先级、待完成行动项、当前指标与目标差距。

### 规则 12.3: 推进优先级

严重问题 (Critical) → 高危问题 (High) → 中危问题 (Medium) → 高优先级行动项 → 中优先级行动项 → 当前里程碑 → 下一里程碑 → 低危问题 (Low) → 低优先级行动项。

同一优先级内，优先解决有依赖关系的前置事项。

### 规则 12.4: 重新规划流程

修改 plan.md 时，按以下流程操作：

| 步骤 | 操作 |
|------|------|
| 1 | **确认**：逐一检查每个剩余问题是否依然存在，已自然消失的移除 |
| 2 | **添加**：将新发现问题纳入对应问题表格 |
| 3 | **排序**：根据当前阶段重新排列优先级 |
| 4 | **删除**：移除所有已完成项（已修复 Bug、已补充文档等） |
| 5 | **更新**：刷新衡量指标的当前值 |
| 6 | **记录**：重要变更写入 CHANGELOG.md |

### 规则 12.5: 版本号规则

plan.md 的版本号采用 `主版本.次版本.修订号`：
- **修订号** (`0.0.x`) 递增：每次重新规划、行动项完成
- **次版本号** (`0.x.0`) 递增：里程碑完成
- **主版本号** (`x.0.0`) 递增：架构重大变更

### 规则 12.6: 发现新问题的处理流程

1. 评估严重程度（严重/高/中/低）→ 2. 分配 ID → 3. 添加至 plan.md 对应表格 → 4. 创建 Issue 实体到知识图谱 → 5. 如可立即修复，修复后触发规则 12.4 重新规划。

### 规则 12.7: 行动项生命周期

```
pending → in_progress → 完成（从 plan.md 移除，记录到 CHANGELOG.md）
   ↑                        │
   └── 如遇阻塞 ←───────────┘
```

完成后**必须**执行规则 12.4 重新规划，完成后项从 plan.md 移除。

### 规则 12.8: 规划文档与行为规范的一致性

`plan.md` 和 `AI_BEHAVIOR_RULES.md` 的版本号**保持独立**。行为规范定义"如何做"，plan.md 定义"做什么"。
