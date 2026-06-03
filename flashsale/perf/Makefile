.PHONY: loadtest loadtest-lite loadtest-lite-idempotency loadtest-high-safe concurrency-smoke concurrency-idempotency-lite concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot

# Shared wrapper and scenario entrypoints used by the perf targets below.
LOADTEST_WRAPPER := bash ./flashsale/perf/scripts/loadtest-k6.sh
CONCURRENCY_SCENARIO := ./flashsale/perf/k6/scenarios/concurrency-test.js
IDEMPOTENCY_SCENARIO := ./flashsale/perf/k6/scenarios/loadtest-lite-idempotency.js

define run_loadtest
LOADTEST_SCRIPT=$(1) $(LOADTEST_WRAPPER) $(2)
endef

# Default thresholds can still be overridden from the CLI or CI environment.
K6_P50_THRESHOLD_MS ?= 800
K6_P90_THRESHOLD_MS ?= 1200
K6_P95_THRESHOLD_MS ?= 1500
K6_P99_THRESHOLD_MS ?= 500
MAX_5XX_RATE ?= 0

# Legacy aliases kept for convenience; these map to the named concurrency profiles.
loadtest:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=baseline)

loadtest-lite:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=smoke -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=200 -e K6_P99_THRESHOLD_MS=500 -e MAX_5XX_RATE=0)

loadtest-lite-idempotency:
>$(call run_loadtest,$(IDEMPOTENCY_SCENARIO),-e K6_P50_THRESHOLD_MS=1000 -e K6_P90_THRESHOLD_MS=1500 -e K6_P95_THRESHOLD_MS=2000)

loadtest-high-safe:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=stress100 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=1200 -e MAX_5XX_RATE=0.02)

# Profile-specific perf lanes used by CI and manual runs.
concurrency-smoke:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=smoke -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=200 -e K6_P99_THRESHOLD_MS=500 -e MAX_5XX_RATE=0)

concurrency-idempotency-lite:
>$(call run_loadtest,$(IDEMPOTENCY_SCENARIO),-e K6_P50_THRESHOLD_MS=1000 -e K6_P90_THRESHOLD_MS=1500 -e K6_P95_THRESHOLD_MS=2000)

concurrency-baseline:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=baseline -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=300 -e K6_P99_THRESHOLD_MS=800 -e MAX_5XX_RATE=0.01)

concurrency-stress100:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=stress100 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=1200 -e MAX_5XX_RATE=0.02)

concurrency-stress200:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=stress200 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=2000 -e MAX_5XX_RATE=0.02)

concurrency-hotspot:
>$(call run_loadtest,$(CONCURRENCY_SCENARIO),-e PROFILE=hotspot -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=2000 -e MAX_5XX_RATE=0.01)
