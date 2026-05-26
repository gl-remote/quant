# 配置说明

> 版本: 0.2.0-dev | 更新日期: 2026-05-26

---

## 配置文件结构

项目使用 TOML 格式的配置文件，支持分层配置和环境变量覆盖。

### 配置文件位置

| 文件 | 用途 | 是否提交版本控制 |
|------|------|----------------|
| `config/conf.toml` | 基础配置 | ✅ 是 |
| `config/conf.local.toml` | 本地覆盖（含密钥） | ❌ 否 |
| `config/conf.example.toml` | 配置模板 | ✅ 是 |

### 配置加载顺序

1. `conf.toml` → 基础配置
2. `conf.local.toml` → 本地覆盖（可选）
3. 环境变量 → 账户凭证优先

---

## 配置项详解

### 1. 应用配置

```toml
[app]
name = "天勤量化交易系统"
version = "0.2.0-dev"
mode = "test"  # test / backtest / live
```

### 2. 环境配置

```toml
[environment]
name = "development"  # development / production
debug = true
```

### 3. 回测配置

```toml
[backtest]
data_dir = ".quant_shared_data/csv"      # K线数据目录
initial_capital = 100000.0               # 初始资金
commission_rate = 0.0003                 # 手续费率 (0.03%)
slippage = 1                             # 滑点（最小变动价位）
price_tick = 1                           # 最小变动价位
contract_size = 10                        # 合约乘数
interval = "1m"                          # K线周期

[backtest.split]
train_ratio = 0.6    # 训练集比例
val_ratio = 0.2      # 验证集比例
test_ratio = 0.2     # 测试集比例
random_seed = 42     # 随机种子
shuffle = false      # 是否随机打乱（时间序列数据应设为false）
```

### 4. 策略配置

```toml
[[strategies]]
name = "ma"                    # 策略名称（唯一标识）
enabled = true                 # 是否启用

# MA 策略参数
sma_short = 5                  # 短期均线周期
sma_long = 60                  # 长期均线周期
stop_loss_ratio = 0.02         # 止损比例 (2%)
take_profit_ratio = 0.05       # 止盈比例 (5%)
position_ratio = 0.5           # 仓位比例 (50%)
kline_period = 60              # K线周期（秒）
```

### 5. 参数优化配置

```toml
[optimizer]
enabled = false                # 是否启用参数优化
engine = "grid"               # 优化引擎: grid / optuna
n_trials = 50                  # Optuna 最大试验次数

# 网格搜索参数（grid 引擎专用）
[optimizer.param_grid]
sma_short = [5, 10, 15]
sma_long = [30, 60, 120]

# Optuna 搜索空间（optuna 引擎专用）
[optimizer.search_space]
sma_short = { type = "int", low = 5, high = 30, step = 5 }
sma_long = { type = "int", low = 30, high = 200, step = 10 }
```

### 6. 数据配置

```toml
[data]
provider = "tqsdk"             # 数据源
cache_enabled = false          # 是否启用缓存
base_dir = ".quant_shared_data"
export_dir = ".quant_shared_data/csv"
db_path = ".quant_shared_data/quant_shared.db"
```

### 7. 导出配置

```toml
[export]
default_dir = ".quant_shared_data/csv"           # 默认导出目录
filename_template = "{symbol}.{interval}.csv"    # 文件名模板
```

### 8. 系统配置

