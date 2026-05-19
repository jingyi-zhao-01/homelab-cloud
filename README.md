# homelab-cloud

## 当前状态

已完成微服务第一版实现，并提供 k3s 可用的 Helm Chart。

当前 Chart 已包含:

- 3 个业务微服务 (user/product/order)
- self-hosted PostgreSQL (StatefulSet + PVC)
- self-hosted Redis (StatefulSet + PVC)
- self-hosted RabbitMQ (StatefulSet + PVC)

当前服务:

- `user-service` (容器端口 `8001`)
- `product-service` (容器端口 `8002`)
- `order-service` (容器端口 `8003`)

服务调用关系:

- `order-service` -> `user-service` (校验用户)
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
nerdctl build -t flashsales/user-service:latest services/user-service
nerdctl build -t flashsales/product-service:latest services/product-service
nerdctl build -t flashsales/order-service:latest services/order-service
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
- 本项目不支持远端覆盖，非本地集群会直接拒绝执行。

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

## 后续工作

- 给数据库表补迁移方案 (当前是服务启动自动建表)
- 在 `order-service` 中接入 Redis 缓存与 RabbitMQ 事件发布
- 增加中间件 Secret 的外部化管理 (例如 SealedSecret)
- 增加 Ingress 统一对外入口
- 为三服务分别拆分独立 Helm Chart 或保留单体 Chart + 子图
