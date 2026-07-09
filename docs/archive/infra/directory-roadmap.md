# 目录结构长期规划

> 类型：Design / 已实现设计记录（目录演进规划）  
> 状态：已归档 — 可执行的迁移路线（阶段 0~3 含收尾）已全部落地，目录现状与规划对齐；阶段 4 及长期项（`risk`/`monitor`/`trading` 域、`deploy/`、`packages/python-common`、`shared-config` 等）按真实需求触发，本文件停止主动推进  
> 完成日期：2026-06-24  
> Git 参考：`102e201 feat: workspace/ 整体收纳（roadmap 阶段 3）`及其后续收尾提交  
> 目的: 为未来目录结构调整提供判断依据，避免为了整理目录而过度嵌套或一次性大迁移。后续如恢复演进，仍以本文「四、目录设计原则」为准绳。

---

## 一、背景

当前项目以单体 Python 工具链为主，同时已经包含 React 报告前端、CLI、脚本、文档和配置。根目录下同时存在业务代码、测试、文档、工具脚本和仓库级配置文件，长期看会带来两个问题：

1. 根目录认知负担增加，业务主体和工程配置混在一起；
2. 未来如果出现多语言、多服务协作，缺少稳定的目录演进原则。

本规划不要求立即调整现有目录。目录迁移必须在测试基线稳定、CI 覆盖充分、阶段目标明确时单独进行。

---

## 二、核心判断

### 1. 当前不追求完整 monorepo 模板

不采用一开始就很深的结构：

```text
workspace/services/quant-core/src/quant_core/domain/...
```

这类结构在大型工程中可能合理，但对当前项目会增加路径深度和维护成本。

### 2. 未来按业务域优先，而不是按语言优先

量化系统的核心边界更接近业务能力：

- 数据
- 策略
- 回测
- 交易
- 报告
- 风控
- 监控

因此未来第一层目录应优先反映业务域，而不是简单按 `python/`、`web/`、`services/`、`apps/` 切分。

### 3. 业务域内允许多语言协作

例如报告域可能同时包含：

- Python 报告数据生成；
- Web 前端展示；
- 报告数据契约；
- 报告相关文档。

这种复杂度来自真实业务边界，应该允许存在，但要控制嵌套深度。

---

## 三、长期目标结构

长期目标是根目录只承担仓库级职责，项目主体逐步收纳到 `workspace/` 下。

```text
quant/
  README.md
  CHANGELOG.md
  LICENSE

  .github/
  .gitignore
  .editorconfig
  .env.example
  .pre-commit-config.yaml

  scripts/
    test.sh
    lint.sh
    build.sh
    dev.sh
    tools/

  deploy/
    compose/
    k8s/
    docker/

  workspace/
    packages/
      contracts/
        schemas/
        openapi/
        protobuf/
      python-common/
      ts-common/
      shared-config/

    data/
      docs/

    strategy/
      docs/

    backtest/
      docs/

    trading/
      contracts/
      docs/

    report/
      contracts/
      docs/

    risk/
      contracts/
      docs/

    monitor/
      docs/

    cli/
      commands/
      workflows/

    tests/
    docs/
```

这是方向，不是一次性迁移目标。不存在真实需求的目录不应提前创建。

---

## 四、目录设计原则

### 原则 1：根目录只放仓库级文件

根目录保留：

```text
README.md
CHANGELOG.md
LICENSE
.github/
.gitignore
.editorconfig
.env.example
.pre-commit-config.yaml
scripts/
deploy/
workspace/
```

仓库级脚本、CI、编辑器配置、Git 配置留在根目录。业务代码、业务文档、业务工具应逐步进入 `workspace/`。

### 原则 2：`workspace/` 第一层按业务域

优先采用：

```text
workspace/data/
workspace/strategy/
workspace/backtest/
workspace/trading/
workspace/report/
workspace/cli/
workspace/packages/
```

不优先采用：

```text
workspace/python/
workspace/services/
workspace/apps/
```

