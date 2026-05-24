# AI 行为规范约束

> 版本: 0.2.0-dev | 更新日期: 2026-05-24

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

```
quant/
├── main.py                 # 命令行入口（子命令模式）
├── plan.md                 # 项目改进计划（仅含未解决问题）
├── AI_BEHAVIOR_RULES.md    # 本文档
├── .memory_rules.md         # 知识图谱记忆规则
├── run.sh / activate_env.sh
├── .plan/                  # 版本规划归档
│   ├── plan.0.0.1.log.md   #   初始审计结果
│   ├── plan.0.0.2.log.md   #   文档同步更新
│   ├── plan.0.0.3.log.md   #   中危以上问题修复记录
│   ├── plan.0.0.4.log.md   #   测试框架建立
│   ├── plan.0.0.5.log.md   #   规划行为模式建立
│   ├── plan.0.0.6.log.md   #   M2 工程化深度规划
│   └── plan.0.0.7.log.md   #   归档优先规范落地
├── tests/                  # 测试目录 (127 用例)
│
├── config/                 # 配置管理（YAML 分层合并）
│   ├── conf.yaml           #   基础配置（提交版本控制）
│   ├── conf.local.yaml     #   本地密钥覆盖（不提交）
│   └── conf.example.yaml   #   配置模板
├── strategies/             # 策略子系统
│   ├── core/               #   纯业务逻辑，零框架依赖
│   └── gateways/           #   vn.py / 天勤 网关适配器
├── backtest/               # 回测子系统（引擎+数据+报告+对比）
├── data/                   # 数据子系统（导出+SQLite）
└── doc/                    # 项目文档
```

---

## 三、CLI 命令

系统使用**子命令模式**（非 `--mode` 参数），命令格式为：

```
python main.py <子命令> [参数]
```

| 子命令 | 用途 | 示例 |
|--------|------|------|
| `export` | 从天勤导出历史 K 线 CSV | `python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01` |
| `test` | 离线策略逻辑验证（不联网） | `python main.py test` |
| `backtest` | vn.py 三阶段回测 | `python main.py backtest --symbol DCE.m2509` |
| `tq-backtest` | 天勤 SDK 回测（旧版兼容） | `python main.py tq-backtest --symbol DCE.m2109 --gui` |
| `live` | 实盘/模拟交易 | `python main.py live --symbol DCE.m2509 --gui` |

> **禁止**使用旧版 `--mode backtest` 格式，该格式已废弃。

---

## 四、编码规范

### 规则 4.1: 架构约束

**核心+网关模式是强制性架构约束。** 所有策略业务逻辑必须写入 `strategies/core/`，不得包含任何框架依赖。框架集成代码仅允许存在于 `strategies/gateways/`。

```
strategies/core/ma_strategy.py      ← 允许: 纯算法（SMA计算、信号检测）
strategies/gateways/vnpy_gateway.py ← 允许: vn.py 适配
strategies/gateways/tqsdk_gateway.py← 允许: 天勤适配
```

新增网关时必须：继承核心策略 → 转换数据格式 → 委托调用核心方法。

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
| `doc/*.md` | API 变更、配置参数增删、架构调整 |
| `AI_BEHAVIOR_RULES.md` | 编码规范变更、新操作规则 |
| `.memory_rules.md` | Knowledge Graph 实体/关系类型变更 |
| `plan.md` | 行动项完成 → 归档重规划；新问题发现；里程碑推进；风险评估变更——遵循规则 12.4-12.5（归档优先 → 重新规划） |

---

## 十、规划文档归档规范

`.plan/` 目录存放各版本的规划快照，文件命名格式为 `plan.{version}.log.md`：

```
.plan/
├── plan.0.0.1.log.md    # 初始审计：17 个问题 + 8 类缺失元素
├── plan.0.0.2.log.md    # 文档同步：AI_BEHAVIOR_RULES 更新
└── plan.0.0.3.log.md    # 问题修复：14 个中危以上问题全部解决
```

根目录 `plan.md` 仅保留**当前未解决问题**和未来规划。已修复的问题从 `plan.md` 移除，完整记录见对应版本日志文件。

---

## 十一、Knowledge Graph Memory

### 规则 11.1: 知识图谱持久化（强制执行）

项目使用 Knowledge Graph Memory 跨会话保持关键信息。详细规则见 [.memory_rules.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.memory_rules.md)。

核心要求：

| 场景 | 必须创建 |
|------|---------|
| 项目首次加载 | Module + Strategy 实体及依赖关系 |
| 发现新问题 | Issue 实体 |
| 修复问题 | Fix 实体 + `resolved_by` 关系 |
| 新增模块/类 | 对应实体及关系 |
| 文档变更 | 更新 Document 实体的 observations |

### 规则 11.2: 实体类型

| 类型 | 命名格式 | 示例 |
|------|---------|------|
| Module | `{子系统}/{模块名}` | `backtest/backtest_engine` |
| Strategy | `{ClassName}` | `MaStrategyCore` |
| Issue | `{issue_id}` | `C1` |
| Fix | `fix-{issue_id}` | `fix-C1` |
| Config | `{section}.{key}` | `backtest.initial_capital` |
| Document | `{路径不含扩展名}` | `doc/architecture` |

