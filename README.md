# homelab-cloud

A personal Kubernetes homelab running on k3s, used to practice platform engineering and infrastructure tooling.

## What this repo is for

| Namespace | Purpose |
|---|---|
| `flashsales` | Concurrency practice — multi-service workload with PostgreSQL, Redis, RabbitMQ |
| `strategy-tester` | Real workload — scheduled option data ingestion via Polygon API |

---

## Platform Features

### Kubernetes / Helm
- Two independent Helm charts, one per namespace
- HPA configured for all Deployments
- StatefulSets with PVC for PostgreSQL, Redis, RabbitMQ (flashsales)
- CronJobs for scheduled ingestion (strategy-tester)

### Secrets Management
- **External Secrets Operator** syncing from AWS SSM Parameter Store
- Separate `ClusterSecretStore` per namespace

| Chart | ClusterSecretStore | SSM prefix |
|---|---|---|
| `flashsales` | `flashsales-aws-ssm` | `/flashsales/prod/` |
| `strategy-tester` | `strategy-tester-aws-ssm` | `/strategy-tester/prod/` |

### CI/CD
Two independent parallel deploy workflows — changes to one namespace never trigger the other.

| Workflow | Trigger | Namespace |
|---|---|---|
| `deploy-flashsale.yml` | push to `flashsale/**` or `charts/flashsales/**` | `flashsales` |
| `deploy-strategy-tester.yml` | push to `strategy-tester/**` or `charts/strategy-tester/**` | `strategy-tester` |
| `perf-concurrency-suite.yml` | `deploy-flashsale` succeeds | — |
| `loadtest-manual.yml` | manual `workflow_dispatch` | — |
| `terraform-provision.yml` | manual | — |

### Observability
- Grafana k6 load testing with ramp-up/steady/ramp-down phases
- Concurrency suite auto-triggered after each flashsale deploy
- Grafana Cloud monitoring via `secrets/grafana-k8s-monitoring-values.yaml`

### Developer Tooling
- **pre-commit** hooks: trailing whitespace, end-of-file, YAML lint (excluding Helm templates), `helm lint` for both charts
- **uv** as package manager; pre-commit installed as dev dependency via `uv sync --extra dev`
- **Makefile** targets: `deploy`, `status`, `fix-images`, `loadtest`, `loadtest-quick`

---

## Repository Layout

```text
.
├── charts/
│   ├── flashsales/              # Helm chart — concurrency practice workload
│   └── strategy-tester/         # Helm chart — real scheduled ingestion workload
├── services/                    # flashsales microservice source (FastAPI)
│   ├── user-service/
│   ├── product-service/
│   └── order-service/
├── perf/                        # k6 load test scripts + shell wrappers
├── scripts/
│   └── e2e-smoke.sh
├── secrets/                     # gitignored: kubeconfig, Grafana tokens
├── .github/workflows/
├── .pre-commit-config.yaml
├── pyproject.toml
└── Makefile
```

---

## Quick Start

**Deploy flashsales (concurrency workload)**
```bash
kubectl create namespace flashsales --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install flashsales charts/flashsales -n flashsales
```

**Deploy strategy-tester (real workload)**
```bash
kubectl create namespace strategy-tester --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install strategy-tester charts/strategy-tester \
  -n strategy-tester \
  --set externalSecrets.enabled=true
```

**Run concurrency load test**
```bash
make loadtest KUBECONFIG_PATH=secrets/.kube-config
```

**Run e2e smoke test**
```bash
./scripts/e2e-smoke.sh
```

---

## Required Secrets (GitHub Actions)

```
KUBE_CONFIG_DATA        # base64-encoded kubeconfig
GHCR_PULL_USERNAME
GHCR_PULL_TOKEN         # read:packages scope
AWS_ACCESS_KEY_ID       # for ESO → SSM
AWS_SECRET_ACCESS_KEY
```
│   ├── flashsales/          # flashsales Helm Chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   └── strategy-tester/     # strategy-tester Helm Chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── services/                # flashsales 微服务源码
│   ├── user-service/
│   ├── product-service/
│   └── order-service/
├── perf/                    # 性能测试脚本
│   ├── loadtest.js
│   ├── loadtest-lite.js
│   ├── loadtest-high.js
│   ├── concurrency-test.js
│   ├── loadtest-k6.sh
│   └── perf.mk
├── scripts/
│   └── e2e-smoke.sh
├── secrets/                 # 本地 kubeconfig（不提交到 git）
├── .github/workflows/
│   ├── deploy-flashsale.yml        # flashsales 命名空间部署
│   ├── deploy-strategy-tester.yml  # strategy-tester 命名空间部署
│   ├── perf-concurrency-suite.yml  # deploy-flashsale 成功后自动触发
│   ├── loadtest-manual.yml         # 手动压测
│   └── terraform-provision.yml     # 基础设施 Terraform
├── .pre-commit-config.yaml
├── pyproject.toml
└── Makefile
```

---

## flashsales

### 服务架构

- `user-service` (端口 `8001`) → PostgreSQL
- `product-service` (端口 `8002`) → PostgreSQL
- `order-service` (端口 `8003`) → PostgreSQL / Redis / RabbitMQ
- `order-service` → `user-service`（校验用户）
- `order-service` → `product-service`（查询商品、扣库存）

基础设施（自托管）：PostgreSQL · Redis · RabbitMQ（均为 StatefulSet + PVC）

### 部署

```bash
# 创建命名空间
kubectl create namespace flashsales --dry-run=client -o yaml | kubectl apply -f -