`workspace/packages/` 是例外：它不表示业务域，而表示跨业务域、跨语言或跨运行环境复用的可安装共享包与契约。

### 原则 3：业务域内不按语言或形态划分子目录

业务域目录下直接放置该域的所有代码、资源和文档，不按 `python/`、`web/`、`api/` 等语言或形态拆分。

可以：

```text
workspace/report/        # Python 包、前端、文档共存
workspace/trading/       # Python 包、契约、文档共存
```

不建议：

```text
workspace/report/python/src/report/domain/application/usecases/
```

目录层级应服务于定位和边界，不服务于架构表演。

### 原则 4：跨语言共享契约，不共享语言内部实现

多语言协作时优先共享：

```text
contracts/
  schemas/
  openapi/
  protobuf/
```

不要让前端、Go 服务或其他语言依赖 Python 内部 `common` 实现。

业务域专属契约放在域内：

```text
workspace/report/contracts/
workspace/trading/contracts/
```

契约归属规则：

- 只被一个业务域使用：放在 `workspace/<domain>/contracts/`；
- 被多个业务域、多个运行单元或多种语言共同使用：放在 `workspace/packages/contracts/`；
- 先从业务域内开始，复用边界稳定后再上提到 `packages/contracts`。

跨多个业务域共享的契约放在：

```text
workspace/packages/contracts/
```

如果共享内容需要被某种语言直接引用，应作为该语言的独立 package 管理，例如：

```text
workspace/packages/python-common/
workspace/packages/ts-common/
```

服务或应用通过对应语言的 workspace/package 管理工具安装或链接后引用，不通过相对路径穿透引用。

### 原则 5：`common` 不急着抽成 package，但抽出后必须按 package 管理

当前 `common/` 更像核心 Python 项目内部公共模块，不应为了目录好看过早迁入 `packages/`。

只有当多个独立 Python 服务都需要复用，并且 API 稳定、可独立测试时，才考虑抽成：

```text
workspace/packages/python-common/
```

抽成 package 后，依赖方应通过 `uv workspace`、editable install 或其他包管理机制引用：

```text
from quant_common import ...
```

不要通过修改 `PYTHONPATH` 或跨目录相对路径直接引用 `packages/python-common` 内部文件。

### 原则 6：CLI 是入口，`cli/workflows` 承载命令级跨域编排

长期目标是：

```text
cli/commands -> cli/workflows -> data/strategy/backtest/trading/report
```

CLI 的命令入口负责参数解析、命令分发和用户输出，不直接承载数据、策略、回测、交易或报告的核心逻辑。

`cli/workflows` 负责命令级跨业务域编排，例如一次回测命令如何串联 data、backtest、report 等业务域。workflow 不应绑定 argparse 细节，应接收明确的请求对象，便于未来被 API、scheduler 或 worker 复用。

不新增顶层 `services/` 或 `application/` 作为长期目录承诺。各业务域内的 service/module 视为该业务域对外契约边界；当前通过 Python 函数/类调用，未来如需拆分为独立服务、worker 或 package，应优先沿这些契约边界拆分。

### 原则 7：目录按业务域组织，部署按运行单元组织

未来运行时可能由多个容器在 K8s 环境中协同工作，包括：

- 同步查询服务，例如报告 API、行情查询 API；
- 离线任务，例如历史数据更新、批量回测、参数优化；
- 队列消费者，例如信号处理、成交回报处理、通知发送；
- 常驻网关，例如 TQSDK 实盘交易网关、行情订阅网关。

目录结构不应因为运行时形态而把业务域打散。业务代码仍按业务域放在 `workspace/` 下；部署清单、Compose、K8s manifest、镜像构建入口放在仓库级 `deploy/` 下。

推荐约定：

```text
workspace/trading/python/        # trading 域代码
deploy/docker/trading-gateway.Dockerfile
deploy/k8s/trading-gateway.yaml

deploy/docker/backtest-worker.Dockerfile
deploy/k8s/backtest-worker.yaml

deploy/compose/dev.yaml
```

