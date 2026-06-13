#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $(basename "$0") <chart-directory>" >&2
  exit 1
fi

CHART_DIR="$1"

if [ ! -d "$CHART_DIR" ]; then
  echo "Chart directory does not exist: $CHART_DIR" >&2
  exit 1
fi

CLEAN_LOCK=0
CLEAN_DEPENDENCY_DIR=0

cleanup() {
  if [ "${CLEAN_LOCK}" = "1" ]; then
    rm -f "$CHART_DIR/Chart.lock"
  fi

  if [ "${CLEAN_DEPENDENCY_DIR}" = "1" ]; then
    rm -rf "$CHART_DIR/charts"
  fi
}

trap cleanup EXIT

if [ -f "$CHART_DIR/Chart.lock" ]; then
  CLEAN_LOCK=0
else
  CLEAN_LOCK=1
fi

if [ -d "$CHART_DIR/charts" ]; then
  CLEAN_DEPENDENCY_DIR=0
else
  CLEAN_DEPENDENCY_DIR=1
fi

helm dependency update "$CHART_DIR"
helm lint "$CHART_DIR"
