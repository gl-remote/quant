# 使用指南

> 版本: 0.2.0-dev | 更新日期: 2026-05-27

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

| 指标 | 说明 |
|------|------|
| `total_return` | 总收益率 |
| `sharpe_ratio` | 夏普比率 |
| `max_drawdown` | 最大回撤 |
| `win_rate` | 胜率 |

---

## 最佳实践

1. 使用 Walk-Forward 验证策略稳健性
2. 避免过拟合，测试集表现不应显著差于训练集
3. 使用合理的止损比例控制风险
4. 定期更新数据确保回测质量