Dockerfile 命名跟随“可部署运行单元”，不强制跟随业务域目录名。一个业务域可以产生多个运行单元，例如 `trading-gateway`、`trading-worker`、`trading-reconciler`。

运行单元命名建议使用 `<domain>-<role>`：

- `<domain>-api`：同步查询或管理 API，例如 `report-api`、`market-data-api`；
- `<domain>-worker`：离线任务或批处理 worker，例如 `backtest-worker`；
- `<domain>-gateway`：外部系统连接网关，例如 `trading-gateway`；
- `<domain>-scheduler`：定时任务调度器，例如 `data-scheduler`；
- `<domain>-consumer`：队列消费者，例如 `notify-consumer`、`signal-consumer`。

`scripts/build.sh`、Dockerfile、K8s manifest 应使用同一运行单元名称，方便 CI 和部署系统统一映射。

### 原则 8：测试是横切验证层，顶层化，单向依赖所有业务域

`tests/`（未来 `workspace/tests/`）保持顶层单一目录，**不**拆进各业务域。它与「原则 2 业务域内聚」不冲突，因为测试是一个**横切关切**，不是第 N 个业务域：

```text
data / strategy / backtest / trading / report ...   ← 业务域，平级，按契约相互依赖
tests                                               ← 横切验证层，单向依赖所有业务域，不被任何域依赖
scripts                                             ← 横切工程操作层（同理放根级）
```

`tests` 与 `scripts` 是同一类东西——都不属于任何单一业务域、服务于全部域，因此都不进业务域目录。区别只在 `tests` 管正确性、`scripts` 管工程操作。

量化对正确性的强需求，使测试体系膨胀到接近一个独立关切：除单元测试外，还包含数值精度回归、历史数据回放、策略 PnL 基准对拍、滑点/手续费边界、可见性语义校验，以及专门的测试基础设施（fixture 数据集、golden files、对拍工具、确定性随机种子）。这些天然横切多个业务域，正是测试顶层化的合理性来源。

测试目录组织规则：

1. **严格与被测项目目录对齐**：`tests/<domain>/` ↔ `workspace/<domain>/`，便于定位。
2. **跨域 / `common` 的影响由依赖它的各业务域测试覆盖**：不为 `common` 单设测试域；改 `common` 由各依赖域的测试暴露问题。
3. **域间复用走共享 fixture / 测试工具**（放 `tests/` 公共层或 `workspace/packages`），**不**让一个域的测试硬调另一个域的 test case，避免测试间反向耦合。
4. **依赖方向单向**：测试 import 业务域代码，业务域代码永不 import 测试。

这条原则同时为「按业务域切分 pre-commit 增量验证」提供前置依据：当测试按域组织且域内自覆盖完整后，`files: ^<domain>/` 即可安全地只触发该域的检查；在此之前 commit 仍走全量门槛兜底（参见 `scripts/test.sh` 顶部演进规划）。

---

## 五、当前目录到未来目录的映射

| 当前目录 | 未来方向 | 说明 |
|----------|----------|------|
| `common/` | 短期保留在当前 Python 项目内；长期可抽为 `workspace/packages/python-common/` | 多个 Python 服务复用且 API 稳定后再抽 package |
| `config/` | `workspace/packages/shared-config/` 或业务域内配置模块 | 跨域共享配置契约可进 shared-config；业务私有配置留在业务域内 |
| `data/` | `workspace/data/` | 行情、数据源、数据存储、数据管理 |
| `strategies/` | `workspace/strategy/` | 策略核心、运行期结构、桥接器 |
| `backtest/` | `workspace/backtest/` | 回测、优化、walk-forward |
| `cli/` | `workspace/cli/` | 命令行入口、命令分发和命令级 workflows |
| `report/` | `workspace/report/` | Python 报告生成和 Web 报告展示共存于同一业务域 |
| `tests/` | `workspace/tests/` | 横切验证层，保持顶层单一目录（不拆进各业务域），内部按域子目录与被测代码对齐，详见原则 8 |
| `docs/` | `docs/` | 已迁回仓库根目录（2026-06-26），不再放入 `workspace/` |
| `tools/` | `scripts/tools/` | 操作脚本层（拉数据/回测/清数据等），与 `scripts/test.sh` 同属工程操作层，不属于任何业务域 |
| Dockerfile / Compose / K8s | `deploy/docker/`、`deploy/compose/`、`deploy/k8s/` | 按运行单元组织部署文件，不放入业务域目录 |
| `plan.md` | `docs/roadmap/plan.md` | 活跃路线图保留在 `roadmap/`，与已归档设计记录分开 |

