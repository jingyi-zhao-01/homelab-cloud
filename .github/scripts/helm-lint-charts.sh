#!/usr/bin/env bash
set -euo pipefail

CHART_ROOT="charts"

if [ ! -d "$CHART_ROOT" ]; then
  echo "Chart directory does not exist: $CHART_ROOT" >&2
  exit 1
fi

selected_charts=()

is_application_chart() {
  local chart_dir="$1"
  local chart_yaml="$chart_dir/Chart.yaml"

  [ -f "$chart_yaml" ] || return 1
  # Exclude shared/library charts from linting here.
  grep -q "^type: library" "$chart_yaml" && return 1
  return 0
}

lint_chart() {
  local chart_dir="$1"

  if [ ! -d "$chart_dir" ]; then
    echo "Chart directory does not exist: $chart_dir" >&2
    return 1
  fi

  local clean_lock=0
  local clean_dependency_dir=0
  local chart_name

  chart_name="$(basename "$chart_dir")"

  cleanup_chart() {
    if [ "$clean_lock" = "1" ]; then
      rm -f "$chart_dir/Chart.lock"
    fi

    if [ "$clean_dependency_dir" = "1" ]; then
      rm -rf "$chart_dir/charts"
    fi
  }

  trap cleanup_chart RETURN

  if [ -f "$chart_dir/Chart.lock" ]; then
    clean_lock=0
  else
    clean_lock=1
  fi

  if [ -d "$chart_dir/charts" ]; then
    clean_dependency_dir=0
  else
    clean_dependency_dir=1
  fi

  echo "Helm Lint - $chart_name"
  helm dependency update "$chart_dir"
  helm lint "$chart_dir"
}

mark_chart_from_path() {
  local path="$1"
  path="${path#./}"
  if [[ "$path" == charts/* ]]; then
    local chart_name
    chart_name="$(echo "$path" | cut -d/ -f2)"
    local chart_dir="$CHART_ROOT/$chart_name"
    if is_application_chart "$chart_dir"; then
      for existing_chart in "${selected_charts[@]:-}"; do
        [ "$existing_chart" = "$chart_name" ] && return
      done
      selected_charts+=("$chart_name")
    fi
  fi
}

for changed_file in "$@"; do
  mark_chart_from_path "$changed_file"
done

if [ "${#selected_charts[@]}" -eq 0 ]; then
  while IFS= read -r chart_dir; do
    chart_name="$(basename "$chart_dir")"
    if is_application_chart "$chart_dir"; then
      selected_charts+=("$chart_name")
    fi
  done < <(find "$CHART_ROOT" -mindepth 1 -maxdepth 1 -type d)
fi

if [ "${#selected_charts[@]}" -eq 0 ]; then
  echo "No application charts found under $CHART_ROOT"
  exit 0
fi

while IFS= read -r chart_name; do
  lint_chart "$CHART_ROOT/$chart_name"
done < <(printf '%s\n' "${selected_charts[@]}" | sort -u)
