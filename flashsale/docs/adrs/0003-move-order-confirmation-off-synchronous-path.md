# ADR 0003：将 `/orders` 的确认步骤移出同步请求路径

- 状态：Accepted
- 日期：2026-06-04

## 背景

在 `order-service` 的 `POST /orders` trace 中，请求链路依次包含：

1. `validate user`
2. `reserve inventory`
3. `persist order`
4. `enqueue terminalization`

在修复前，第 4 步并不只是“写一条 task”，而是同步等待 `confirm / cancel` 的终态处理完成。也就是说，`/orders` 会一直阻塞到 `product-service` 的终态调用结束，再把订单写到最终状态后才返回。

这会带来几个直接问题：

- trace 链路很长，用户请求必须等待多个串行依赖完成
- `product-service` 的 reservation terminalization 会放大尾延迟
- `order-service` 自己的订单落库和终态更新之间，没有把“业务意图”与“后台执行”拆开
- 一旦终态处理慢，前台请求就会把慢点全部背到自己身上

本次 trace 的现象就是这个问题的直接表现：

- `user-service lookup` 约 1.2s
- `product-service reserve` 约 1.6s
- `order db create` 约 1.2s
- 终态确认段还会继续拉长请求尾部

## 决策

我们将 `POST /orders` 的确认步骤改成异步终态处理。

### 新流程

1. `order-service` 校验用户
2. `order-service` 预留库存
3. `order-service` 在同一个数据库边界内创建 `pending` 订单，并 durable 地写入 terminalization task
4. `POST /orders` 立即返回，不再等待 `confirm / cancel`
5. 后台 worker 处理 terminalization task
6. worker 在 `confirm` 成功后把订单推进到 `confirmed / succeeded`

### 具体实现

- `CreateOrderUseCase.create_order()` 不再同步调用 `finalize_order()`
- 新增 `create_order_and_enqueue_terminalization()`，把订单创建和 task 入队放进同一事务边界
- `ProcessTerminalizationTaskUseCase` 在 `confirm` 成功后回写订单状态
- `cancel` 类型 task 只负责终结 reservation，不再回写已经由其他路径决定好的订单终态

## 为什么这样能缩短 trace

修复前，`/orders` 路径必须等待：

- 商品预留
- 订单写入
- 订单终态确认
- 终态确认完成后的订单状态回写

修复后，`/orders` 只需要等待：

- 用户校验
- 商品预留
- 订单写入
- durable enqueue

也就是说，最重的同步尾段从请求路径里消失了。请求依然要等待 user lookup 和 reserve inventory，但不再背负终态处理的额外延迟。

## 影响

预期收益：

- `/orders` 的 p95/p99 延迟下降
- trace 链路更短，更容易区分“下单本身慢”与“后台终态处理慢”
- 终态处理失败可以通过 worker 重试，而不会阻塞前台请求
- 订单最终状态和 reservation 终态的边界更清晰

代价与权衡：

- `POST /orders` 的响应语义从“立即 confirmed”变成“先返回 pending，再由 worker 推进到 confirmed”
- 上层调用方如果关心最终状态，需要通过 `GET /orders/{id}` 或后续事件来观察
- worker 和 queue 的健康度变成必须关注的运营指标

## 观测与运维

这次改动后，Grafana 至少要关注三类信号：

- `event=order_service_create_order_timing`
- `event=order_service_enqueue_task`
- `event=order_service_terminalization_call`

如果 `order_service_create_order_timing` 下降，而 `order_service_terminalization_call` 仍然抖动，说明前台路径已经被切短，但后台终态消费还在落后。

## 相关变更

- `flashsale/order-service/app/application/create_order_use_case.py`
- `flashsale/order-service/app/application/process_terminalization_task_use_case.py`
- `flashsale/order-service/app/adapters/order_postgres_unit_of_work.py`
- `flashsale/order-service/app/entrypoints/http_api.py`
- `flashsale/order-service/tests/unit/test_order_lifecycle.py`
- `flashsale/order-service/tests/interagtion/order_compose_integration.py`
- `flashsale/scripts/integration_test_support.py`
