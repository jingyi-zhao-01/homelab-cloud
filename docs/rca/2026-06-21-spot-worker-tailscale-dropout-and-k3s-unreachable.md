# Spot Worker Tailscale 掉线导致 K3s Worker 失联 RCA（2026-06-21）

## 摘要

`2026-06-21`，AWS spot worker `ip-10-44-2-229-c0fd05f3` 仍然处于 `EC2 running`
状态，但从 `Tailscale` tailnet 中掉线，导致该节点上的 `k3s-agent / kubelet`
无法继续通过 tailnet 地址向 control-plane 上报心跳。

由于当前 spot worker bootstrap 明确依赖 Tailscale：

- worker 节点使用 Tailscale IPv4 作为 `--node-ip`
- `flannel` 被强制绑定到 `tailscale0`
- `K3S_URL` 指向 control-plane 的 Tailscale 地址

因此一旦节点从 tailnet 掉线，即使 EC2 实例仍然存活，Kubernetes 视角中这台
worker 也会迅速变成 `NodeStatusUnknown -> NotReady -> unreachable taints`。

这次事故最终导致：

- `flashsales` 因 `node-purpose=worker` 约束失去唯一可用 worker
- 新 Pod 长时间 `Pending`
- 旧 Pod 卡在失联 node 上长期 `Terminating`
- 恢复需要人工介入确认是“实例死亡”还是“tailnet 掉线”

## 影响范围

- `flashsales` namespace：
  - `flashsales-user-service`
  - `flashsales-product-service`
  - `flashsales-order-service`
  - `flashsales-order-worker`
- worker 节点上的 DaemonSet / system pods：
  - `datadog-agent`
  - `grafana-k8s-monitoring-*`
  - `svclb-traefik-*`

## 用户可见现象

- `kubectl get nodes` 中唯一 worker 显示 `NotReady`
- `kubectl describe node` 中 node conditions 全部为 `Unknown`
- node 自动带上：
  - `node.kubernetes.io/unreachable:NoSchedule`
  - `node.kubernetes.io/unreachable:NoExecute`
- `flashsales` 新副本全部 `Pending`
- 旧副本继续停留在失联 worker 上，长时间 `Terminating`

## 证据

### 1. Worker 不是 EC2 消失，而是 Kubernetes 心跳中断

节点对象中显示：

- `Ready: Unknown`
- `MemoryPressure: Unknown`
- `DiskPressure: Unknown`
- `PIDPressure: Unknown`
- `message: Kubelet stopped posting node status.`

这说明不是 control-plane 主动删除节点，也不是 kubelet 正常上报了某个明确资源压力值，
而是 **kubelet / k3s-agent 心跳链路整体断掉了**。

### 2. Lease 最后续约时间说明失联是突发的

`kube-node-lease` 中该节点的最后续约时间约为：

- `renewTime: 2026-06-21T02:45:22Z`

之后 control-plane 不再收到新的 lease 更新，节点被转成 `unreachable`。

### 3. Spot worker bootstrap 对 Tailscale 是硬依赖

[terraform/k3s-spot-node/user-data.sh.tftpl](/home/jingyi/PycharmProjects/homelab-cloud/terraform/k3s-spot-node/user-data.sh.tftpl)
中，worker 在 `tailscale_enabled = true` 时会：

- 安装并启动 `tailscaled`
- 通过 `tailscale up` 入网
- 读取 `tailscale ip -4` 作为 `NODE_IP`
- 把 `flannel` 绑定到 `tailscale0`
- 让 `K3S_URL` 指向 tailnet control-plane URL

这意味着：

- tailnet 是 worker 加入集群的基础网络
- 一旦 Tailscale 掉线，`k3s-agent` 与 control-plane 的通信路径也随之失效

### 4. 调度错误与 worker 失联完全一致

`flashsales` 的 scheduling event 为：

- `0/2 nodes are available: 1 node(s) didn't match Pod's node affinity/selector, 1 node(s) had untolerated taint(s)`

解释如下：

- `srv1304323` 是 `control-plane`，不匹配 `node-purpose=worker`
- 唯一 worker 已经因为 `unreachable` taint 不可调度

### 5. 用户确认 worker 是从 Tailscale 中掉线

事故确认阶段，operator 明确观察到：

- EC2 instance 仍然是 `running`
- 但该 worker 已从 Tailscale 里掉线

这与 Kubernetes 侧看到的 `NodeStatusUnknown` 完全吻合。

## 时间线

### 事故前状态

