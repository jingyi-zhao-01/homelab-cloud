# K3s Worker Capacity 事故 RCA（2026-06-08）

## 摘要

`2026-06-08`，本地 `archlinux` 主机上的 `k3s-agent` 意外重新加入 `homelab` k3s 集群，成为一个未被明确纳入容量计划的额外 worker 候选节点。该节点本地磁盘容量不足，加入后很快出现 `DiskPressure`，随后进入 `NotReady`。

与此同时，原本承载 `flashsales` workload 的 AWS spot worker `ip-10-44-2-116-7c47b13c` 也处于 `NotReady`。由于 `flashsales` Helm chart 明确要求所有业务 Pod 调度到 `node-purpose=worker` 节点，而当时集群里没有任何 `Ready` 的 worker，最终导致：

- `flashsales` 新副本无法调度，长期 `Pending`
- 旧副本卡在失联 worker 上，长期 `Terminating`
- 需要人工清理 `archlinux` 节点、人工处理 spot worker 替换 / 重新 provision，恢复流程繁琐且依赖人工判断

这次事故的关键不是“`flashsales` 业务 Pod 大量正常运行在 `archlinux` 上”，而是：

1. `archlinux` 不应加入集群，却因为本地 `k3s-agent` 存在而重新注册
2. 集群级 DaemonSet / ServiceLB Pod 会自动落到所有 Linux node，上线后放大了 `archlinux` 的磁盘压力
3. spot worker `NotReady` 后，`flashsales` 丧失唯一符合约束的可用 worker 容量
4. 当前 spot worker 的 AWS Auto Scaling Group 只看 `EC2` 健康，不看 Kubernetes `Ready`，因此不能自动替换“实例还活着但 node 已失联”的 worker

## 影响范围

- `flashsales` namespace 业务服务中断或不可用：
  - `flashsales-user-service`
  - `flashsales-product-service`
  - `flashsales-order-service`
  - `flashsales-order-worker`
- 集群监控相关的部分 DaemonSet Pod 也受到 `archlinux` 节点异常影响
- 恢复依赖人工：
  - 删除 / 阻止 `archlinux` 再次 join
  - 终止异常 spot worker
  - 重新 provision 新的 spot worker

## 用户可见现象

- `flashsales` 新 Pod 长时间处于 `Pending`
- 原来运行在 spot worker 上的 `flashsales` Pod 长时间处于 `Terminating`
- `kubectl get nodes` 同时出现多个 `NotReady` 节点
- `archlinux` 节点在删除后又会重新出现 / 重新 join

## 证据

### 1. `flashsales` 明确要求运行在 worker 节点

[charts/flashsales/values.yaml](/home/jingyi/PycharmProjects/homelab-cloud/charts/flashsales/values.yaml) 为 `user-service`、`product-service`、`order-service` 和 `order-worker` 都设置了：

```yaml
nodeSelector:
  node-purpose: worker
```

这意味着 `srv1304323` 这类 control-plane 节点默认不会承接 `flashsales` 业务 Pod。

### 2. spot worker 是唯一计划内 worker，但当时处于 `NotReady`

事故排查时集群节点状态为：

- `srv1304323`: `Ready`, `control-plane`
- `ip-10-44-2-116-7c47b13c`: `NotReady`
- `archlinux`: 加入后又因磁盘与节点状态问题进入异常

因此对 `flashsales` 来说，当时没有任何 `Ready` 的 `node-purpose=worker` 节点可用。

### 3. Scheduler 的报错说明是“无可用 worker”，不是业务 Pod 自己崩溃

事故窗口内 `flashsales` 的 scheduling event 为：

- `0/3 nodes are available: 1 node(s) didn't match Pod's node affinity/selector, 2 node(s) had untolerated taint(s)`

这和当前调度约束完全一致：

- `srv1304323` 不匹配 `node-purpose=worker`
- `archlinux` / `ip-10-44-2-116-7c47b13c` 均不可用或带有 `unreachable` taint

### 4. `archlinux` 确实存在本地 `k3s-agent`，join 是本机行为，不是 Terraform 重复创建

本机 systemd 中存在：

- `/etc/systemd/system/k3s-agent.service`

日志中明确出现：

- 连接控制面：`wss://100.92.165.80:6443/v1-k3s/connect`
- 注册节点：`Successfully registered node "archlinux"`

这说明 `archlinux` 加入集群的直接原因是本机 `k3s-agent` 被启动，而不是 GitHub Actions 或 Terraform 在 AWS 上“创建了一个叫 archlinux 的 worker”。

### 5. `archlinux` 的磁盘压力导致节点很快失稳

节点与事件日志中可见：

- `DiskPressure`
- `FreeDiskSpaceFailed`
- `NodeNotReady`

同时 `archlinux` 上的 K3s 日志出现：

- `Eviction manager: must evict pod(s) to reclaim resourceName="ephemeral-storage"`
- `Eviction manager: cannot evict a critical pod`

说明该节点加入后承接了集群级 Pod，但本地磁盘容量无法支撑。

### 6. 集群级 DaemonSet / ServiceLB 会自动落到任何 Linux node

当前集群中以下资源没有 `node-purpose=worker` 约束：

- `grafana-k8s-monitoring-alloy-logs` DaemonSet
- `grafana-k8s-monitoring-kepler` DaemonSet
- `grafana-k8s-monitoring-node-exporter` DaemonSet
- `svclb-traefik-*` DaemonSet

它们的 node selector 主要是：

- `kubernetes.io/os=linux`
- 或完全无约束

因此，只要 `archlinux` join，系统级 Pod 就会自动被调度到该节点。

