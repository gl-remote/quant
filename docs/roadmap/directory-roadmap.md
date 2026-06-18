# 目录结构长期规划

> 状态: 规划性文档  
> 目的: 为未来目录结构调整提供判断依据，避免为了整理目录而过度嵌套或一次性大迁移。

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
      python/
      tools/
      docs/

    strategy/
      python/
      docs/

    backtest/
      python/
      docs/

    trading/
      python/
      contracts/
      docs/

    report/
      python/
      web/
      contracts/
      docs/

    risk/
      python/
      contracts/
      docs/

    monitor/
      web/
      api/
      docs/

    cli/
      python/
        commands/
        workflows/

    tests/
    docs/
    tools/
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

### 原则 3：业务域内最多一层语言或形态目录

可以：

```text
workspace/report/python/
workspace/report/web/
workspace/report/contracts/
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

---

## 五、当前目录到未来目录的映射

| 当前目录 | 未来方向 | 说明 |
|----------|----------|------|
| `common/` | 短期保留在当前 Python 项目内；长期可抽为 `workspace/packages/python-common/` | 多个 Python 服务复用且 API 稳定后再抽 package |
| `config/` | `workspace/packages/shared-config/` 或业务域内配置模块 | 跨域共享配置契约可进 shared-config；业务私有配置留在业务域内 |
| `data/` | `workspace/data/python/` | 行情、数据源、数据存储、数据管理 |
| `strategies/` | `workspace/strategy/python/` | 策略核心、运行期结构、桥接器 |
| `backtest/` | `workspace/backtest/python/` | 回测、优化、walk-forward |
| `cli/` | `workspace/cli/python/` | 命令行入口、命令分发和命令级 workflows；`cli/commands` 负责适配命令行，`cli/workflows` 负责编排跨域任务 |
| `report/` | `workspace/report/python/` + `workspace/report/web/` | Python 报告生成和 Web 报告展示分离到同一业务域 |
| `tests/` | `workspace/tests/` | 可继续按业务域组织测试 |
| `docs/` | `workspace/docs/` | 长期可迁移；当前先保留根目录 docs |
| `tools/` | `workspace/tools/` | 业务辅助工具 |
| Dockerfile / Compose / K8s | `deploy/docker/`、`deploy/compose/`、`deploy/k8s/` | 按运行单元组织部署文件，不放入业务域目录 |
| `plan.md` | `workspace/docs/project/plan.md` | 当前频繁使用，迁移优先级较低 |

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
  python/
  web/
  contracts/
  docs/
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
