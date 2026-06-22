# tools/ 目录约定

## 规则（给所有写脚本的人看的）

- **入口脚本 → `.sh`**：用户直接跑的命令。负责环境激活、参数传递、循环控制。
- **复杂逻辑 → `.py`**：被 `.sh` 调用的 Python 脚本。做数据处理、拉取、业务逻辑。
- **临时验证脚本 → 用完就删**：不要进仓库。需要长期保留的自动化验证请写到 `tests/` 里。

## 当前脚本

| 脚本 | 用途 |
|------|------|
| `backtest-ma.sh` | 启动 MA 策略全链路回测（包含网格搜索） |
| `backtest-debug.sh` | DEBUG 单次回测（关搜索 + 指标落地 + 重建报告，可选 --profile） |
| `clean_data.sh` | 清理回测/Optuna 数据，保留 CSV 和 metadata |
| `fetch_data.sh` | 拉取多品种多周期 K 线数据（调用 `fetch_data.py`） |
| `fetch_data.py` | 单品种单周期数据拉取逻辑（被 `fetch_data.sh` 调用） |
| `test-signal.sh` | 启动实时信号链路测试（不下单，安全） |

## 命名建议

- 用途清晰，一眼能看懂
- `.sh` 用命令式动词开头：`fetch_xxx.sh`、`run_xxx.sh`、`clean_xxx.sh`
- 同一个功能的 `.sh` 和 `.py` 保持同名（例如 `fetch_data.sh` ↔ `fetch_data.py`）
