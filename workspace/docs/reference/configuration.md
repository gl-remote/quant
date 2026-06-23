# 配置指南

> 版本: 0.2.0-dev | 更新日期: 2026-05-27

---

## 配置文件结构

```
config/
├── conf.toml          # 基础配置（提交版本控制）
└── conf.local.toml    # 本地覆盖（不提交，包含敏感信息）
```

---

## 配置层级

| 层级 | 文件 | 优先级 | 是否提交 |
|------|------|--------|----------|
| 基础 | `conf.toml` | 低 | ✅ |
| 本地 | `conf.local.toml` | 中 | ❌ |
| 环境变量 | `TQSDK_API_KEY` 等 | 高 | - |

---

## 配置示例

### 主配置文件 (`conf.toml`)

```toml
[app]
name = "策略工具箱"
version = "0.2.0-dev"
log_level = "INFO"

[backtest]
initial_capital = 100000.0
commission_rate = 0.0003
slippage = 0.1

[backtest.split]
train_ratio = 0.6
val_ratio = 0.2
test_ratio = 0.2

[data]
data_dir = ".quant_shared_data"
csv_dir = "csv"
db_file = "quant_shared.db"

[optimizer]
enabled = true
engine = "bayesian"
n_trials = 50

[optimizer.search_space]
sma_short = { type = "int", low = 5, high = 30, step = 5 }
sma_long = { type = "int", low = 30, high = 200, step = 10 }

[strategies]
enabled = ["ma"]

[[strategies.items]]
name = "ma"
enabled = true
sma_short = 5
sma_long = 60
stop_loss_ratio = 0.02
take_profit_ratio = 0.05
position_ratio = 0.5

[third_party]
[[third_party.services]]
name = "tqsdk"
provider = "tqsdk"
enabled = false
```

### 本地配置文件 (`conf.local.toml`)

```toml
[third_party]
[[third_party.services]]
name = "tqsdk"
provider = "tqsdk"
api_key = "your_actual_api_key"
api_secret = "your_actual_api_secret"
enabled = true
```

---

## 配置项说明

### [backtest]

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `initial_capital` | float | 100000.0 | 初始资金 |
| `commission_rate` | float | 0.0003 | 手续费率（如 0.0003 = 万三） |
| `slippage` | float | 0.1 | 单边滑点（价格单位，如 0.1 元/跳） |
| `interval` | str | "1m" | K线周期: 1m/5m/15m/30m/1h/d |
| `price_tick` | float | 1.0 | 最小变动价位 |
| `contract_size` | int | 10 | 合约乘数 |

### [optimizer]

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | true | 是否启用优化 |
| `engine` | str | "bayesian" | 优化引擎：grid/bayesian |
| `n_trials` | int | 50 | 试验次数 |

### [strategies.items]

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `name` | str | - | 策略名称 |
| `enabled` | bool | true | 是否启用 |
| `sma_short` | int | 5 | 短期均线周期 |
| `sma_long` | int | 60 | 长期均线周期 |
| `stop_loss_ratio` | float | 0.02 | 止损比例 |
| `take_profit_ratio` | float | 0.05 | 止盈比例 |

---

## 配置加载流程

1. 读取 `conf.toml`
2. 读取 `conf.local.toml`（覆盖）
3. 解析环境变量（最高优先级）
4. Pydantic 模型校验

---

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `TQSDK_API_KEY` | 天勤 API Key |
| `TQSDK_API_SECRET` | 天勤 API Secret |
| `QUANT_DATA_DIR` | 数据目录路径 |