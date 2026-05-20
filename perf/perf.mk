.PHONY: loadtest loadtest-lite loadtest-high-safe concurrency-smoke concurrency-baseline concurrency-stress100 concurrency-stress200 concurrency-hotspot

K6_P50_THRESHOLD_MS ?= 800
K6_P90_THRESHOLD_MS ?= 1200
K6_P95_THRESHOLD_MS ?= 1500
K6_P99_THRESHOLD_MS ?= 500
MAX_5XX_RATE ?= 0

loadtest:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=baseline

loadtest-lite:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=smoke -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=200 -e K6_P99_THRESHOLD_MS=500 -e MAX_5XX_RATE=0

loadtest-high-safe:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=stress100 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=1200 -e MAX_5XX_RATE=0.02

concurrency-smoke:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=smoke -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=200 -e K6_P99_THRESHOLD_MS=500 -e MAX_5XX_RATE=0

concurrency-baseline:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=baseline -e K6_P50_THRESHOLD_MS=100 -e K6_P90_THRESHOLD_MS=300 -e K6_P99_THRESHOLD_MS=800 -e MAX_5XX_RATE=0.01

concurrency-stress100:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=stress100 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=1200 -e MAX_5XX_RATE=0.02

concurrency-stress200:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=stress200 -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=2000 -e MAX_5XX_RATE=0.02

concurrency-hotspot:
>LOADTEST_SCRIPT=./perf/concurrency-test.js bash ./perf/loadtest-k6.sh -e PROFILE=hotspot -e K6_P50_THRESHOLD_MS=150 -e K6_P90_THRESHOLD_MS=500 -e K6_P99_THRESHOLD_MS=2000 -e MAX_5XX_RATE=0.01