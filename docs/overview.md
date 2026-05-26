# 项目概览

> 版本: 0.2.0-dev | 最后更新: 2026-05-26

---

## 项目简介

天勤量化均线交叉策略交易系统是一个基于 Python 的量化交易框架，提供完整的策略研发、回测、优化和实盘交易能力。

### 核心特性

| 特性 | 说明 |
|------|------|
| **策略引擎** | 双均线交叉策略，支持金叉买入、死叉卖出、止损止盈 |
| **多引擎支持** | vn.py 批量回测 + TqSdk 图形化回测 |
| **参数优化** | 网格搜索 + Optuna 贝叶斯优化 |
| **Walk-Forward** | 滚动时间窗口验证，评估策略稳健性 |
| **数据管理** | 统一数据访问入口，支持 Pandera Schema 验证 |
| **报告生成** | 自动生成回测报告和优化报告 |

### 技术栈

| 分类 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 回测引擎 | vn.py、TqSdk |
| 数据处理 | pandas、Pandera |
| 配置管理 | Pydantic、TOML |
| 数据库 | SQLite + peewee ORM |
| 可视化 | Plotly |

---

## 快速开始

### 安装依赖

```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .
```

### 配置账户

复制配置模板并填写天勤 API 密钥：

```bash
cp config/conf.example.toml config/conf.local.toml
# 编辑 conf.local.toml，填入 tqsdk 的 api_key 和 api_secret
```

### 运行回测

**单品种回测（带 GUI）**：
```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --start 2024-01-01 --end 2024-12-31 --gui
```

**批量回测**：
```bash
python main.py backtest --pattern "DCE\.m" --strategy ma
```

**参数优化**：
```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --optimizer optuna --mode search
```

**Walk-Forward 验证**：
```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --mode walk-forward
```

---

## 项目结构

```
quant/
├── main.py                    # 命令行入口
├── cli/                       # 命令行子包
│   ├── main.py                # 参数解析与命令分发
│   └── commands/              # 子命令实现
├── strategies/                # 策略子系统
│   ├── core/                  # 抽象接口
│   ├── bridges/               # 框架桥接器
│   └── ma_strategy.py         # 均线策略核心
├── backtest/                  # 回测引擎
├── optimizer/                 # 参数优化器
├── data/                      # 数据管理
├── report/                    # 报告生成
├── common/                    # 通用工具
├── config/                    # 配置管理
└── tests/                     # 测试用例
```

---

## 主要命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `export` | 导出 K 线数据 | `python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31` |
| `test` | 策略逻辑测试 | `python main.py test --strategy ma` |
| `backtest` | 统一回测 | `python main.py backtest --symbol DCE.m2509 --strategy ma` |
| `report` | 查看回测报告 | `python main.py report --id 42` |
| `live` | 实盘交易 | `python main.py live --symbol DCE.m2509 --strategy ma` |

---

## 目录说明

| 目录 | 职责 |
|------|------|
| `cli/` | 命令行接口，负责参数解析和命令分发 |
| `strategies/` | 策略核心，包含策略基类和具体实现 |
| `backtest/` | 回测引擎，封装 vn.py 和 TqSdk |
| `optimizer/` | 参数优化，支持网格搜索和贝叶斯优化 |
| `data/` | 数据层，统一数据访问和持久化 |
| `report/` | 报告生成，包含可视化和 HTML 报告 |
| `common/` | 通用工具，纯函数库（零依赖） |
| `config/` | 配置管理，TOML 分层配置 |