### 7. spot worker 当前的自动修复边界有限

[terraform/k3s-spot-node/main.tf](/home/jingyi/PycharmProjects/homelab-cloud/terraform/k3s-spot-node/main.tf) 中，spot worker 由：

- `aws_autoscaling_group`
- `health_check_type = "EC2"`
- `min=1`, `desired=1`, `max=1`

维护。

这意味着：

- 如果 EC2 实例真正消失或 EC2 health check 失败，ASG 会补新实例
- 但如果实例还活着，只是 `k3s-agent` / kubelet / 网络失联，Kubernetes node 可能长期 `NotReady`，而 ASG 不会自动替换它

这正是本次人工 terminate + reprovision 必须发生的关键原因之一。

## 时间线

### 事故前状态

- `flashsales` workload 被设计为只运行在 dedicated worker 上
- AWS spot worker `ip-10-44-2-116-7c47b13c` 是主要业务 worker
- `archlinux` 并不在原始容量规划中

### 事故发生

1. `archlinux` 上本地 `k3s-agent` 被启动
2. `archlinux` 注册进集群并开始承接系统级 DaemonSet / ServiceLB Pod
3. `archlinux` 本地容量不足，触发 `DiskPressure`
4. `archlinux` 节点进入 `NotReady`
5. 同期 AWS spot worker 也处于 `NotReady`
6. `flashsales` 新 Pod 无处可调度，旧 Pod 卡在失联 worker 上

### 事故处置

1. 人工调查发现 `archlinux` 是本地 agent 自动 join
2. 人工删除 `archlinux` node，并准备阻止其再次 join
3. 人工评估并处理异常 spot worker
4. 通过手动 terminate / reprovision spot worker 恢复 worker 容量

## 根因

本次事故的主根因是：

- `archlinux` 上存在并被启动的本地 `k3s-agent`，导致未纳入正式容量设计的本机节点意外加入生产集群

## 促成因素

### 1. `archlinux` 没有被默认隔离

当前没有机制保证“本地实验节点即使误 join，也不会立刻承接生产流量或系统级 Pod”。只要 agent 启动，节点就会进入普通调度面。

### 2. 集群级 DaemonSet 默认会落到所有 Linux node

即使业务 Pod 本身没有落到 `archlinux`，系统级 DaemonSet 和 `svclb-traefik` 仍然会自动落上去，放大本机容量不足问题。

### 3. `flashsales` 对 worker 的约束正确但过于脆弱

`flashsales` 正确地限制了自己只跑在 worker 上，但当时没有第二个健康 worker 作为冗余，因此单个 worker 失联后，业务完全丧失可调度目标。

### 4. ASG 只感知 EC2 健康，不感知 Kubernetes `Ready`

实例还在、node 已失联时，ASG 不会自动替换，导致“基础设施看似存在，Kubernetes 实际不可用”的灰色故障需要人工介入。

### 5. 恢复流程依赖 operator 手动判断

当前恢复链路大致是：

- 判断 node 是否应该存在
- 删除异常 node
- 判断 spot worker 是否应 terminate
- 重新 provision / 等待 ASG

缺少自动化 runbook 和健康护栏，导致恢复过程复杂、容易重复劳动。

## 可以排除的方向

- 不是 Terraform 在 AWS 上创建了一个名为 `archlinux` 的新 spot instance
- 不是 `flashsales` 业务容器自身 crash 导致的主故障
- 不是 `flashsales` chart 忘记加 worker selector

## 修复与改进建议

### 立即修复

1. 在 `archlinux` 上停用本地 `k3s-agent`
   - `systemctl stop k3s-agent`
   - `systemctl disable k3s-agent`
   - `systemctl mask k3s-agent`
   - 如无保留需求，直接执行卸载

2. 清理 `archlinux` 的 cluster membership
   - 删除 node 对象
   - 确认其不会再次自动注册

3. 对异常 spot worker 采用更短恢复路径
   - 若实例仍存在但 node 长期 `NotReady`，直接 terminate 实例，让 ASG 重新补一台

### 中期改进

1. 给“非正式 worker”增加默认隔离策略
   - 例如本地 agent 默认带 taint
   - 或者通过 admission / label policy 限制未授权 node 进入业务调度面

2. 收紧 cluster-level DaemonSet 的落点
   - 对 Alloy / node-exporter / kepler / svclb 重新评估是否应无条件覆盖所有 Linux node
   - 对实验节点或本地主机增加排除规则

3. 为 worker 容量建立冗余
   - 至少保证 `flashsales` 不是单 worker 容量点

4. 将 spot worker 健康判断从“仅 EC2”提升到“包含 Kubernetes node readiness”
   - 即使最终仍保留 ASG，也应增加外部健康检测或自动 replace 机制

5. 建立 runbook
   - 如何识别“本地节点误 join”
   - 如何安全 terminate spot worker 而不破坏 Terraform 期望状态
   - 如何在 GitHub Actions / Terraform apply 后验证 worker 真正 `Ready`

### 长期改进

1. 明确区分“生产 cluster node”和“本地实验节点”
2. 把 worker replacement 自动化为标准恢复动作
3. 把 node 级容量 / disk pressure 告警前置，而不是等到业务 Pod `Pending`

## 当前状态

- RCA 创建时间：`2026-06-08`
- 当前文档聚焦平台层 root cause 和恢复成本，不包含应用代码修复
- 后续建议补一份对应 runbook，覆盖：
  - 本地 `k3s-agent` 清理
  - spot worker replace 流程
  - worker `Ready` 验证步骤
