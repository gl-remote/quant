# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.2.0-dev] - 2026-05-27

### 新增
- **Runs 追踪系统**: `runs`/`run_studies` 表，每次回测有 run_id，输出到 `output/r{id}/`
- **Jinja2 模板引擎**: `report/` 重构为 `builder.py` + `queries/` + `templates/` 三层分离
- **backtest_params 拆表**: 替代 `params_json` 列，参数可 SQL 查询按品种/按值筛选
- **全量单回测报告**: 回测时生成全部品种的 `backtest_N.html`，非仅一份
- **页面板块 ID**: `[NAV]` `[BT-SUM]` `[OPT-CONV]` 等统一前缀，精确定位
- **看板系统**: `output/index.html` 导航页 + `r1/index.html` 双 Tab 看板 (回测 + 优化)
- **单回测多板块**: `[BT-METRICS]` + `[BT-EQ]` + `[BT-TRADES]` 三板块
- **本地 Plotly.js**: `output/assets/plotly.min.js`，零网络请求
- **多数据源抽象**: `data/datasource/` — tqsdk / akshare 切换

### 修复
- `clean_data.sh` 白名表单精确清理，保留 `export_metadata` + CSV
- `report --id` 自动归入 `output/r{run}/` 目录
- `test-ma.sh` PYTHON_PATH 路径嵌套 bug
- plotly CDN 不可用 → 本地文件

### 移除
- `report/dashboard.py` → `builder.py` + 模板
- `report/_html.py` → `templates/single_report.html`
- `backtests.params_json` 列 → `backtest_params` 表

### 改动
- `fetch_data.py` 默认跳过已有数据，`--force` 强制重拉
- `tools/` 目录集中存放 shell 脚本
- `[data].provider` 与 `[backtest].provider` 职责分离
- `serialize_strategy_params` 返回值 `str` → `dict`

---

## [0.1.0] - 2026-05-25

### 新增
- 项目初始化：vnpy 回测引擎 + 双均线策略
- CLI 命令系统：export / test / backtest / report / live
- Optuna 参数优化 (GridSampler + TPESampler)
- Plotly 可视化 + HTML 报告
- Pandera Schema 数据校验
- peewee ORM + SQLite 持久化
