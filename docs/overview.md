# 项目概览

> 版本: 0.2.0-dev | 最后更新: 2026-05-27

---

## 项目简介

天勤量化均线交叉策略交易系统是一个基于 **Python + React** 的量化交易框架，提供完整的策略研发、回测、优化和实盘交易能力。

### 核心特性

| 特性 | 说明 |
|------|------|
| **策略引擎** | 双均线交叉策略，支持金叉买入、死叉卖出、止损止盈 |
| **多引擎支持** | vn.py 批量回测 + TqSdk 图形化回测 |
| **参数优化** | 网格搜索 + Optuna 贝叶斯优化 |
| **Walk-Forward** | 滚动时间窗口验证，评估策略稳健性 |
| **数据管理** | 统一数据访问入口，支持 Pandera Schema 验证 |
| **报告生成** | React + Plotly 可视化报告，支持 `file://` 协议直接打开 |

### 技术栈

| 分类 | 技术 |
|------|------|
| 后端 | Python 3.10+、vn.py、TqSdk |
| 前端 | React 18、TypeScript、Vite、Plotly |
| 数据库 | SQLite + peewee ORM |
| 配置 | Pydantic、TOML |

---

## 快速开始

### 安装依赖

```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .

# 前端依赖（报告模块）
cd report/web
npm install
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

**查看报告**：
```bash
open output/index.html
```

---

## 项目结构

```
quant/
├── main.py                    # 命令行入口
├── cli/                       # 命令行子包
├── strategies/                # 策略子系统
├── backtest/                  # 回测引擎
├── optimizer/                 # 参数优化器
├── data/                      # 数据管理
├── report/                    # 报告生成
│   └── web/                   # React 前端工程
├── common/                    # 通用工具
├── config/                    # 配置管理
└── docs/                      # 项目文档
```

---

## 主要命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `export` | 导出 K 线数据 | `python main.py export --symbol DCE.m2509` |
| `test` | 策略逻辑测试 | `python main.py test --strategy ma` |
| `backtest` | 统一回测 | `python main.py backtest --symbol DCE.m2509` |
| `report` | 查看回测报告 | `python main.py report --id 42` |
| `live` | 实盘交易 | `python main.py live --symbol DCE.m2509` |

---

## 核心模块

| 模块 | 职责 |
|------|------|
| `cli/` | 命令行接口，参数解析和命令分发 |
| `strategies/` | 策略核心，桥接器模式实现框架无关性 |
| `backtest/` | 回测引擎，vn.py 批量回测 + Walk-Forward |
| `optimizer/` | 参数优化，网格搜索 + 贝叶斯优化 |
| `data/` | 数据层，统一数据访问和持久化 |
| `report/` | 报告生成，Python 数据导出 + React 前端渲染 |
| `common/` | 通用工具，纯函数库（零依赖） |