---

## 六、推荐迁移路线

### 阶段 0：只记录规划，不移动目录

当前阶段只建立共识和文档，不做结构迁移。

### 阶段 1：先稳定 workflow 与业务域 service 契约边界

在现有结构下逐步引入 `cli/workflows`，让 CLI 命令入口和脚本减少对底层模块的直接依赖。

目标：

```text
cli/commands -> cli/workflows -> data/strategy/backtest/trading/report
```

各业务域维护自己的 service/module 契约，作为对外调用边界；暂不设计顶层跨多个业务域的 `services/`，避免形成无人明确维护的新杂烩层。

这一步比搬目录更重要。

### 阶段 2：选择一个业务域试点

优先选择 `report`，因为它已经天然包含 Python + Web 两部分。

目标形态：

```text
workspace/report/
  # Python 包（__init__.py, builder/, cache/, reporter/, writer/ 等）
  # 前端（web/）
  # 文档（README.md, docs/）
  # 契约（contracts/，如有）
```

试点成功后，再推广到其他业务域。

### 阶段 3：整体收纳到 `workspace/`

当测试、CI、路径配置稳定后，再逐步把业务目录迁入 `workspace/`。迁移时只做路径调整，不同时做逻辑重构。

### 阶段 4：按真实需要拆分新业务域

只有出现真实独立需求时，才新增：

```text
workspace/risk/
workspace/monitor/
workspace/trading/gateway/
workspace/data/service/
```

不要提前创建空目录或空服务。

---

## 七、工具和包管理原则

### Python

当前继续使用现有 Python 环境和项目配置。未来如果出现多个 Python 包，可考虑 `uv workspace`。

### Node / Web

前端继续使用 `npm` 或后续切换到 `pnpm workspace`。是否切换取决于前端包数量和共享依赖需求。

### 多语言统一入口

不优先引入 Bazel、Pants、Nx 等重型工具。未来可先用根目录 `scripts/` 统一编排：

```text
scripts/test.sh
scripts/lint.sh
scripts/build.sh
```

由脚本分别调用各语言自己的工具链。

### 容器构建入口

容器镜像由仓库级脚本统一构建，Dockerfile 放在 `deploy/docker/`，build context 默认使用仓库根目录，避免 Dockerfile 在不同业务域内各自假设不同上下文。

示例：

```text
scripts/build.sh trading-gateway
scripts/build.sh backtest-worker
scripts/build.sh report-web
```

脚本内部再映射到具体镜像：

```text
docker build \
  -f deploy/docker/trading-gateway.Dockerfile \
  -t quant/trading-gateway:dev \
  .
```

如果未来 CI 需要按改动范围选择构建对象，可以在 `scripts/` 中维护运行单元与业务域路径的映射，而不是把部署逻辑散落到各业务目录。

---

## 八、何时可以迁移目录

满足以下条件再做目录迁移：

1. Python tests 和前端 tests 都稳定；
2. CI 覆盖 Python 和前端；
3. 迁移目标明确，并且只做目录调整；
4. 迁移分支独立，不和功能开发混合；
5. 迁移前后完整运行 lint、typecheck、tests、build；
6. README、CI、pre-commit、脚本路径同步更新。

---

## 九、当前结论

当前阶段不急着改目录。长期方向是：

