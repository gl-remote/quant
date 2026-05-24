# 贡献指南

> 版本: 0.2.0 | 更新日期: 2026-05-24

欢迎为天勤量化交易系统贡献代码。请先阅读本文，了解代码规范和提交流程。

---

## 开发环境

```bash
# 克隆仓库
git clone <repo-url>
cd quant

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

# 安装依赖
pip install -e ".[dev]"

# 验证环境
pytest tests/ -q
```

---

## 项目结构

```
quant/
├── main.py                    # CLI 入口
├── strategies/
│   ├── core/                  # 策略抽象层 (ABC + 类型定义)
│   │   ├── base.py            #   Strategy 基类
│   │   ├── context.py         #   TradingContext
│   │   └── types.py           #   Bar/Signal/Fill/Position/Performance
│   ├── bridges/               # 框架桥接器
│   │   ├── vnpy_bridge.py     #   vn.py CtaTemplate
│   │   └── tqsdk_bridge.py    #   天勤 SDK
│   └── ma_strategy.py         # 均线策略核心
├── backtest/                  # 回测子系统
│   ├── vnpy_backtest_engine.py
│   ├── tq_backtest_engine.py
│   ├── data_loader.py
│   ├── report.py
│   ├── comparison.py
│   ├── aggregator.py
│   ├── metrics.py
│   └── types.py
├── data/                      # 数据子系统
│   ├── exporter.py
│   └── database.py
├── config/                    # 配置管理
├── tests/                     # 测试
├── doc/                       # 文档
├── pyproject.toml             # 项目配置 (含 lint/test 工具)
└── plan.md                    # 项目改进计划
```

---

## 代码规范

### Python 风格

项目使用 `flake8` + `pylint` + `mypy` 进行代码质量检查，配置统一在 `pyproject.toml` 中：

```bash
# 运行全部检查
flake8 .
pylint strategies/ backtest/ data/
mypy strategies/ backtest/ data/
```

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `data_loader.py` |
| 类 | `PascalCase` | `MaStrategyCore` |
| 函数/方法 | `snake_case` | `on_bar()` |
| 私有方法 | `_leading_underscore` | `_calc_sma()` |
| 常量 | `UPPER_SNAKE` | `MAX_RETRIES` |
| 类型变量 | `PascalCase` | `TradingConfig` |

### 架构原则

1. **核心-桥接器分离**: 策略核心不依赖任何外部框架
2. **显式优于隐式**: 信号优先级、数据流方向必须有文档或注释说明
3. **防御性编程**: 外部输入必须校验（价格 > 0、手数 >= 1 等）
4. **不可变性优先**: 对外暴露的属性返回副本而非引用（如 `fills`）

---

## 开发流程

### 分支策略

```
main        ← 稳定版本
  ├── dev/0.2    ← 开发主线
  ├── feature/*  ← 新功能分支
  └── fix/*      ← Bug 修复分支
```

### 1. 创建功能分支

```bash
git checkout -b feature/my-feature dev/0.2
```

### 2. 编写代码 + 测试

- 新功能必须有对应测试
- 核心逻辑的测试覆盖率要求 ≥ 80%
- 运行现有测试确保不破坏：

```bash
pytest tests/ -v
```

### 3. 代码检查

```bash
flake8 .
mypy strategies/ backtest/ data/
```

### 4. 提交

```bash
git add .
git commit -m "feat: 添加 RSI 策略核心

- 新增 strategies/core/rsi_strategy.py
- 包含超买超卖信号和动态仓位管理
- 新增 15 个测试用例"
```

### 提交信息格式

采用 [Angular Convention](https://www.conventionalcommits.org/)：

```
<type>: <简短描述>

[详细说明]
```

| type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `refactor` | 重构（无功能变化） |
| `test` | 测试相关 |
| `chore` | 构建/工具链 |

### 5. 发起 Pull Request

- 描述变更内容和原因
- 关联相关 Issue
- 确保 CI 通过

---

## 测试

### 运行测试

```bash
# 全部测试
pytest tests/ -v

# 指定模块
pytest tests/test_backtest.py -v

# 带覆盖率
pytest tests/ --cov=. --cov-report=term-missing
```

### 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── test_ma_strategy.py      # 策略核心测试
├── test_vnpy_bridge.py      # vn.py 桥接器测试
├── test_tqsdk_bridge.py     # 天勤桥接器测试
├── test_export.py           # 数据导出测试
├── test_backtest.py         # 回测引擎测试
└── test_aggregator.py       # 指标计算测试
```

### 编写测试的原则

- 测试策略信号用模拟 Bar 序列
- Mock 外部 API 调用（天勤、vn.py）
- 每个测试函数只测一个场景
- 使用参数化测试覆盖边界情况

---

## 回测注意事项

- **参数命名**: 回测参数通过 `config/conf.yaml` 管理，不在代码中硬编码
- **手续费和滑点**: 双向扣除，`commission_rate * 2` + `slippage * 2 * volume`
- **profit_factor**: 使用行业标准公式 `gross_profit / abs(gross_loss)`
- **equity curve**: 优先使用 vnpy 的 `balance` 字段（含手续费/滑点），回退 `net_pnl`
- **过拟合检测**: Walk-Forward 验证必需，关注 IS-OOS 差距

---

## 联系方式

- Issue: [GitHub Issues](<repo-url>/issues)
- 文档: 参见 `doc/` 目录