# Helm 部署
helm upgrade --install flashsales charts/flashsales -n flashsales

# 或使用 Make
make deploy KUBECONFIG_PATH=$HOME/.kube/config
```

### E2E 验证

```bash
./scripts/e2e-smoke.sh
```

通过标准：三个业务服务 + 中间件 Pod 全部 Running，脚本输出 `E2E PASS`。

### 接口调试（port-forward）

```bash
kubectl port-forward -n flashsales svc/flashsales-user-service 8001:8001
kubectl port-forward -n flashsales svc/flashsales-product-service 8002:8002
kubectl port-forward -n flashsales svc/flashsales-order-service 8003:8003
```

```bash
curl -X POST http://localhost:8001/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice","email":"alice@example.com"}'

curl -X POST http://localhost:8002/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"Keyboard","price":199,"stock":10}'

curl -X POST http://localhost:8003/orders \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"items":[{"product_id":1,"quantity":2}]}'
```

---

## strategy-tester

### 服务架构

- `option-ingestor`：期权数据采集，CronJob 每天 **21:00 EST**（UTC `0 2 * * *`）
- `snapshot-ingestor`：持仓快照采集，CronJob 每天 **23:00 EST**（UTC `0 4 * * *`）

Secrets 通过 **External Secrets Operator** 从 AWS SSM Parameter Store 注入：

| SSM 路径 | 注入为 |
|---|---|
| `/strategy-tester/prod/DATABASE_URL` | `DATABASE_URL` |
| `/strategy-tester/prod/POLYGON_API_KEY` | `POLYGON_API_KEY` |

### 部署

```bash
kubectl create namespace strategy-tester --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install strategy-tester charts/strategy-tester \
  -n strategy-tester \
  --set externalSecrets.enabled=true
