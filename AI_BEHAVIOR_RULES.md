# AI 行为规范约束

> 版本: 2.0.0 | 更新日期: 2026-05-24

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
├── plan.md                 # 项目改进计划
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
strategies/core/ma_strategy.py   ← 允许: 纯算法（SMA计算、信号检测）
strategies/gateways/vnpy_gateway.py  ← 允许: vn.py 适配
strategies/gateways/tqsdk_gateway.py ← 允许: 天勤适配
```

新增网关时必须：继承核心策略 → 转换数据格式 → 委托调用核心方法。

### 规则 4.2: 命名约定

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件名 | `snake_case` | `data_loader.py`, `config_manager.py` |
| 类名 | `PascalCase` | `VnpyBacktestEngine`, `MaStrategyCore` |
| 函数/方法 | `snake_case` | `run_full_pipeline`, `load_csv_data` |
| 私有方法 | `_` 前缀 | `_run_single_backtest`, `_calc_max_drawdown` |
| 常量 | `UPPER_SNAKE_CASE` | `HAS_VNPY`, `Qlib_COLUMNS` |

### 规则 4.3: 代码风格

- **禁止**添加注释，除非用户明确要求
- 缩进：4 空格
- 文档字符串：保持现有风格一致（中文或英文按上下文）
- 导入顺序：标准库 → 第三方库 → 项目内部模块
- 类型注解：所有公开方法必须标注参数和返回值类型

### 规则 4.4: 配置管理

- API 密钥、密码等敏感信息**必须**写入 `conf.local.yaml`，严禁写入 `conf.yaml`
- `conf.local.yaml` 已通过 `.gitignore` 排除，严禁手动 `git add`
- 新增配置参数应提供默认值，遵循 `.get(key, default)` 模式

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
| 禁止模式 | 禁止 `import traceback; traceback.print_exc()` 混入业务逻辑 |
| 异常处理 | 在所有 try/except 中记录堆栈：`logger.error("msg", exc_info=True)` |

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
| `plan.md` | 问题修复完成、里程碑达成、新问题发现 |

---

## 十、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0.0 | 2026-05-24 | 全面重写：新增项目结构、CLI 命令、编码规范、回测流水线约束、错误处理、Git 工作流、测试要求、文档规范 |
| 1.0.0 | 2026-05-23 | 初始版本：Python 环境激活规则 |