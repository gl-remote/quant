# 使用指南

> 版本: 0.2.1-dev | 更新日期: 2026-06-06

---

## 快速入门

### 1. 安装依赖

```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .

# 前端依赖（报告模块）
cd report/web && npm install
```

### 2. 配置账户

```bash
cp config/conf.example.toml config/conf.local.toml
# 编辑 conf.local.toml 填入 API 密钥
```

### 3. 导出数据

```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31
```

### 4. 运行回测

```bash
python main.py backtest --symbol DCE.m2509 --strategy ma
```

### 5. 查看报告

```bash
open output/index.html
```

---

## 回测命令详解

### 单品种回测

```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --start 2024-01-01 --end 2024-12-31 --gui
```

### 批量回测

```bash
python main.py backtest --pattern "DCE\.m" --strategy ma
```

### 参数优化

```bash
# 网格搜索
python main.py backtest --symbol DCE.m2509 --optimizer grid --mode search

# 贝叶斯优化
python main.py backtest --symbol DCE.m2509 --optimizer bayesian --mode search
```

### Walk-Forward 验证

```bash
python main.py backtest --symbol DCE.m2509 --mode walk-forward
```

---

## 报告查看

### 查看回测列表

```bash
python main.py report
```

### 查看详细报告

```bash
open output/index.html
```

---

## 策略开发指南

### 创建新策略

1. 在 `strategies/` 目录创建新文件
2. 实现 `Strategy` 接口
3. 在配置文件中添加策略配置

---

## 关键指标解读

### 格式约定

| 字段类型 | 格式 | 示例 |
|----------|------|------|
| 收益率类 (`total_return`, `annual_return`) | 百分比（已乘 100） | `15.5` 表示 15.5% |
| 回撤金额 (`max_drawdown`) | 绝对金额（元） | `5200` 表示亏了 5200 元 |
| 回撤百分比 (`max_ddpercent`) | 百分比（已乘 100） | `12.5` 表示 12.5% |
| 胜率 (`win_rate`) | 比值 (0~1)，前端显示时 ×100 | 数据库存 `0.6` → 显示 "60.0%" |

### 核心绩效指标

| 指标 | 说明 | 来源 |
|------|------|------|
| `total_return` | 总收益率（%） | [vnpy] |
| `end_balance` | 最终权益余额 | [vnpy] |
| `sharpe_ratio` | 夏普比率 | [vnpy] |
| `max_drawdown` / `max_ddpercent` | 最大回撤（金额 / 百分比） | [vnpy] |
| `annual_return` | 年化收益率（%） | [vnpy] |
| `ewm_sharpe` | EWM 指数加权夏普比率 | [vnpy] |

### 盈亏汇总

| 指标 | 说明 | 来源 |
|------|------|------|
| `total_net_pnl` | 总净盈亏（扣完手续费和滑点后） | [vnpy] |
| `total_commission` | 总手续费 | [vnpy] |
| `total_slippage` | 总滑点成本 | [vnpy] |
| `total_turnover` | 总成交金额 | [vnpy] |

### 交易级别统计

| 指标 | 说明 | 统计口径 |
|------|------|----------|
| `win_rate` | 胜率 | 仅统计 pnl != 0 的平仓交易（排除开仓和持平） |
| `win_trades` / `loss_trades` | 盈利/亏损笔数 | 同上，pnl > 0 为盈利，pnl < 0 为亏损 |
| `avg_win` / `avg_loss` | 平均盈利/亏损金额 | 基于上述盈亏交易计算 |
| `win_loss_ratio` | 盈亏比 | avg_win / avg_loss |
| `max_consecutive_win/loss` | 最大连续盈利/亏损次数 | 基于平仓时间顺序 |

### 交易日统计

| 指标 | 说明 | 来源 |
|------|------|------|
| `profit_days` / `loss_days` | 盈利/亏损交易日数 | [vnpy] |

---

## 最佳实践

1. 使用 Walk-Forward 验证策略稳健性
2. 避免过拟合，测试集表现不应显著差于训练集
3. 使用合理的止损比例控制风险
4. 定期更新数据确保回测质量