- cluster 中只有一台正式 worker
- worker 通过 Tailscale 接入 control-plane
- `flashsales` 所有 workload 强制调度到 `node-purpose=worker`

### 事故发生

1. worker spot instance 仍然存活
2. worker 从 tailnet 掉线
3. `k3s-agent / kubelet` 无法继续通过 `K3S_URL=https://100.x.x.x:6443` 上报
4. node lease 停止续约
5. control-plane 将节点标记为 `NotReady` 并打上 `unreachable` taints
6. `flashsales` 因失去唯一 worker 而整体不可调度

## 根因

本次事故的直接根因是：

- **spot worker 对 Tailscale 网络存在单点依赖，而节点侧没有 tailnet 掉线后的自愈机制**

## 促成因素

### 1. 单 worker 架构导致 tailnet 掉线直接等价于业务容量归零

`flashsales` workload 的调度约束是正确的，但当前 worker 冗余不足，
导致单节点失联会直接放大成业务面故障。

### 2. 当前 ASG 只看 EC2 健康，不看 Tailscale / Kubernetes 健康

实例保持 `running` 时，ASG 不会感知“这台 worker 对集群已经不可用”。

### 3. bootstrap 只负责首次 join，不负责长期 tailnet 自愈

现有 `user-data.sh.tftpl` 只在开机时：

- `tailscale up`
- 启动 `k3s-agent`

但没有周期性检查：

- `tailscaled` 是否还活着
- 节点是否仍持有 Tailscale IP
- control-plane Tailscale peer 是否仍可达

### 4. `DiskPressure` 类故障与 `Tailscale dropout` 类故障在表象上都能导致 `NotReady`

之前集群确实多次受磁盘问题影响，因此容易先入为主地把这次也归因成磁盘。
但这次 node conditions 是 `Unknown` 而不是明确 `DiskPressure=True`，
真正问题更偏向网络/agent 心跳链路中断。

## 可以排除的方向

- 不是 `flashsales` 应用本身崩溃
- 不是 control-plane 节点故障
- 不是业务 Pod 调度规则写错
- 不是“节点已经被 terminate”导致的对象残留
- 不是本次故障窗口内 kubelet 明确上报 `DiskPressure=True`

## 修复

### 已实施修复

最终没有把 Tailscale watchdog 固化在
[terraform/k3s-spot-node/user-data.sh.tftpl](/home/jingyi/PycharmProjects/homelab-cloud/terraform/k3s-spot-node/user-data.sh.tftpl)
里，而是收敛到 `node-disk-janitor` 统一负责：

- 避免 bootstrap 脚本和 DaemonSet 同时做重启决策
- 让 node cleanup 和 node self-heal 由同一个 agent 统一执行
- 跟随应用发布一起滚动更新，后续维护更简单

`node-disk-janitor` 现在会检查：

- `tailscaled` 是否仍处于 active
- `tailscale ip -4` 是否仍能取到地址
- control-plane 的 Tailscale peer 是否仍可 `tailscale ping`
- `k3s-agent` 或 `k3s` 是否仍处于 active

在异常时会自动：

- 重启 `tailscaled`
- 重启对应的 `k3s-agent` / `k3s`

### 对应配置项

[charts/node-disk-janitor/values.yaml](/home/jingyi/PycharmProjects/homelab-cloud/charts/node-disk-janitor/values.yaml)
里新增：

- `TAILSCALE_SELF_HEAL_ENABLED`
- `SELF_HEAL_COOLDOWN_SECONDS`
- `TAILSCALE_PING_TIMEOUT_SECONDS`
- `TAILSCALE_PING_PEER`
- `RESTART_K3S_ON_TAILSCALE_HEAL`

## 建议的恢复路径

当未来再次出现类似现象时：

1. 先判断 EC2 是否仍然 `running`
2. 如果 EC2 仍在，但 node 是 `Ready=Unknown` / `unreachable`
   - 优先怀疑 `tailscaled` / `k3s-agent` / tailnet 路径
3. 若 watchdog 未能自愈，再决定：
   - 手动重启 `tailscaled`
   - 手动重启 `k3s-agent`
   - 或直接 terminate 让 ASG 补新节点

## 后续改进建议

1. 给 worker 增加第二个冗余节点，避免单点 tailnet 故障直接影响业务
2. 在监控中区分：
   - `DiskPressure` 类节点故障
   - `NodeStatusUnknown / unreachable` 类节点故障
3. 为 ASG 增加更贴近 Kubernetes / tailnet 可用性的 replace 信号
4. 为 tailnet dropout 建立独立 runbook，而不是并入 disk cleanup runbook