```text
根目录 = 仓库级配置和统一入口
workspace/ = 按量化业务域组织的项目主体
workspace/packages/ = 跨业务域、跨语言或跨运行环境复用的共享包与契约
业务域内 = 按语言/形态分 python/web/contracts/docs
```

目录结构应随真实业务边界逐步演进，避免为了形式上的规范引入过深嵌套。

---

## 十、实施记录

### 阶段 0.5（2026-06-19）

在回测重构 [阶段 0.5](./backtest-refactor-plan.md#阶段-05建立最小-json-契约测试) 中，`workspace/packages/contracts/` 和 `workspace/packages/python-contracts/` 已提前试点落地：

```text
workspace/packages/
  contracts/                          # 跨语言共享契约
    README.md
    schemas/
      run.schema.json                 # run 元信息
      summary.schema.json             # 回测摘要
      backtests.schema.json           # 回测明细
      equity.schema.json              # 权益曲线
      optuna.schema.json              # 参数优化历史
      trades.schema.json              # 交易记录
      logs.schema.json                # 运行日志
      nav.schema.json                 # 全局导航
  python-contracts/                   # Python 侧 schema loader + validator
    pyproject.toml                    # name="quantsmith-contracts"
    src/quantsmith_contracts/
      __init__.py
      schema.py                       # load_schema(name) -> dict
      validate.py                     # validate_run_artifacts(run_dir, nav_path) -> list[str]
    tests/
      conftest.py
      test_run_artifacts.py
```

要点：
- 8 份 JSON Schema（Draft 2020-12）定义前端 JSON 契约护栏，`additionalProperties: true` 允许扩展
- Python 子包通过 `uv pip install -e` 安装为 editable，测试已接入 pytest
- 根 `pyproject.toml` 已加 `[tool.uv.workspace] members` 和 `testpaths` 扩展
- 这是 `workspace/packages/` 提前试点，比 roadmap 原本规划的阶段 2（report 域试点）更早，但方向一致：先建立契约，再推进业务域迁移

### 阶段 1（2026-06-19）

在回测重构 [阶段 1](./backtest-refactor-plan.md#阶段-1抽出-outputlayout--runpaths) 中，集中管理 output 目录结构：

- 新建 `data/output_paths.py`：`output_root()` — 唯一暴露项目 output 根路径
- 新建 `report/output_paths.py`：`run_dir/run_data_dir/run_log_path/logs_json_path/nav_json_path` — run 维度路径
- 消除 27 处 `"output"` 硬编码，覆盖 8 个文件
- `BuildCache`/`KlineCache` 默认值改为 `output_root()`
- `DataFeed.create()` feeds 目录 / `parallel.py` workers 目录 改用 `output_root()`
- ruff + mypy + pytest contracts 全部通过

### 阶段 2（2026-06-24）

> roadmap 原规划：选择 report 域试点迁移到 `workspace/report/`。

**已完成**：

- `report/` → `workspace/report/`（git mv，保留完整 git 历史）
- `workspace/report/pyproject.toml`：独立 Python 项目，name=`quantsmith-report`
  - `package-dir = {"report" = "."}` — 物理目录 `workspace/report/` 映射为 Python 包 `report`
  - 依赖 `quantsmith`（主项目，提供 data、common 等包）
  - `[tool.uv.sources] quantsmith = { workspace = true }` — workspace 内依赖解析
- 主项目 `pyproject.toml` 调整：
  - `packages` 列表移除 `report`（不再由主项目打包）
  - `[tool.uv.workspace] members` 添加 `workspace/report`
  - `dependencies` 添加 `quantsmith-report`
  - `[tool.uv.sources] quantsmith-report = { workspace = true }`
  - `pythonpath` 改为 `[]`（不再需要项目根在 sys.path 中）
  - `addopts` 添加 `--import-mode=importlib`（解决 pytest + editable install 兼容性）
- `tests/__init__.py`：让 tests 成为 Python 包（importlib 模式需要）
- `tests/report/test_report.py`、`tests/data/test_database.py`：`from conftest import` → `from tests.conftest import`
- CI、pre-commit、scripts/test.sh：`report/web` → `workspace/report/web`

**验证**：ruff + mypy（82 文件）+ pytest（431 passed）全部通过

### 阶段 3（2026-06-24）

> roadmap 原规划：测试、CI、路径配置稳定后，把业务目录整体迁入 `workspace/`，只做路径调整不做逻辑重构。

**已完成**（commit `102e201 feat: workspace/ 整体收纳（roadmap 阶段 3）`）：

- `git mv` 全部剩余业务目录到 `workspace/`：`data/ backtest/ strategies/ cli/ common/ config/ tests/ tools/ docs/`（保留完整 git 历史，`strategies/` 保持原名）
- 主项目 `pyproject.toml`：
  - 新增 `[tool.setuptools.package-dir]` 映射物理路径（`workspace/<domain>`）↔ 包名（`<domain>`）
  - 更新 `testpaths`、`[tool.coverage]` omit/source、`[tool.ruff] per-file-ignores` 为 `workspace/` 前缀
- `scripts/test.sh`：域→路径映射全量更新为 `workspace/`；contracts 域 conftest 冲突用独立子 shell 分流
- `.pre-commit-config.yaml`：7 个域 hook 的 `files` 正则更新为 `^workspace/<domain>/`
- `.github/workflows/ci.yml`：mypy + pytest 路径更新为 `workspace/`
- `workspace/data/output_paths.py`：`_PROJECT_ROOT` 层级 `parent.parent` → `parent.parent.parent`（多一层 `workspace/`）

### 阶段 3 复核与修复（2026-06-24）

对阶段 3 提交做全面验证（ruff + mypy + pytest 全量 + 路径回归核查），发现并修复一处遗漏：

- **修复 `workspace/config/manager.py`**：`project_root` 推断仍为 `Path(__file__).parent.parent`（迁移后只到 `workspace/`），与 `output_paths.py` 的层级修正不一致。导致 `conf.toml` 中相对数据路径（`base_dir`/`export_dir`/`db_path`）解析到 `workspace/.quant_shared_data/` 而非仓库根的真实数据目录。改为 `Path(__file__).resolve().parent.parent.parent`（到仓库根），并清理误生成的 `workspace/.quant_shared_data/`。
- **同步 `README.md` 项目结构树**：补 `workspace/` 层级，移除已不存在的文件示例（`runners.py`/`builder.py`）。
- **修复 mypy 漏配 `mypy_path`（迁移引入的配置回归）**：迁移后业务包物理位置在 `workspace/` 下，但 `[tool.mypy]` 未把 `workspace` 设为包搜索根。导致 mypy 跨包 import（如 `data` → `common`/`config`）解析不到类型、回退成 `Any`，在 `warn_return_any=true` 下触发 11 个 `no-any-return` **误报**（代码本身无缺陷，迁移前 0 错误）。在 `pyproject.toml` 加 `mypy_path = "workspace"` 后归零。

**遗留（与本次迁移无关，未处理）**：`CONTRIBUTING.md` 内容整体陈旧（引用 flake8/pylint、不存在的文件、旧版本号、未带 `workspace/` 前缀的目录树），属独立的文档维护项。

**验证**：ruff ✓ + ruff format ✓（129 文件）+ mypy（68 文件，0 错误）+ pytest（428 passed / 3 skipped + contracts 1 passed）全部通过

### 阶段 3 收尾：业务域统一为主项目子包（2026-06-24）

阶段 2 曾把 report 拆成独立 workspace member（`quantsmith-report`）作试点。阶段 3 把其余业务域整体迁入 `workspace/` 后，出现「两种包管理模式并存」：report 是独立 member，其余域是主项目 `quantsmith` 的子包。为消除认知负担、统一管理模式，本次收敛：

- **打包配置去手写化**：根 `pyproject.toml` 的 `[tool.setuptools]` 手写 `package-dir` + `packages`（12 项）改为 `[tool.setuptools.packages.find]`（`where=["workspace"]` + `include`）。
  - 顺带修复手写列表的缺陷：原列表漏了 `cli.commands`、`cli.workflows`、`data.datasource` 三个子包，打 wheel 分发时会丢失（editable 开发模式因 `.pth` 指向整个 `workspace/` 而未暴露）。
- **report 并回主项目子包**：删除 `workspace/report/pyproject.toml`；根 `pyproject.toml` 的 `include` 加 `report*`，`[tool.uv.workspace] members` 移除 `workspace/report`，`dependencies` 移除 `quantsmith-report`，删除对应 `[tool.uv.sources]`。report 的依赖（optuna/loguru/pandas）主项目均已具备，无需新增。
  - 自此**所有业务域（含 report）统一为主项目 `quantsmith` 的子包**，由 `packages.find` 自动发现，不再各自维护 pyproject。
- **`packages/python-contracts` 保持独立 member**：它是 roadmap 定义的「跨业务域、跨语言复用的共享契约包」（原则 4 / packages 定位），用 `src/` 布局、有独立 conftest、主项目运行时不依赖它，本就是与业务域不同的另一类，故继续作为独立 workspace member。

调整后 workspace 下仅剩一个 Python 项目级 `pyproject.toml`（`packages/python-contracts`），业务域零散 pyproject 全部消除。

**验证**：`uv sync`（report 并入 quantsmith、`quantsmith-report` 卸载）+ ruff ✓ + mypy（主范围 68 文件 0 错误 / report 14 文件 0 错误）+ `uv build` wheel 含全部业务域子包（16 个 + report 5 个）+ report 单测 14 passed。（前端 `tsc` 因 node_modules 未安装报 vitest 类型缺失，属环境问题，与本次改动无关。）

### 阶段 3 收尾：`tools/` 迁移到 `scripts/tools/`（2026-06-24）

阶段 3 曾把 `tools/`（操作脚本：拉数据、清数据、跑回测/信号）收纳进 `workspace/`。复核后纠正分类：`tools/` 是**操作仓库用的脚本**，依赖方向是 tools → 业务域（tools import 业务代码，业务从不 import tools），与 `tests/`、`scripts/` 同属横切操作层，不属于任何业务域，不应放在按业务域组织的 `workspace/` 下。故迁到顶层 `scripts/tools/`：

- **`git mv workspace/tools → scripts/tools`**：与 `scripts/test.sh`、`scripts/activate_env.sh` 同层，统一为「仓库操作脚本」目录。
- **`fetch_data.py` 清理 sys.path hack**：删除 `PROJECT_ROOT = ...; sys.path.insert(...)`，因 editable 安装已把 `workspace/` 注入 `sys.path`，业务包可直接 import；docstring 用法路径改为 `uv run python scripts/tools/fetch_data.py`；连带删除根 `pyproject.toml` 中 `[tool.ruff.lint.per-file-ignores]` 对该文件的 `E402` 豁免（hack 删除后不再需要）。
- **修复 `.sh` 脚本的仓库根定位**：迁移前 `ROOT_DIR="$SCRIPT_DIR/.."` 从 `workspace/tools/` 解析到 `workspace/`，**本就是错的**（`main.py`、`output/`、`.quant_shared_data/` 均在仓库根）；迁到 `scripts/tools/` 后改为 `$SCRIPT_DIR/../..` 正确定位仓库根。涉及 `backtest-debug.sh`、`backtest-ma.sh`、`clean_data.sh`、`test-signal.sh`、`fetch_data.sh` 共 5 个。
- **文档同步**：`README.md` 结构树、`scripts/tools/README.md` 标题、本 roadmap 的长期结构图与映射表均更新。

**验证**：`bash scripts/test.sh lint`（全量 ruff）✓ + 5 个 `.sh` `bash -n` 语法检查 ✓ + `ROOT_DIR` 全部 `../..` + `fetch_data.py` 的 `from config / from data` import 在 `uv run` 下可用 ✓。
