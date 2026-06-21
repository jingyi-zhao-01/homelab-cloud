---
name: home-cloud-backend-rules
description: Use when editing backend, worker, queue, database, Redis, or infra-facing application code in this repo. Favor explicit, searchable, low-magic code that keeps responsibilities separated.
---

# Home Cloud Backend Rules

## Default Style

Prefer explicit code over clever abstraction.

Optimize for:

- easy to trace
- easy to search
- easy to test
- easy for the next agent or human to change

Avoid:

- service locators
- dynamic dispatch by string
- hidden globals
- vague shared helpers
- producer/worker/controller/repository logic mixed in one file

## Dependency Shape

Prefer this flow:

    route -> controller -> usecase -> repository / adapter / producer

Rules:

- Controllers parse input, call one use case, and map result to response.
- Use cases own business workflow and do not know HTTP status codes.
- Repositories own DB access and transactions.
- Adapters own external API calls.
- Producers enqueue jobs.
- Workers consume jobs and must be idempotent.

## Boundaries

- Keep changes inside the smallest relevant feature boundary.
- One use case per file when practical.
- One worker per file when practical.
- Keep files and functions small enough to scan quickly.
- Do not create a new abstraction unless it removes real duplication or confusion.

## Data Rules

- Redis is for cache, rate limit, locks, queue state, and short-lived coordination.
- Redis is not the durable source of truth.
- Durable business state belongs in the database.
- Use atomic Redis operations when correctness depends on it.

## Naming

Prefer direct names such as:

- `createOrderUseCase`
- `orderRepository.create`
- `paymentAdapter.authorize`
- `renderJobProducer.enqueue`
- `renderJobWorker`

Avoid vague names such as:

- `handle`
- `process`
- `manager`
- `helper`
- `utils`
- `service`
- `common`

## Observability

For every changed request path or worker path, make sure logs/errors are clear.

Include when relevant:

- request ID or job ID
- operation name
- tenant or user identifier
- duration
- success or failure
- concrete failure reason

## Testing

For changed behavior:

- add or update the nearest test
- test DB behavior when repository logic changes
- test retry/idempotency behavior when worker logic changes
- test HTTP mapping when controller behavior changes

## Final Check

Before finishing, verify:

- dependency direction is still clean
- DB access stayed in repositories
- external calls stayed in adapters
- workers remain idempotent
- logs and errors are understandable
- tests cover the behavior change
