# 项目改进计划 v0.0.9 归档

## 变更概述

根目录瘦身：删除 5 个冗余配置文件 + 移动 3 个 config yaml 到 config/ 目录。plan.md 从 v0.0.8 归档后重写为 v0.0.9。

## 删除的文件

| 文件 | 原因 |
|------|------|
| `pytest.ini` | 已迁入 pyproject.toml `[tool.pytest.ini_options]` |
| `.flake8` | 已迁入 pyproject.toml `[tool.flake8]` |
| `.pylintrc` | 已迁入 pyproject.toml `[tool.pylint.*]` |
| `.coveragerc` | 已迁入 pyproject.toml `[tool.coverage.*]` |
| `requirements.txt` | 已由 pyproject.toml `[project] dependencies` 替代 |

## 移动的文件

| 文件 | 旧路径 | 新路径 |
|------|--------|--------|
| `conf.yaml` | `/conf.yaml` | `/config/conf.yaml` |
| `conf.example.yaml` | `/conf.example.yaml` | `/config/conf.example.yaml` |
| `conf.local.yaml` | `/conf.local.yaml` | `/config/conf.local.yaml` |

## 修改的文件

| 文件 | 变更 |
|------|------|
| `pyproject.toml` | 新增 `[tool.coverage.run]` 和 `[tool.coverage.report]`，移除 `--cov-config=.coveragerc` |
| `config/config_manager.py` | `Path('conf.yaml')` → `Path(__file__).parent / 'conf.yaml'` |
| `.github/workflows/ci.yml` | 移除 `--cov-config=.coveragerc` |
| `main.py` | 日志消息路径更新 |
| `README.md` | 项目结构图更新，安装命令改为 `pip install -e ".[dev]"` |
| `AI_BEHAVIOR_RULES.md` | 项目结构图更新 |
| `doc/configuration.md` | 配置路径更新 |
| `doc/architecture.md` | 目录结构图更新 |
| `doc/usage-guide.md` | 配置路径更新 |
| `doc/faq.md` | 配置路径更新 |
| `config/conf.yaml` | 注释中路径引用更新 |
| `config/conf.example.yaml` | 注释中路径引用更新 |

## 项目状态快照

- 测试: 127 用例全部通过 (1.64s), 覆盖率 82%
- 根目录文件数: 17 → 9（减少 47%）
- AI_BEHAVIOR_RULES.md: v0.0.6
- plan.md: v0.0.8 → v0.0.9
- 当前阶段: M3 功能增强