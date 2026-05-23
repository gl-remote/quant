# 天勤量化交易系统

基于天勤量化API的均线交叉策略交易系统。

## 项目简介

本项目实现了一个基于简单移动平均线（SMA）交叉的交易策略，支持：
- ✅ 自动化技术指标计算（SMA5、SMA20）
- ✅ 金叉买入、死叉卖出交易逻辑
- ✅ 风险控制（止损、止盈、仓位管理）
- ✅ 回测框架和绩效评估
- ✅ 完整的日志记录和交易记录

## 项目结构

```
quant/
├── config/                     # 配置管理模块
│   ├── __init__.py
│   └── config_manager.py       # 配置加载和验证
├── strategies/                 # 交易策略模块
│   ├── __init__.py
│   └── moving_average_strategy.py  # 均线交叉策略
├── data/                       # 数据处理模块
│   └── __init__.py
├── backtest/                  # 回测模块
│   ├── __init__.py
│   └── backtest_engine.py      # 回测引擎
├── main.py                    # 主程序入口
├── config.yaml                # 配置文件
├── requirements.txt           # Python依赖
├── activate_env.sh            # 环境激活脚本
└── README.md                  # 项目说明文档
```

## 环境配置

### 系统要求

- Python 3.11+
- Conda (推荐) 或 Python venv
- macOS / Linux / Windows

### Conda环境安装

项目使用Conda管理环境，提供了便捷的启动脚本：

```bash
# 1. 激活conda环境
./activate_env.sh

# 或手动激活
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading
```

### 依赖安装

Conda环境已包含所有必需依赖：

```bash
# 核心依赖（已安装）
- tqsdk>=3.0.0          # 天勤量化API
- pyyaml>=6.0          # YAML配置解析
- numpy>=1.21.0       # 数据处理
- python-dateutil>=2.8.0  # 日期时间处理
- matplotlib>=3.5.0    # 数据可视化
- pandas>=1.1.0       # 数据分析
- scipy>=1.5.0        # 科学计算

# 可选依赖（用于开发）
- pytest>=7.0.0       # 单元测试
- flake8>=5.0.0       # 代码检查
- pylint>=2.15.0      # 代码质量
```

### 手动重建环境

如果需要重建Conda环境：

```bash
# 创建新环境
conda create -n quant_trading python=3.11 -y

# 激活环境
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading

# 安装基础依赖
conda install pyyaml numpy python-dateutil matplotlib -y

# 安装天勤量化API
pip install tqsdk
```

## 快速开始

### 1. 配置账号信息

编辑 `config.yaml` 文件，填入天勤量化账号信息：

```yaml
# 天勤量化交易系统配置文件
# 请勿将此文件提交至版本控制系统，建议设置文件权限为600

tq_account:
  # 天勤量化平台API密钥标识
  # 格式要求：字符串类型，从天勤量化平台获取
  api_key: 'your_api_key'

  # 天勤量化平台API密钥
  # 安全建议：建议使用环境变量或加密存储方式
  api_secret: 'your_api_secret'
```

**⚠️ 安全提示：**
- 请勿将 `config.yaml` 提交到版本控制系统
- 建议设置文件权限：`chmod 600 config.yaml`
- 生产环境建议使用环境变量存储敏感信息

### 2. 测试策略逻辑

在测试模式下验证策略功能：

```bash
# 激活conda环境
source /usr/local/Caskroom/miniconda/base/bin/activate quant_trading

# 运行测试
python main.py --mode test
```

预期输出：
```
============================================================
测试模式 - 策略逻辑验证
============================================================
策略参数: SMA(5, 20)
风险控制: 止损=3.00%, 止盈=5.00%
仓位控制: 10.00%
测试: 模拟金叉买入
交叉检测: golden_cross
✓ 金叉信号正确识别
============================================================
测试模式完成 - 所有功能正常
============================================================
```

### 3. 运行回测

使用历史数据测试策略表现：

```bash
# 基本回测
python main.py --mode backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31

# 指定初始资金
python main.py --mode backtest --symbol DCE.m2109 --capital 100000
```

### 4. 实盘交易

```bash
# 运行实盘交易
python main.py --mode live --symbol DCE.m2109

# 使用指定配置文件
python main.py --mode live --symbol DCE.m2109 --config /path/to/config.yaml
```