```toml
[system]
modules = ["backtest", "optimizer"]

[system.logging]
level = "INFO"                    # 日志级别: DEBUG / INFO / WARNING / ERROR
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 9. 第三方服务配置

```toml
[[third_party.services]]
name = "tqsdk"
provider = "tqsdk"
api_key = "your_api_key_here"
api_secret = "your_api_secret_here"
enabled = true
```

---

## 环境变量

| 环境变量 | 用途 |
|----------|------|
| `TQSDK_API_KEY` | 天勤 API Key |
| `TQSDK_API_SECRET` | 天勤 API Secret |

环境变量优先级高于配置文件中的密钥配置。

---

## 配置验证

运行以下命令验证配置是否正确：

```bash
python -c "from config import ProjectConfig; cfg = ProjectConfig.instance(); print('配置验证通过')"
```

### 配置模型结构

```
ProjectConfig
├── app: AppConfig
│   ├── name: str
│   ├── version: str
│   └── mode: str
├── environment: EnvironmentConfig
│   ├── name: str
│   └── debug: bool
├── strategies: list[StrategyItemConfig]
│   └── [*]: StrategyItemConfig
│       ├── name: str
│       ├── enabled: bool
│       ├── sma_short: int
│       ├── sma_long: int
│       ├── stop_loss_ratio: float
│       ├── take_profit_ratio: float
│       ├── position_ratio: float
│       └── kline_period: int
├── backtest: BacktestConfig
│   ├── data_dir: str
│   ├── initial_capital: float
│   ├── commission_rate: float
│   ├── slippage: float
│   ├── price_tick: float
│   ├── contract_size: int
│   ├── interval: str
│   └── split: SplitConfig
│       ├── train_ratio: float
│       ├── val_ratio: float
│       ├── test_ratio: float
│       ├── random_seed: int
│       └── shuffle: bool
├── optimizer: OptimizerConfig
│   ├── enabled: bool
│   ├── engine: str
│   ├── n_trials: int
│   ├── param_grid: dict
│   └── search_space: dict
├── data: DataConfig
│   ├── provider: str
│   ├── cache_enabled: bool
│   ├── base_dir: str
│   ├── export_dir: str
│   └── db_path: str
├── export: ExportConfig
│   ├── default_dir: str
│   └── filename_template: str
├── system: SystemConfig
│   ├── modules: list[str]
│   └── logging: LoggingConfig
│       ├── level: str
│       └── format: str
├── third_party: ThirdPartyConfig
│   └── services: list[ThirdPartyServiceConfig]
└── account: AccountInfo (可选)
    ├── api_key: str
    └── api_secret: str
```

---

## 配置访问示例

```python
from config import ProjectConfig

# 获取单例配置
cfg = ProjectConfig.instance()

# 访问回测配置
print(f"初始资金: {cfg.backtest.initial_capital}")
print(f"手续费率: {cfg.backtest.commission_rate}")

# 访问策略配置
strategy_config = cfg.get_strategy_config("ma")
print(f"SMA短期: {strategy_config.sma_short}")
print(f"SMA长期: {strategy_config.sma_long}")

# 访问账户信息
account = cfg.get_account_info()
if account:
    print(f"API Key: {account.api_key}")

# 检查配置是否有效
if cfg.is_valid:
    print("配置验证通过")
```

---

## 配置最佳实践

### 1. 密钥管理

- **永远不要**将 API 密钥提交到版本控制
- 使用 `conf.local.toml` 存储敏感信息
- 或使用环境变量传递密钥

### 2. 配置继承

- `conf.toml` 存储公共配置（提交版本控制）
- `conf.local.toml` 存储本地覆盖（不提交）
- 本地配置会深度合并覆盖基础配置

### 3. 配置验证

所有配置项通过 Pydantic 模型进行验证：

| 验证规则 | 说明 |
|----------|------|
| `initial_capital` | 必须 > 0 |
| `commission_rate` | 必须在 [0, 1) 范围内 |
| `slippage` | 必须 >= 0 |
| `stop_loss_ratio` | 必须在 (0, 1] 范围内 |
| `sma_short` | 必须 > 0 |
| `train_ratio + val_ratio + test_ratio` | 必须 = 1.0 |

### 4. 多环境配置

可以创建不同环境的配置文件：

```bash
# 开发环境
cp config/conf.example.toml config/conf.local.toml

# 生产环境
cp config/conf.example.toml config/conf.prod.toml
# 修改配置后通过命令行指定
python main.py backtest --config config/conf.prod.toml
```
