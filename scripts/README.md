# scripts/ 目录约定

## 规则（给所有写脚本的人看的）

- **入口脚本 → `.sh`**：用户直接跑的命令。负责环境激活、参数传递、循环控制。
- **复杂逻辑 → `.py`**：被 `.sh` 调用的 Python 脚本。做数据处理、拉取、业务逻辑。
- **临时验证脚本 → 默认放 `ai_tmp/`，用完就删**：AI/开发者为研究 loop、一次性诊断写的脚本放这里，不进入稳定工具目录；需要长期保留的自动化验证请写到 `tests/` 里。
- **稳定操作脚本 → `tools/`**：用户会反复直接使用、路径会被文档引用的仓库操作脚本，才放入 `tools/`。

## 当前脚本

| 脚本 | 用途 |
|------|------|
| `test.sh` | 统一验证（lint + format + type + unit，单一事实来源），支持按 stage / 业务域增量验证 |

## ai_tmp/ AI 临时研究脚本

`ai_tmp/` 用于放 AI/开发者的一次性研究 loop、诊断脚本和实验辅助脚本。这里的脚本默认不视为稳定 API：

- 可以被 roadmap 临时引用，用于复现实验；
- 不保证长期维护路径；
- 实验结束后应删除、迁入 `tests/`，或整理成 `tools/` 下的稳定脚本。

`tools/` 子目录见下方「[tools/ 运维与回测脚本](#tools-运维与回测脚本)」。

## tools/ 运维与回测脚本

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
