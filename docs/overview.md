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
# 编辑 conf.local.toml，填入 tqsdk 的 api_key 和