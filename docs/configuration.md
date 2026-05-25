# 参数配置说明

> 版本: 0.2.0-dev | 更新日期: 2026-05-25

---

## 配置文件体系

系统使用 YAML 分层配置，通过深度合并实现基础配置与本地覆盖的分离：

| 文件 | 用途 | 版本控制 |
|------|------|---------|
| `config/conf.yaml` | 基础配置，含策略参数、风控、回测设置 | 提交 |
| `config/conf.example.yaml` | 配置模板，供新用户参考 | 提交 |
| `config/conf.local.yaml` | 本地密钥与个性化覆盖 | **不提交** |

合并策略为递归深度合并：`conf.local.yaml` 中的键值会覆盖 `conf.yaml` 中同路径的值，嵌套字典逐层合并。`ConfigManager` 在初始化时自动完成此过程。

## 配置域概览

```
conf.yaml
├── app                 # 应用元信息
├── environment         # 运行环境标识
├── strategy_params     # 均线策略参数
├── risk                # 风险管理参数
├── data                # 数据源与存储路径
├── export              # 数据导出模板
├── backtest            # 回测引擎完整配置 ★
│   ├── （基础交易参数）
│   ├── split           # 数据集划分
│   └── report          # 报告输出
├── third_party         # 第三方服务密钥
└── system              # 系统日志配置
```

## 回测配置 `backtest`

回测的所有行为由此段控制，也是配置中最核心的部分。

### 基础交易参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data_dir` | string | `.quant_shared_data/csv` | CSV 历史数据目录 |
| `initial_capital` | float | `100000.0` | 回测初始资金 |
| `commission_rate` | float | `0.0003` | 单边手续费率（万分之三），双向收取 |
| `slippage` | float | `1` | 滑点（最小价格变动单位，跳） |
| `price_tick` | float | `1` | 合约最小价格变动 |
| `contract_size` | int | `10` | 合约乘数（每手对应多少单位标的） |
| `interval` | string | `"1m"` | K 线周期：`1m`/`5m`/`15m`/`30m`/`1h`/`d` |

### 数据集划分 `split`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `train_ratio` | float | `0.6` | 训练集比例，用于策略参数优化 |
| `val_ratio` | float | `0.2` | 验证集比例，用于策略选择与超参调优 |
| `test_ratio` | float | `0.2` | 测试集比例，用于最终性能评估（仅使用一次） |
| `random_seed` | int | `42` | 随机种子，保证划分可复现 |
| `shuffle` | bool | `true` | `true`=随机采样，`false`=时间顺序划分 |

> **重要**：三比例之和必须等于 1.0。对时间序列金融数据，强烈建议使用 `shuffle: false`，否则可能引入前视偏差导致回测结果过于乐观。

### 报告输出 `report`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_dir` | string | `.quant_shared_data/reports` | 报告文件输出目录 |
| `save_trade_records` | bool | `true` | 是否保存逐笔交易 JSON |
| `save_equity_curve` | bool | `true` | 是否保存每日资金曲线 JSON |
| `format` | string | `"json"` | 报告格式（当前仅 JSON） |

## 策略参数

### 均线参数 `strategy_params`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sma_short` | int | `5` | 短期均线周期，金叉条件为短线上穿长线 |
| `sma_long` | int | `20` | 长期均线周期，需大于 `sma_short` |

### 风控参数 `risk`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | `true` | 是否启用风控 |
| `stop_loss_ratio` | float | `0.03` | 止损比例（3%），持仓亏损达此比例平仓 |
| `take_profit_ratio` | float | `0.05` | 止盈比例（5%），持仓盈利达此比例平仓 |
| `position_ratio` | float | `0.1` | 仓位比例，单次开仓占总资金的 10% |

## 数据与导出配置

### 数据存储 `data`

| 参数 | 类型 | 说明 |
|------|------|------|
| `base_dir` | string | 共享数据根目录 |
| `export_dir` | string | CSV 导出目录 |
| `db_path` | string | SQLite 数据库路径 |

### 导出模板 `export`

| 参数 | 类型 | 说明 |
|------|------|------|
| `default_dir` | string | 默认导出目录 |
| `filename_template` | string | 文件命名模板，`{symbol}` 替换为品种代码 |

## 第三方服务 `third_party`

用于配置外部数据源和交易接口的认证信息。当前支持天勤量化 (tqsdk)：

```yaml
third_party:
  services:
    - name: "tqsdk"
      provider: "tianqin"
      api_key: "your_api_key"        # 天勤账号
      api_secret: "your_api_secret"  # 天勤密码
      enabled: true
```

> 密钥信息应写入 `config/conf.local.yaml`，`config/conf.yaml` 中仅保留占位符。

## 配置示例

### 期货日线回测（保守型）

```yaml
backtest:
  initial_capital: 500000.0
  commission_rate: 0.0001
  slippage: 1
  price_tick: 0.5
  contract_size: 100
  interval: "d"
  split:
    train_ratio: 0.7
    val_ratio: 0.15
    test_ratio: 0.15
    shuffle: false
  report:
    output_dir: "./output/reports"
```

### 分钟线高频回测

```yaml
backtest:
  initial_capital: 200000.0
  commission_rate: 0.0002
  slippage: 0
  interval: "5m"
  split:
    shuffle: true
```

## 配置验证

系统启动时自动验证：
- 数据集划分比例之和必须为 1.0
- 止损/止盈/仓位比例必须在 (0, 1] 区间
- 短期均线周期必须小于长期均线周期
- 数据量至少需要满足均线计算的最小 K 线条数