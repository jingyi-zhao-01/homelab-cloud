#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: resolve-ssm-key-map.sh --ssm-keys-file <file> --namespace-prefix <prefix> --github-env <path>

Optional:
  --marker-key <yaml_key>   Default: vercelClient
  --marker-value <value>    Default: true
  --mappings-var <name>     Default: VERCEL_SSM_MAPPINGS
  --env-vars-var <name>     Default: VERCEL_ENV_VARS
EOF
}

SSM_KEYS_FILE=""
NAMESPACE_PREFIX=""
MARKER_KEY="vercelClient"
MARKER_VALUE="true"
MAPPINGS_GITHUB_VAR="VERCEL_SSM_MAPPINGS"
ENV_VARS_GITHUB_VAR="VERCEL_ENV_VARS"
GITHUB_ENV_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssm-keys-file)
      SSM_KEYS_FILE="${2:?missing value for --ssm-keys-file}"
      shift 2
      ;;
    --namespace-prefix)
      NAMESPACE_PREFIX="${2:?missing value for --namespace-prefix}"
      shift 2
      ;;
    --marker-key)
      MARKER_KEY="${2:?missing value for --marker-key}"
      shift 2
      ;;
    --marker-value)
      MARKER_VALUE="${2:?missing value for --marker-value}"
      shift 2
      ;;
    --mappings-var)
      MAPPINGS_GITHUB_VAR="${2:?missing value for --mappings-var}"
      shift 2
      ;;
    --env-vars-var)
      ENV_VARS_GITHUB_VAR="${2:?missing value for --env-vars-var}"
      shift 2
      ;;
    --github-env)
      GITHUB_ENV_FILE="${2:?missing value for --github-env}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$SSM_KEYS_FILE" ]; then
  echo "Missing required --ssm-keys-file" >&2
  exit 1
fi

if [ -z "$NAMESPACE_PREFIX" ]; then
  echo "Missing required --namespace-prefix" >&2
  exit 1
fi

if [ ! -f "$SSM_KEYS_FILE" ]; then
  echo "SSM key file not found: $SSM_KEYS_FILE" >&2
  exit 1
fi

if [ -z "$GITHUB_ENV_FILE" ]; then
  echo "Missing required --github-env" >&2
  exit 1
fi

if [ ! -w "$GITHUB_ENV_FILE" ]; then
  echo "GITHUB_ENV path is not writable: $GITHUB_ENV_FILE" >&2
  exit 1
fi

raw_mappings="$(
  awk -v marker_key="$MARKER_KEY" -v marker_value="$MARKER_VALUE" '
    /^[A-Za-z0-9_]+:[[:space:]]*$/ {
      if (in_block && mark_for_selector && key != "" && path != "") {
        print key "=" path
      }
      key=substr($0, 1, index($0, ":") - 1)
      path=""
      mark_for_selector=0
      in_block=1
      next
    }
    in_block && /^[[:space:]]*path:[[:space:]]*/ {
      sub(/^[[:space:]]*path:[[:space:]]*/, "", $0)
      path=$0
      gsub(/^"/, "", path)
      gsub(/"$/, "", path)
      next
    }
    in_block && $0 ~ "^[[:space:]]*" marker_key ":[[:space:]]*" marker_value "[[:space:]]*$" {
      mark_for_selector=1
      next
    }
    in_block && /^[[:space:]]*[A-Za-z0-9_]+:[[:space:]]*$/ {
      if (mark_for_selector && key != "" && path != "") {
        print key "=" path
      }
      in_block=0
      key=""
      path=""
      mark_for_selector=0
      next
    }
    END {
      if (in_block && mark_for_selector && key != "" && path != "") {
        print key "=" path
      }
    }
  ' "$SSM_KEYS_FILE"
)"

if [ -z "$raw_mappings" ]; then
  echo "No entries matched selector $MARKER_KEY=$MARKER_VALUE in $SSM_KEYS_FILE" >&2
  exit 1
fi

resolved_pairs=()
env_names=()

while IFS='=' read -r logical_name default_path; do
  if [ -z "$logical_name" ] || [ -z "$default_path" ]; then
    continue
  fi

  override_var="${NAMESPACE_PREFIX}_${logical_name}_SSM_NAME"
  resolved_path="${!override_var:-$default_path}"

  if [ -z "$resolved_path" ]; then
    echo "No parameter source resolved for $logical_name" >&2
    exit 1
  fi

  resolved_pairs+=("${logical_name}=${resolved_path}")
  env_names+=("${logical_name}")
done <<< "$raw_mappings"

if [ "${#resolved_pairs[@]}" -eq 0 ]; then
  echo "No valid SSM mappings could be resolved from $SSM_KEYS_FILE" >&2
  exit 1
fi

{
  echo "${MAPPINGS_GITHUB_VAR}<<EOF"
  printf '%s\n' "${resolved_pairs[@]}"
  echo "EOF"
} >> "$GITHUB_ENV_FILE"

{
  echo "${ENV_VARS_GITHUB_VAR}<<EOF"
  printf '%s\n' "${env_names[@]}"
  echo "EOF"
} >> "$GITHUB_ENV_FILE"
