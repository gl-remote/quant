# 参数配置说明

> 版本: 1.0.0 | 更新日期: 2026-05-23

---

## 1. 配置文件概述

回测系统的所有参数通过 `conf.yaml` 中的 `backtest` 段统一管理，支持分层覆盖 (`conf.local.yaml`)。

配置文件位置：
- `conf.yaml` — 基础配置，提交至版本控制
- `conf.local.yaml` — 本地覆盖，不提交版本控制

## 2. 完整配置参数

```yaml
# ============================================================
# vn.py 回测配置
# ============================================================
backtest:
  # ──── 基础交易参数 ────
  data_dir: ".quant_shared_data/csv"   # CSV 数据目录
  initial_capital: 100000.0            # 初始资金
  commission_rate: 0.0003              # 手续费率 (0.03%)
  slippage: 1                          # 滑点 (跳)
  price_tick: 1                        # 最小价格变动
  contract_size: 10                    # 合约乘数
  interval: "1m"                       # K线周期

  # ──── 数据集划分 ────
  split:
    train_ratio: 0.6                   # 训练集比例
    val_ratio: 0.2                     # 验证集比例
    test_ratio: 0.2                    # 测试集比例
    random_seed: 42                    # 随机种子
    shuffle: true                      # 随机打乱 / 时间顺序划分

  # ──── 报告输出 ────
  report:
    output_dir: ".quant_shared_data/reports"  # 报告输出目录
    save_trade_records: true                  # 保存交易记录
    save_equity_curve: true                   # 保存资金曲线
    format: "json"                            # 报告格式
```

## 3. 参数详解

### 3.1 基础交易参数

#### data_dir

- **类型**: `string`
- **默认值**: `".quant_shared_data/csv"`
- **说明**: CSV 历史数据的存放目录。支持相对路径和绝对路径。

#### initial_capital

- **类型**: `float`
- **默认值**: `100000.0`
- **说明**: 回测初始资金。所有收益率、资金曲线等指标均以此为基准计算。

#### commission_rate

- **类型**: `float`
- **默认值**: `0.0003`
- **说明**: 单边手续费率。`0.0003` 表示 0.03% (万分之三)。双向收取。

#### slippage

- **类型**: `float`
- **默认值**: `1`
- **说明**: 滑点设置，单位为最小价格变动单位 (跳)。每笔交易在实际价格基础上额外扣除 `slippage × price_tick`。

#### price_tick

- **类型**: `float`
- **默认值**: `1`
- **说明**: 合约最小价格变动单位。不同品种不同：螺纹钢为 1，铁矿石为 0.5，股指期货为 0.2。

#### contract_size

- **类型**: `int`
- **默认值**: `10`
- **说明**: 合约乘数。用于计算开仓手数。国内商品期货通常为 10。

#### interval

- **类型**: `string`
- **默认值**: `"1m"`
- **说明**: K线周期，控制回测时使用的行情数据粒度。

| 值 | 含义 |
|----|------|
| `1m` | 1分钟线 |
| `5m` | 5分钟线 |
| `15m` | 15分钟线 |
| `30m` | 30分钟线 |
| `1h` | 1小时线 |
| `d` | 日线 |

### 3.2 数据集划分参数

#### train_ratio / val_ratio / test_ratio

- **类型**: `float`
- **默认值**: `0.6` / `0.2` / `0.2`
- **约束**: 三者之和必须等于 `1.0`
- **说明**: 控制数据集划分比例。机器学习领域经典的 60-20-20 划分。

**划分策略说明:**

| 数据集 | 用途 | 注意事项 |
|--------|------|---------|
| 训练集 | 策略参数优化/拟合 | 可多次使用，允许调参 |
| 验证集 | 策略选择/超参调整 | 可多次使用但不应过度调整 |
| 测试集 | 最终性能评估 | 只能使用一次，严禁用于调参 |

#### random_seed

- **类型**: `int`
- **默认值**: `42`
- **说明**: 随机种子，保证数据划分的可复现性。同一随机种子和同一数据集产生完全相同的划分。

#### shuffle

- **类型**: `bool`
- **默认值**: `false`
- **说明**: 数据划分模式。

| 值 | 模式 | 适用场景 |
|----|------|---------|
| `false` | 时间顺序划分 | 时间序列数据，避免未来信息泄露 (推荐) |
| `true` | 随机采样划分 | 跨品种/跨时段稳健性验证 |

> **警告**: 时间序列数据使用 `shuffle: true` 可能引入前视偏差 (look-ahead bias)，导致回测结果过于乐观，与实际交易表现偏差较大。仅在明确理解风险的前提下使用。

### 3.3 报告输出参数

#### output_dir

- **类型**: `string`
- **默认值**: `".quant_shared_data/reports"`
- **说明**: 报告文件输出目录，不存在时自动创建。

#### save_trade_records

- **类型**: `bool`
- **默认值**: `true`
- **说明**: 是否保存详细的逐笔交易记录到 JSON 文件。

#### save_equity_curve

- **类型**: `bool`
- **默认值**: `true`
- **说明**: 是否保存每日资金曲线数据到 JSON 文件。

#### format

- **类型**: `string`
- **默认值**: `"json"`
- **说明**: 报告文件格式。

| 值 | 说明 |
|----|------|
| `json` | JSON 格式，结构化，便于程序读取 (推荐) |
| `csv` | CSV 格式 (预留) |

## 4. 策略参数配置

策略参数通过 conf.yaml 中的 `risk` 和 `strategy_params` 段配置：

```yaml
# 均线策略参数
strategy_params:
  sma_short: 5              # 短期均线周期
  sma_long: 20              # 长期均线周期

# 风险管理配置
risk:
  enabled: true
  stop_loss_ratio: 0.03     # 止损比例 (3%)
  take_profit_ratio: 0.05   # 止盈比例 (5%)
  position_ratio: 0.1       # 仓位比例 (10%)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `sma_short` | `int` | 短期均线计算周期，金叉条件为短线上穿长线 |
| `sma_long` | `int` | 长期均线计算周期，需大于 `sma_short` |
| `stop_loss_ratio` | `float` | 止损比例，持仓亏损达此比例时平仓 |
| `take_profit_ratio` | `float` | 止盈比例，持仓盈利达此比例时平仓 |
| `position_ratio` | `float` | 单次开仓占总资金比例 |

## 5. 配置示例

### 期货日线回测

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
    random_seed: 123
    shuffle: false
  report:
    output_dir: "./output/reports"
    save_trade_records: true
    save_equity_curve: true
```

### 分钟线高频回测

```yaml
backtest:
  initial_capital: 200000.0
  commission_rate: 0.0002
  slippage: 0
  price_tick: 1
  contract_size: 10
  interval: "5m"
  split:
    train_ratio: 0.6
    val_ratio: 0.2
    test_ratio: 0.2
    shuffle: true
```

## 6. 配置验证

系统启动时会自动验证配置参数：

- `train_ratio + val_ratio + test_ratio` 必须等于 1.0
- 数据量至少需要 10 条记录
- 参数值在合理范围内 (如止损止盈比例 0~1)