```

---

## External Secrets Operator

两个命名空间均使用 ESO 从 AWS SSM 拉取 Secrets：

| Chart | ClusterSecretStore | SSM 前缀 |
|---|---|---|
| `flashsales` | `flashsales-aws-ssm` | `/flashsales/prod/` |
| `strategy-tester` | `strategy-tester-aws-ssm` | `/strategy-tester/prod/` |

ESO 凭据通过 `aws-ssm-credentials` Secret 注入（namespace `external-secrets`）。

---

## CI/CD (GitHub Actions)

### 工作流概览

| 工作流 | 触发 | 命名空间 |
|---|---|---|
| `deploy-flashsale.yml` | push → `flashsale/**` 或 `charts/flashsales/**` | `flashsales` |
| `deploy-strategy-tester.yml` | push → `strategy-tester/**` 或 `charts/strategy-tester/**` | `strategy-tester` |
| `perf-concurrency-suite.yml` | `deploy-flashsale` 成功后自动触发 | — |
| `loadtest-manual.yml` | 手动 `workflow_dispatch` | — |
| `terraform-provision.yml` | 手动 | — |

两个 deploy 工作流**相互独立、可并行运行**。

### 所需 Repository Secrets

```
KUBE_CONFIG_DATA       # base64 编码的 kubeconfig
GHCR_PULL_USERNAME
GHCR_PULL_TOKEN        # 需要 read:packages 权限
AWS_ACCESS_KEY_ID      # 用于 ESO 读取 SSM
AWS_SECRET_ACCESS_KEY
```

生成 `KUBE_CONFIG_DATA`：

```bash
base64 -w 0 secrets/.kube-config
```

---

## 性能测试

```bash
# 标准压测
make loadtest KUBECONFIG_PATH=secrets/.kube-config

# 快速压测
make loadtest-quick KUBECONFIG_PATH=secrets/.kube-config

# 自定义参数
bash ./perf/loadtest-k6.sh \
  -e RAMP_UP=30s \
  -e STEADY=180s \
  -e TARGET_VUS=50
```

---

## 开发工具

### pre-commit hooks

```bash
uv sync --extra dev
uv run pre-commit install
```

包含：trailing-whitespace · end-of-file-fixer · check-yaml（排除 Helm templates）· helm lint（flashsales + strategy-tester）

### Make 命令

```bash
make deploy          # 本地 k3s 部署（有 localhost 保护）
make status          # 查看 Pod / Service 状态
make fix-images      # 重建本地镜像并导入 k3s containerd
make loadtest        # 运行 k6 压测
```
- `order-service` -> `product-service` (查询商品和扣库存)
- `user-service` -> `PostgreSQL` (用户持久化存储)
- `product-service` -> `PostgreSQL` (商品与库存持久化存储)
- `order-service` -> `PostgreSQL` (订单持久化存储)

## 目录结构

```text
.
├── charts/flashsales
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── user-deployment.yaml
│       ├── user-service.yaml
│       ├── product-deployment.yaml
│       ├── product-service.yaml
│       ├── order-deployment.yaml
│       ├── order-service.yaml
│       ├── postgres-secret.yaml
│       ├── postgres-service.yaml
│       ├── postgres-statefulset.yaml
│       ├── redis-secret.yaml
│       ├── redis-service.yaml
│       ├── redis-statefulset.yaml
│       ├── rabbitmq-secret.yaml
│       ├── rabbitmq-service.yaml
│       └── rabbitmq-statefulset.yaml
└── services
    ├── user-service
    │   ├── app/main.py
    │   ├── requirements.txt
    │   └── Dockerfile
    ├── product-service
    │   ├── app/main.py
    │   ├── requirements.txt
    │   └── Dockerfile
    └── order-service
        ├── app/main.py
        ├── requirements.txt
        └── Dockerfile
```

## k3s 部署步骤

安全提示:

- 本项目默认只部署到本机 k3s。
- 请使用本机 kubeconfig (通常是 `$HOME/.kube/config`)。
- 仓库内的 `.kube-config` 当前指向远端地址，请勿直接用于本地部署。

1. 使用 containerd 生态工具构建镜像 (不使用 Docker)

```bash
nerdctl build -t flashsales/user-service:latest flashsale/user-service
nerdctl build -t flashsales/product-service:latest flashsale/product-service
nerdctl build -t flashsales/order-service:latest flashsale/order-service
```

1. 导入镜像到 k3s 的 containerd

```bash
nerdctl save flashsales/user-service:latest | sudo k3s ctr images import -
nerdctl save flashsales/product-service:latest | sudo k3s ctr images import -
nerdctl save flashsales/order-service:latest | sudo k3s ctr images import -
```

1. 可选: 不在本地构建，直接使用镜像仓库

说明:

- 如果你有私有/公共仓库镜像，可跳过上面两步。
- 只需在 `charts/flashsales/values.yaml` 中把三个服务的 `image.repository` 和 `image.tag` 改成仓库地址，然后直接执行 Helm 部署。

1. 部署 Helm Chart

```bash
KUBECONFIG=$HOME/.kube/config kubectl create namespace flashsales --dry-run=client -o yaml | KUBECONFIG=$HOME/.kube/config kubectl apply -f -
KUBECONFIG=$HOME/.kube/config helm upgrade --install flashsales charts/flashsales -n flashsales
```

1. 推荐: 使用 Make 命令一键部署

```bash
make deploy KUBECONFIG_PATH=$HOME/.kube/config
```

说明:

- `make deploy` 默认带本地集群保护，检测到非 localhost/127.0.0.1 会拒绝执行。
- 远端 VPS 部署建议通过 GitHub Actions 自动化流程执行，见下文 CI/CD 章节。

1. 检查 Pod

```bash
KUBECONFIG=$HOME/.kube/config kubectl get pods -n flashsales
KUBECONFIG=$HOME/.kube/config kubectl get svc -n flashsales
```

也可使用:

```bash
make status KUBECONFIG_PATH=$HOME/.kube/config
```

如果业务服务出现 `ErrImagePull` / `ImagePullBackOff`:

```bash
make fix-images KUBECONFIG_PATH=$HOME/.kube/config
```

说明:

- `make fix-images` 会构建本地镜像、导入 k3s containerd，并重启业务 Deployment。
- 导入步骤需要 `sudo k3s ctr` 权限。

## E2E Milestone (M1)

目标:

- 在 k3s 上跑通完整业务链路: 创建用户 -> 创建商品 -> 创建订单
- 订单成功后库存正确扣减
- 结果可重复执行

通过标准:

- 三个业务服务 Pod 全部 Running
- 中间件 Pod 全部 Running
- E2E 脚本输出 `E2E PASS`

一键执行:

```bash
./scripts/e2e-smoke.sh
```

可选参数:

```bash
KUBECONFIG_PATH=$HOME/.kube/config NAMESPACE=flashsales USER_PORT=18001 PRODUCT_PORT=18002 ORDER_PORT=18003 ./scripts/e2e-smoke.sh
```

## 验证接口

可通过 `kubectl port-forward` 验证:

```bash
kubectl port-forward -n flashsales svc/flashsales-user-service 8001:8001
kubectl port-forward -n flashsales svc/flashsales-product-service 8002:8002
kubectl port-forward -n flashsales svc/flashsales-order-service 8003:8003
```

示例请求:

```bash
curl -X POST http://localhost:8001/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice","email":"alice@example.com"}'

curl -X POST http://localhost:8002/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"Keyboard","price":199,"stock":10}'

curl -X POST http://localhost:8003/orders \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"items":[{"product_id":1,"quantity":2}]}'
```

## 验证中间件

查看中间件资源:

```bash
kubectl get pods -n flashsales | grep -E 'postgres|redis|rabbitmq'
kubectl get pvc -n flashsales
```

查看服务连通性:

```bash
kubectl get svc -n flashsales | grep -E 'postgres|redis|rabbitmq'
```

RabbitMQ 管理面板端口转发:

```bash
kubectl port-forward -n flashsales svc/flashsales-rabbitmq 15672:15672
```

## Grafana k6 Load Test

用途:

- 对 `order-service` 发压测请求
- 在测试开始前自动创建测试用户和测试商品
- 通过 `kubectl port-forward` 连接远端或本地 k3s 服务

前置要求:

- 已安装 `k6`
- 已安装 `kubectl`
- `KUBECONFIG_PATH` 指向可访问目标集群的 kubeconfig

快速执行:

```bash
make loadtest KUBECONFIG_PATH=.kube-config
```

短时压测:

```bash
make loadtest-quick KUBECONFIG_PATH=.kube-config
```

自定义并发和时长示例:

```bash
bash ./perf/loadtest-k6.sh \
  -e RAMP_UP=30s \
  -e STEADY=180s \
  -e RAMP_DOWN=30s \
  -e TARGET_VUS=50
```

说明:

- k6 场景脚本在 `perf/loadtest.js`
- 包装脚本在 `perf/loadtest-k6.sh`
- 包装脚本会自动选择可用本地端口并在结束后清理 port-forward 进程

GitHub Actions 手动触发:

- workflow 文件: `.github/workflows/loadtest-manual.yml`
- 触发方式: Actions 页面手动点击 `Run workflow`
- 可配置输入参数:
  - `target_vus` (默认 `20`)
  - `ramp_up` (默认 `20s`)
  - `steady` (默认 `60s`)
  - `ramp_down` (默认 `20s`)

说明:

- 此压测 workflow 仅支持手动触发 (`workflow_dispatch`)，不会在 push 时自动运行。
- 依赖仓库 Secret `KUBE_CONFIG_DATA` 用于连接远端 k3s。

## 后续工作

- 给数据库表补迁移方案 (当前是服务启动自动建表)
- 在 `order-service` 中接入 Redis 缓存与 RabbitMQ 事件发布
- 增加中间件 Secret 的外部化管理 (例如 SealedSecret)
- 增加 Ingress 统一对外入口
- 为三服务分别拆分独立 Helm Chart 或保留单体 Chart + 子图

## GitHub Actions 远端部署 (VPS k3s)

已新增工作流:

- `.github/workflows/deploy-remote-vps.yml`

流程:

1. push 到 `main` 或手动触发 workflow
1. 构建 3 个服务镜像
1. 推送镜像到 `ghcr.io`
1. 使用仓库 Secret 中的 kubeconfig 连接远端 k3s
1. 执行 `helm upgrade --install` 完成部署

需要配置的仓库 Secret:

1. `KUBE_CONFIG_DATA`
1. `GHCR_PULL_USERNAME`
1. `GHCR_PULL_TOKEN`

生成方式示例:

```bash
base64 -w 0 .kube-config
```

将输出结果完整复制到 GitHub Repository Secrets 的 `KUBE_CONFIG_DATA`。

说明:

- 工作流会将镜像推到 `ghcr.io/<owner>/flashsales-<service>:<commit_sha>`。
- Helm 部署时使用对应 commit sha 的 tag，保证部署版本可追踪。
- workflow 会在目标 namespace 自动创建 `ghcr-pull-secret` 并注入 chart 的 `imagePullSecrets`。
- `GHCR_PULL_TOKEN` 需要包含 `read:packages` 权限（classic PAT）或等价 package 读取权限。
