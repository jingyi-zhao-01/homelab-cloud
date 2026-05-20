.PHONY: loadtest loadtest-lite loadtest-high-safe

K6_P50_THRESHOLD_MS ?= 800
K6_P90_THRESHOLD_MS ?= 1200
K6_P95_THRESHOLD_MS ?= 1500

loadtest:
>LOADTEST_SCRIPT=./perf/loadtest.js bash ./perf/loadtest-k6.sh -e K6_P50_THRESHOLD_MS=$(K6_P50_THRESHOLD_MS) -e K6_P90_THRESHOLD_MS=$(K6_P90_THRESHOLD_MS) -e K6_P95_THRESHOLD_MS=$(K6_P95_THRESHOLD_MS)

loadtest-lite:
>LOADTEST_SCRIPT=./perf/loadtest-lite.js bash ./perf/loadtest-k6.sh -e K6_P50_THRESHOLD_MS=$(K6_P50_THRESHOLD_MS) -e K6_P90_THRESHOLD_MS=$(K6_P90_THRESHOLD_MS) -e K6_P95_THRESHOLD_MS=$(K6_P95_THRESHOLD_MS)

loadtest-high-safe:
>LOADTEST_SCRIPT=./perf/loadtest-high.js bash ./perf/loadtest-k6.sh -e K6_P50_THRESHOLD_MS=$(K6_P50_THRESHOLD_MS) -e K6_P90_THRESHOLD_MS=$(K6_P90_THRESHOLD_MS) -e K6_P95_THRESHOLD_MS=$(K6_P95_THRESHOLD_MS)