### 规则 11.3: 核心关系

| 关系 | 含义 |
|------|------|
| `imports` | 模块导入依赖 |
| `implements` | 网关实现核心策略 |
| `depends_on` | 依赖外部框架 |
| `found_in` | 问题所在文件 |
| `resolved_by` | 问题被修复解决 |
| `tracks` | 文档跟踪问题 |

---

## 十二、规划行为模式

### 规则 12.1: plan.md 是干净的行动指南

`plan.md` 是项目的**唯一规划权威文档**，且必须保持**干净、清晰**——只包含当前待处理的内容。

**plan.md 中不应出现**：
- ✅ 完成标记或 ~~删除线~~
- "已完成"、"已修复"、"已缓解" 的章节/表格
- 已关闭的风险项
- 已完成的行动项

**历史记录全部在 `.plan/` 归档中**。每次打开 plan.md 看到的应是一份可直接指导下一步行动的任务清单。

### 规则 12.2: 工作前必须审阅 plan.md

每次开始重要工作会话（用户提出涉及代码变更、问题修复、功能开发的请求）时，**必须**先阅读 `plan.md`。

审阅清单：
- 当前版本号和所在阶段
- 待解决问题及优先级
- 待完成的行动项
- 当前里程碑的推进状态
- 当前指标与目标差距

### 规则 12.3: 推进优先级

按以下顺序推进 plan.md 中的事项：

```
严重问题 (Critical) → 高危问题 (High) → 中危问题 (Medium)
→ 高优先级行动项 → 中优先级行动项
→ 当前里程碑 → 下一里程碑
→ 低危问题 (Low) → 低优先级行动项
```

同一优先级内，优先解决有依赖关系的前置事项（如先建测试框架再做 CI）。

### 规则 12.4: 归档优先原则（强制执行）

**每次修改 plan.md 前，必须先将当前版本完整归档。**

| 步骤 | 操作 |
|------|------|
| 1 | 将当前 `plan.md` 的完整内容归档至 `.plan/plan.{当前版本号}.log.md` |
| 2 | 归档文件需包含：变更概述、各章节快照、已完成项说明、项目状态快照 |
| 3 | 确保所有已完成事项的历史信息完整记录在归档中 |

归档是重新规划的前置步骤，不可跳过。归档完成后方可进入规则 12.5 流程。

### 规则 12.5: 重新规划流程

归档完成后，从头生成新的 `plan.md`：

| 步骤 | 操作 |
|------|------|
| 1 | **确认**：逐一检查每个剩余问题是否依然存在，已自然消失的移除 |
| 2 | **添加**：将新发现问题纳入对应问题表格 |
| 3 | **排序**：根据当前阶段重新排列优先级，调整行动项顺序 |
| 4 | **删除**：移除所有已完成项（✅/删除线/已完成标记/已关闭风险） |
| 5 | **更新**：刷新衡量指标的当前值 |
| 6 | **写入**：生成干净的 plan.md，版本号递增 |
| 7 | **同步**：更新知识图谱中相关实体 |

plan.md 只保留**剩余待处理**内容。版本记录表保留（含归档链接），但仅为元数据。

### 规则 12.6: 版本号规则

`plan.md` 的版本号采用 `主版本.次版本.修订号` 格式：

- **修订号** (`0.0.x`) 递增：每次重新规划、行动项完成
- **次版本号** (`0.x.0`) 递增：里程碑完成、阶段性总结
- **主版本号** (`x.0.0`) 递增：架构重大变更

每次版本变更在 `plan.md` 版本记录表中新增一行，包含归档链接。**每次重写 plan.md 都必须递增版本号。**

### 规则 12.7: 发现新问题的处理流程

| 步骤 | 操作 |
|------|------|
| 1 | 评估严重程度（严重 / 高 / 中 / 低） |
| 2 | 分配 ID（按严重级别：Cx / Hx / Mx / Lx） |
| 3 | 添加至 plan.md 对应问题表格 |
| 4 | 创建对应 Issue 实体到知识图谱 |
| 5 | 如问题可立即修复，修复后触发规则 12.4-12.5 归档重规划流程 |

### 规则 12.8: 行动项生命周期

```
pending → in_progress → 完成（触发归档重规划，从 plan.md 移除）
   ↑                        │
   └── 如遇阻塞 ←───────────┘
```

处于 `in_progress` 状态时，plan.md 中仅更新状态不触发归档。完成后**必须**执行规则 12.4-12.5（归档 → 重规划），完成后项从新 plan.md 中移除。阻塞时注明原因，不标记完成。

### 规则 12.9: 规划文档与行为规范的一致性

`plan.md` 和 `AI_BEHAVIOR_RULES.md` 的版本号**保持独立**。行为规范定义"如何做"，plan.md 定义"做什么"。行为规范变更时不需同步更新 plan.md 版本，反之亦然。
