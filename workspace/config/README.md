# 配置文件说明

本目录使用 TOML + Pydantic 管理项目配置。数据库环境隔离后，配置拆成「通用配置」「环境配置」「本机私密覆盖」三层。

## 文件职责

| 文件 | 是否提交 | 职责 |
|---|---:|---|
| `conf.toml` | 是 | 通用基础配置：策略参数、通用数据目录、第三方服务占位、回测默认值、日志、优化器等。不要放真实密钥，不放具体 data environment。 |
| `conf.backtest.toml` | 是 | backtest 环境覆盖：`app.mode`、`environment`、`data.environment`、`data.database_path`。 |
| `conf.test.toml` | 是 | test 环境覆盖：`app.mode`、`environment`、`data.environment`、`data.database_path`。 |
| `conf.live.toml` | 是 | live 环境覆盖：`app.mode`、`environment`、`data.environment`、`data.database_path`。 |
| `conf.example.toml` | 是 | 本机私密覆盖模板。复制为 `conf.<env>.local.toml` 后填写真实账号或本机参数。 |
| `conf.<env>.local.toml` | 否 | 本机私密覆盖，例如 `conf.backtest.local.toml`、`conf.test.local.toml`、`conf.live.local.toml`。用于真实 TqSdk 账号、broker 信息、本机调试参数。 |
| `conf.local.toml` | 否 | 旧通用 local 文件，已废弃，不再被标准 env 加载链读取。不要继续使用。 |

## 标准加载顺序

使用 `--env <env>` 时，加载顺序为：

```text
conf.toml
  ↓ deep merge
conf.<env>.toml
  ↓ deep merge（如果存在）
conf.<env>.local.toml
  ↓ validate / resolve paths
ProjectConfig
```

示例：

```bash
uv run python main.py backtest --env backtest --strategy ma --pattern "DCE\\.m"
uv run python main.py report --env backtest --limit 10
uv run python main.py test --env test --strategy ma --symbol DCE.m2509
uv run python main.py live --env live --strategy ma --symbol DCE.m2509
```

## 显式配置文件

使用 `--config <path>` 时，加载顺序为：

```text
conf.toml
  ↓ deep merge
--config 指定文件
  ↓ validate / resolve paths
ProjectConfig
```

显式配置文件必须最终提供：

```toml
[data]
environment = "backtest"  # backtest / test / live / unit_test
database_path = "project_data/database/backtest/quant.db"
```

如果同时传 `--env` 和 `--config`，`--config` 解析出的 `data.environment` 必须等于 `--env`，否则启动失败。

## 本机私密配置

首次配置本机账号时，不要修改 `conf.toml`，而是复制模板：

```bash
cp workspace/config/conf.example.toml workspace/config/conf.backtest.local.toml
cp workspace/config/conf.example.toml workspace/config/conf.test.local.toml
cp workspace/config/conf.example.toml workspace/config/conf.live.local.toml
```

然后在对应文件里填写：

```toml
[[third_party.services]]
name = "tqsdk"
provider = "tianqin"
api_key = "YOUR_TQ_API_KEY"
api_secret = "YOUR_TQ_API_SECRET"
account_type = "tqsim"          # tqsim / tqkq / tqaccount
broker_id = ""                  # account_type=tqaccount 时必填
broker_user = ""
broker_password = ""
enabled = true
```

这些 `conf.<env>.local.toml` 文件已被 `.gitignore` 忽略，不能提交。

## 配置放置原则

- 通用、可提交、无密钥的默认值放 `conf.toml`。
- 环境身份和数据库路径放 `conf.<env>.toml`。
- 真实账号、broker 信息、本机调试覆盖放 `conf.<env>.local.toml`。
- 不再使用旧字段 `data.db_path`；只使用 `data.environment` 和 `data.database_path`。
- 不再使用旧数据库 `project_data/database/quant_shared.db`。

## 相关代码

- `schemas.py`：Pydantic schema 和 `DataEnvironment` 类型。
- `manager.py`：配置加载、deep merge、路径解析、账户解析。
- `app_config.py` / `__init__.py`：对外兼容导出。