## 策略参数

### 默认配置

策略支持通过 `config.yaml` 自定义参数：

```yaml
trading:
  # 均线周期参数
  sma_short: 5           # 短期均线周期
  sma_long: 20           # 长期均线周期
  
  # 风险控制参数
  stop_loss_ratio: 0.03   # 止损比例（3%）
  take_profit_ratio: 0.05 # 止盈比例（5%）
  position_ratio: 0.1     # 仓位比例（10%）
```

### 参数调整建议

- **SMA周期**：可根据交易品种调整，一般短线交易使用(5,20)，长线使用(10,60)
- **止损比例**：建议设置在2%-5%之间
- **止盈比例**：建议为止损的1.5-2倍
- **仓位比例**：建议不超过账户的10%-20%

## 交易逻辑

### 买入条件（金叉）

当满足以下所有条件时，系统执行买入：
1. SMA5从下向上穿越SMA20
2. 当前无持仓
3. 买入数量根据仓位比例计算

### 卖出条件（死叉）

当满足以下任一条件时，系统执行卖出：
1. SMA5从上向下穿越SMA20（死叉）
2. 当前亏损达到止损比例
3. 当前盈利达到止盈比例

### 风险控制

1. **固定止损**：亏损达到3%时自动平仓
2. **固定止盈**：盈利达到5%时自动平仓
3. **仓位控制**：每次交易使用账户可用资金的10%
4. **交易记录**：记录所有交易的时间、价格、盈亏

## 绩效指标

系统提供以下绩效评估指标：

- **胜率**：盈利交易数 / 总交易数
- **盈亏比**：平均盈利 / 平均亏损
- **最大回撤**：历史最大亏损比例
- **总盈亏**：所有交易的累计盈亏

## 命令行参数

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 运行模式：live/backtest/test | test |
| `--symbol` | 交易品种代码 | DCE.m2109 |
| `--config` | 配置文件路径 | config.yaml |

### 回测参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start` | 回测开始日期 | 2024-01-01 |
| `--end` | 回测结束日期 | 2024-12-31 |
| `--capital` | 初始资金 | 100000.0 |

### 使用示例

```bash
# 测试模式
python main.py --mode test

# 完整回测（2024年全年）
python main.py --mode backtest \
  --symbol DCE.m2109 \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000

# 实盘交易
python main.py --mode live --symbol DCE.m2109

# 自定义配置文件
python main.py --mode live --config /path/to/custom_config.yaml
```

## 常见问题

### 1. Conda环境激活失败

```bash
# 检查conda安装
which conda

# 如果未找到，执行conda初始化
conda init
source ~/.zshrc  # 或 source ~/.bashrc
```

### 2. 依赖安装失败

```bash
# 更新conda
conda update conda

# 清理缓存
conda clean --all

# 重新安装
pip install --no-cache-dir tqsdk
```

### 3. API连接问题

- 检查网络连接
- 确认API密钥有效
- 查看天勤量化服务状态

### 4. 策略运行异常

- 检查配置文件格式
- 查看日志输出
- 确认数据源可用

## 开发指南

### 代码规范

项目遵循PEP 8编码规范：

```bash
# 代码检查
flake8 strategies/*.py config/*.py backtest/*.py main.py

# 自动格式化
black strategies/*.py config/*.py backtest/*.py main.py
```

### 测试

```bash
# 运行单元测试
pytest tests/

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

## 版本历史

### v1.0.0 (2026-05-23)
- 初始版本发布
- 实现均线交叉策略
- 支持回测和实盘交易
- 风险控制机制

## 注意事项

### ⚠️ 重要提示

1. **实盘风险**：量化交易存在风险，实盘交易可能导致资金损失
2. **充分测试**：实盘前务必在回测和模拟交易中充分验证策略
3. **资金管理**：合理控制仓位，避免过度交易
4. **持续监控**：实盘运行时应持续监控策略表现

### 📋 使用建议

1. 先使用测试模式验证功能
2. 使用回测评估策略表现
3. 小资金实盘验证
4. 逐步增加仓位

## 联系方式

如有问题或建议，请通过以下方式联系：
- GitHub Issues: [项目仓库地址]
- 邮箱: [联系邮箱]

## 许可证

本项目仅供学习和研究使用，实盘交易风险自负。

---

**最后更新：2026-05-23**
