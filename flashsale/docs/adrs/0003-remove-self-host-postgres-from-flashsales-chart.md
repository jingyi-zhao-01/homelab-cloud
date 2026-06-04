# ADR 0003：从 Flashsales Chart 中移除自托管 Postgres

- 状态：Accepted
- 日期：2026-06-04

## 背景

Flashsales 的 chart 最初同时承担了两类职责：

1. 管理应用 Deployment / Service
2. 额外渲染一个自托管 PostgreSQL 资源组，供三套服务作为数据库后端使用

随着平台演进，这个设计开始暴露出几个问题：

- self-host Postgres 和外部数据库凭证混在同一个 chart 里，语义不清晰
- Helm upgrade 会尝试管理一个历史遗留的 `flashsales-postgres-auth` Secret，容易与集群中已有的外部凭证冲突
- 当前平台已经切到外部数据库供应商提供的 PostgreSQL 兼容实例，不再需要 chart 自己再创建数据库 StatefulSet
- self-host 资源和外部凭证并存时，values、templates、部署名和运维文档都会出现重复和歧义

换句话说，chart 里保留 self-host Postgres，不再是“多一个可选项”，而是在继续制造迁移歧义。

## 决策

我们将从 `charts/flashsales` 中移除自托管 Postgres 相关资源，只保留“消费外部数据库凭证”的路径。

### 具体变更

- 删除 self-host Postgres 的模板
  - `postgres-secret.yaml`
  - `postgres-service.yaml`
  - `postgres-statefulset.yaml`
- 将数据库凭证的 chart 语义改为中性命名：
  - `flashsales-postgres-auth` -> `flashsales-db-auth`
  - ExternalSecret 模板改名为 `external-secret-db.yaml`
- 三个服务和 `db-proxy` 不再硬编码 secret 名称，而是统一通过 helper 读取数据库凭证 secret

### 为什么不继续保留 self-host Postgres

保留它会带来几个坏处：

1. 会让部署语义分裂
   同一个 chart 同时像是在“部署应用”和“部署数据库”，而实际上数据库已经由外部系统接管。

2. 会继续制造 Helm ownership 冲突
   历史遗留 Secret 很容易和 Helm release 的期望状态不一致，导致 upgrade 失败。

3. 会干扰排障和文档阅读
   看到 `postgres` 的名字，容易误以为平台仍然依赖自托管数据库，但事实上已经不是。

4. 会增加未来迁移成本
   每一次改数据库后端，都要先分辨哪些 `postgres` 相关配置是真的需要，哪些只是历史包袱。

## 影响

预期收益：

- chart 语义更清晰，只负责应用和外部数据库接入
- Helm upgrade 不再尝试创建自托管 Postgres 资源
- secret 命名与实际架构一致，降低误解和冲突概率
- 运维和文档更容易统一到“外部数据库”模型

代价与权衡：

- 不能再通过这个 chart 一键拉起自托管数据库
- 如果将来要回到自托管 Postgres，必须显式重新引入新模板，而不是依赖旧配置残留

## 迁移说明

如果集群里还存在旧的 `flashsales-postgres-auth` Secret，需要在升级前或升级后按实际情况迁移为新的 `flashsales-db-auth` 名称，避免 Deployment 因 secret 名称变化而短暂报错。

建议迁移顺序：

1. 先把外部 Secret / ExternalSecret 的目标名称切到 `flashsales-db-auth`
2. 再更新 chart release
3. 最后清理旧的 `flashsales-postgres-auth` 名称引用

## 为什么这份 ADR 存在

这份 ADR 记录的不是“换个名字”这么简单，而是一次架构边界收缩：

- database provisioning 不再属于 Flashsales chart 的职责
- chart 只保留对数据库凭证的消费
- 应用层继续通过 `DATABASE_URL` 工作，不需要感知底层是 Neon、RDS 还是别的 PostgreSQL 兼容后端

## 相关变更

- `charts/flashsales/values.yaml`
- `charts/flashsales/templates/_helpers.tpl`
- `charts/flashsales/templates/external-secret-db.yaml`
- `charts/flashsales/templates/user-deployment.yaml`
- `charts/flashsales/templates/product-deployment.yaml`
- `charts/flashsales/templates/order-deployment.yaml`
- `charts/flashsales/templates/db-proxy-deployment.yaml`
