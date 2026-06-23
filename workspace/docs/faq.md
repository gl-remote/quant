# 常见问题

> 版本: 0.2.0-dev | 更新日期: 2026-05-27

---

## 安装与配置

### Q: 如何安装依赖？

A: 

```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .
```

### Q: 如何配置天勤 API 密钥？

A: 复制配置模板并编辑：

```bash
cp config/conf.example.toml config/conf.local.toml
```

在 `conf.local.toml` 中填入：

```toml
[third_party]
[[third_party.services]]
name = "tqsdk"
provider = "tqsdk"
api_key = "your_api_key"
api_secret = "your_api_secret"
enabled = true
```

---

## 数据管理

### Q: 数据文件存储在哪里？

A: 默认存储在 `.quant_shared_data/csv/` 目录，文件格式为 `{symbol}.{interval}.csv`。

### Q: 如何导出新的 K 线数据？

A: 

```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31
```

### Q: 回测结果存储在哪里？

A: 存储在 SQLite 数据库 `.quant_shared_data/quant_shared.db` 中。

---

## 回测相关

### Q: 如何运行单品种回测？

A: 

```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --start 2024-01-01 --end 2024-12-31
```

### Q: 如何运行批量回测？

A: 

```bash
python main.py backtest --pattern "DCE\.m" --strategy ma
```

### Q: 如何启用参数优化？

A: 在配置文件中设置：

```toml
[optimizer]
enabled = true
engine = "bayesian"  # 或 "grid"
n_trials = 50
```

### Q: Walk-Forward 和普通回测有什么区别？

A: Walk-Forward 将数据划分为多个时间窗口，每个窗口在训练集训练、测试集验证，能更真实评估策略未来表现。

---

## 报告相关

### Q: 如何查看回测报告？

A: 回测完成后直接打开：

```bash
open output/index.html
```

### Q: 报告为什么无法加载？

A: 确保已安装前端依赖：

```bash
cd report/web && npm install
```

### Q: 报告支持离线查看吗？

A: 是的，报告使用数据预加载机制，支持 `file://` 协议直接打开。

---

## 策略开发

### Q: 如何添加新策略？

A: 

1. 在 `strategies/` 目录创建新文件
2. 实现 `Strategy` 接口
3. 在配置文件中添加策略配置

### Q: 策略核心代码需要关注哪些方法？

A: 主要关注：
- `on_bar()` - K 线处理
- `on_fill()` - 成交回调
- `reset()` - 状态重置

---

## 技术问题

### Q: 如何选择回测引擎？

A: 单品种带 GUI 使用 TqSdk，批量回测或参数优化使用 vn.py。系统会根据参数自动选择。

### Q: 支持哪些数据周期？

A: 支持分钟线、日线等多种周期，默认从配置读取。

### Q: 如何清除缓存？

A: 

```bash
rm -rf .quant_shared_data/csv/
rm -rf output/.kline_cache/
```

---

## 性能优化

### Q: 回测速度慢怎么办？

A: 

1. 使用 vn.py 批量回测（比 TqSdk 更快）
2. 减少参数搜索空间
3. 使用 K 线缓存机制（自动启用）

### Q: K 线数据缓存如何工作？

A: 首次构建时 CSV → JSON，后续构建直接使用缓存，基于文件 mtime 自动失效。

---

## 其他

### Q: 如何运行测试？

A: 

```bash
python main.py test --strategy ma
# 或
python -m pytest tests/ -v
```

### Q: 如何贡献代码？

A: 遵循项目代码规范，提交前确保测试通过。