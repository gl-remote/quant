# AI 行为规范约束

> 版本: 2.1.0 | 更新日期: 2026-05-24

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

vn.py 为可选依赖，未安装时系统自动启用降级引擎。

---

## 二、项目结构

```
quant/
├── main.py                 # 命令行入口（子命令模式）
├── conf.yaml               # 基础配置（提交版本控制）
├── conf.local.yaml         # 本地密钥覆盖（不提交，.gitignore 已排除）
├── conf.example.yaml       # 配置模板
├── requirements.txt
├── plan.md                 # 项目改进计划（仅含未解决问题）
├── .plan/                  # 版本规划归档
│   ├── plan.1.0.0.log.md   #   初始审计结果
│   ├── plan.2.0.0.log.md   #   文档同步更新
│   └── plan.3.0.0.log.md   #   中危以上问题修复记录
├── AI_BEHAVIOR_RULES.md    # 本文档
├── run.sh / activate_env.sh
│
├── config/                 # 配置管理（YAML 分层合并）
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

降级引擎（`_run_fallback_backtest`）同样受此约束，已通过 `MaStrategyCore` 实现。

### 规则 4.3: 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件名 | `snake_case` | `data_loader.py`, `config_manager.py` |
| 类名 | `PascalCase` | `VnpyBacktestEngine`, `MaStrategyCore`, `TqsdkImports` |
| 函数/方法 | `snake_case` | `run_full_pipeline`, `parse_symbol_exchange` |
| 私有方法 | `_` 前缀 | `_run_single_backtest`, `_calc_max_drawdown` |
| 常量 | `UPPER_SNAKE_CASE` | `HAS_VNPY` |

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
| `plan.md` | 新问题发现——已修复问题从 plan.md 移除，归档至 `.plan/plan.{version}.log.md` |

---

## 十、规划文档归档规范

`.plan/` 目录存放各版本的规划快照，文件命名格式为 `plan.{version}.log.md`：

```
.plan/
├── plan.1.0.0.log.md    # 初始审计：17 个问题 + 8 类缺失元素
├── plan.2.0.0.log.md    # 文档同步：AI_BEHAVIOR_RULES 更新
└── plan.3.0.0.log.md    # 问题修复：14 个中危以上问题全部解决
```

根目录 `plan.md` 仅保留**当前未解决问题**和未来规划。已修复的问题从 `plan.md` 移除，完整记录见对应版本日志文件。

---

## 十一、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.1.0 | 2026-05-24 | 新增规则 4.2（核心策略复用）、4.6（构造函数校验）、4.7（模块状态管理）、4.8（工具函数抽象）；新增第十章（规划文档归档规范） |
| 2.0.0 | 2026-05-24 | 全面重写：新增项目结构、CLI 命令、编码规范、回测流水线、错误处理、Git 工作流、测试要求、文档规范 |
| 1.0.0 | 2026-05-23 | 初始版本：Python 环境激活规则 |