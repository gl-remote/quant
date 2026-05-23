# 天勤量化交易系统

基于天勤量化API的均线交叉策略交易系统。

## 项目简介

本项目实现了一个基于简单移动平均线（SMA）交叉的交易策略，支持：

- 自动化技术指标计算（SMA5、SMA20）
- 金叉买入、死叉卖出交易逻辑
- 风险控制（止损、止盈、仓位管理）
- 回测框架和绩效评估（胜率、最大回撤、夏普比率）
- 天勤图形界面支持（K线图、资金曲线可视化）
- 完整的日志记录和交易记录

## 项目结构

```
quant/
├── conf.yaml                 # 通用配置（提交git）
├── conf.local.yaml          # 本地覆盖配置（不提交git）
├── conf.example.yaml        # 配置模板
├── config/                  # 配置管理模块
│   ├── __init__.py
│   └── config_manager.py
├── strategies/              # 交易策略模块
│   ├── __init__.py
│   └── moving_average_strategy.py
├── backtest/               # 回测模块
│   ├── __init__.py
│   └── backtest_engine.py
├── data/                   # 数据处理模块
│   └── __init__.py
├── main.py                 # 主程序入口
├── run.sh                  # 快捷运行脚本
├── activate_env.sh         # 环境激活脚本
├── requirements.txt        # Python依赖
└── README.md              # 项目说明文档
```

## 快速开始

### 1. 激活环境

```bash
./activate_env.sh
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置天勤账号

复制配置模板并填入账号信息：

```bash
cp conf.example.yaml conf.local.yaml
```

编辑 `conf.local.yaml`，填入天勤账号信息：

```yaml
third_party:
  services:
    - name: "tqsdk"
      api_key: "your_tq_api_key"
      api_secret: "your_tq_api_secret"
```

### 4. 测试策略

```bash
python main.py --mode test
```

### 5. 运行回测

```bash
python main.py --mode backtest --symbol DCE.m2509 --start 2025-06-01 --end 2025-08-31
```

### 6. 运行回测并显示图形界面

```bash
python main.py --mode backtest --symbol DCE.m2509 --start 2025-06-01 --end 2025-08-31 --gui
```

### 7. 实盘交易

```bash
python main.py --mode live --symbol DCE.m2509
```

### 8. 实盘交易并显示图形界面

```bash
python main.py --mode live --symbol DCE.m2509 --gui
```

> 也可以使用 `./run.sh` 替代 `python main.py`，它会自动使用项目配置的 Python 解释器路径。

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 运行模式：`live`（实盘）、`backtest`（回测）、`test`（测试） | `test` |
| `--symbol` | 交易品种代码 | `DCE.m2109` |
| `--config` | 配置文件路径 | 无 |
| `--start` | 回测开始日期（格式：YYYY-MM-DD） | `2024-01-01` |
| `--end` | 回测结束日期（格式：YYYY-MM-DD） | `2024-12-31` |
| `--capital` | 初始资金 | `100000.0` |
| `--gui` | 启用天勤图形界面（回测和实盘模式） | 禁用 |

## 图形界面功能

启用 `--gui` 参数后，系统将通过天勤量化 Web GUI 启动图形界面：

- **K线图**：显示实时/历史K线数据
- **技术指标**：SMA5、SMA20均线叠加显示
- **交易信号标记**：买入/卖出信号在K线图上标记
- **资金曲线**：展示账户权益变化
- **实时监控**：实盘模式下实时更新数据

## 配置文件

### 配置文件说明

| 文件 | 用途 | 是否提交Git |
|------|------|------------|
| `conf.yaml` | 通用配置，包含策略参数、风控配置等 | 是 |
| `conf.local.yaml` | 本地覆盖配置，包含API密钥等敏感信息 | 否 |
| `conf.example.yaml` | 配置模板，供新用户参考 | 是 |

配置文件使用深度合并策略：先加载 `conf.yaml`，再用 `conf.local.yaml` 中的内容覆盖相同键的值。

### conf.yaml - 通用配置

```yaml
# 交易策略参数
strategy_params:
  sma_short: 5              # 短期均线周期
  sma_long: 20              # 长期均线周期

# 风险管理配置
risk:
  stop_loss_ratio: 0.03     # 止损比例 (3%)
  take_profit_ratio: 0.05   # 止盈比例 (5%)
  position_ratio: 0.1       # 单次仓位比例 (10%)

# 系统配置
system:
  logging:
    level: "INFO"           # 日志级别
```

### conf.local.yaml - 本地配置

```yaml
# 天勤API密钥
third_party:
  services:
    - name: "tqsdk"
      api_key: "your_tq_api_key"      # 天勤账号
      api_secret: "your_tq_api_secret" # 天勤密码

# 本地环境配置
environment:
  name: "local"
  debug: true
```

## 回测报告

回测完成后输出详细的绩效报告：

```
============================================================
回测报告
============================================================
初始资金: 100,000.00
最终资金: 105,230.00
总收益率: 5.23%

交易统计:
  总交易次数: 12
  盈利交易: 8
  亏损交易: 4
  胜率: 66.67%

盈亏统计:
  总盈亏: 5,230.00
  平均盈利: 850.00
  平均亏损: -320.00
  盈亏比: 2.66
  最大回撤: 2.34%
  夏普比率: 1.85
============================================================
```

## 注意事项

### 本地环境配置

本项目保存了本地配置，注意以下路径问题：

1. **Conda 环境路径**: `/usr/local/Caskroom/miniconda/base/envs/quant_trading`
   - 如果conda安装位置不同，需要修改 `activate_env.sh`、`run.sh` 和 `.vscode/settings.json`

2. **Python 解释器路径**: 见 `.vscode/settings.json`
   - 在新机器上需要更新为实际Python路径

3. **Pip 镜像源**: `.pip/pip.conf`
   - 配置了清华镜像源，如需更换可修改此文件

4. **API 密钥**: `conf.local.yaml`
   - 包含个人天勤量化API密钥
   - 已配置 `.gitignore`，不提交到版本控制

### 图形界面注意事项

1. **显示环境**: 需要支持图形界面的操作系统（Linux需安装图形环境）
2. **依赖安装**: 确保已正确安装 `tqsdk` 和相关图形依赖
3. **网络连接**: 图形界面需要持续连接天勤服务器

### 重要提示

1. **实盘风险**：量化交易存在风险，实盘交易可能导致资金损失
2. **充分测试**：实盘前务必在回测和模拟交易中充分验证策略
3. **资金管理**：合理控制仓位，避免过度交易
4. **持续监控**：实盘运行时应持续监控策略表现

## 版本历史

### v1.1.0 (2026-05-23)
- 添加天勤图形界面支持
- 通过 `--gui` 参数启用图形界面
- 支持回测和实盘模式的可视化
- 更新项目文档

### v1.0.0 (2026-05-23)
- 初始版本发布
- 实现均线交叉策略
- 支持回测和实盘交易
- 风险控制机制

---

**最后更新：2026-05-23**