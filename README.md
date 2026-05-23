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
├── conf.yaml                 # 通用配置（提交git）
├── conf.local.yaml          # 本地覆盖配置（不提交git）
├── conf.example.yaml        # 配置模板
├── config/                  # 配置管理模块
│   └── config_manager.py
├── strategies/              # 交易策略模块
│   └── moving_average_strategy.py
├── backtest/               # 回测模块
│   └── backtest_engine.py
├── data/                   # 数据处理模块
├── main.py                 # 主程序入口
├── requirements.txt         # Python依赖
├── activate_env.sh         # 环境激活脚本
└── README.md              # 项目说明文档
```

## 快速开始

### 1. 激活环境

```bash
./activate_env.sh
```

### 2. 测试策略

```bash
python main.py --mode test
```

### 3. 运行回测

```bash
python main.py --mode backtest --symbol DCE.m2109
```

### 4. 实盘交易

```bash
python main.py --mode live --symbol DCE.m2109
```

## 配置文件

### 配置文件结构

```
conf.yaml              # 通用配置，包含策略参数、风控配置等
conf.local.yaml       # 本地覆盖配置，包含API密钥等敏感信息
conf.example.yaml     # 配置模板
```

### 配置说明

**conf.yaml** - 通用配置
- 交易策略参数（SMA周期）
- 风险管理配置（止损、止盈、仓位）
- 第三方服务配置（天勤API占位符）
- 系统配置（日志等）

**conf.local.yaml** - 本地配置
- 天勤API密钥（敏感信息）
- 本地环境覆盖配置
- 不提交到git

### 使用方法

1. 复制 `conf.example.yaml` 为 `conf.local.yaml`
2. 填入真实的天勤API密钥
3. 根据需要调整其他配置

## ⚠️ 注意事项

### 私人项目配置说明

本项目保存了本地配置，注意以下路径问题：

1. **Conda 环境路径**: `/usr/local/Caskroom/miniconda/base/envs/quant_trading`
   - 如果conda安装位置不同，需要修改 `activate_env.sh` 和 `.vscode/settings.json`

2. **Python 解释器路径**: 见 `.vscode/settings.json`
   - 在新机器上需要更新为实际Python路径

3. **Pip 镜像源**: `.pip/pip.conf`
   - 配置了清华镜像源，如需更换可修改此文件

4. **API 密钥**: `conf.local.yaml`
   - 包含个人天勤量化API密钥
   - 不提交到版本控制

### 重要提示

1. **实盘风险**：量化交易存在风险，实盘交易可能导致资金损失
2. **充分测试**：实盘前务必在回测和模拟交易中充分验证策略
3. **资金管理**：合理控制仓位，避免过度交易
4. **持续监控**：实盘运行时应持续监控策略表现

## 版本历史

### v1.0.0 (2026-05-23)
- 初始版本发布
- 实现均线交叉策略
- 支持回测和实盘交易
- 风险控制机制

---

**最后更新：2026-05-23**
