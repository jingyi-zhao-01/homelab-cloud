#!/usr/bin/env bash
set -euo pipefail

if [ -z "${AWS_REGION:-}" ]; then
  echo "AWS_REGION is required" >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  echo "At least one VAR=SSM_PARAMETER mapping is required" >&2
  exit 1
fi

fetch_ssm() {
  local logical_name="$1"
  local parameter_name="$2"
  local value

  if ! value="$(
    aws ssm get-parameter \
      --name "$parameter_name" \
      --with-decryption \
      --query 'Parameter.Value' \
      --output text \
      --region "$AWS_REGION"
  )"; then
    echo "Failed to resolve $logical_name from SSM parameter $parameter_name" >&2
    exit 1
  fi

  if [ -z "$value" ] || [ "$value" = "None" ]; then
    echo "Resolved empty value for $logical_name from SSM parameter $parameter_name" >&2
    exit 1
  fi

  printf '%s\n' "$value"
}

for mapping in "$@"; do
  var_name="${mapping%%=*}"
  parameter_name="${mapping#*=}"

  if [ -z "$var_name" ] || [ -z "$parameter_name" ] || [ "$var_name" = "$parameter_name" ]; then
    echo "Invalid mapping: $mapping" >&2
    exit 1
  fi

  value="$(fetch_ssm "$var_name" "$parameter_name")"
  echo "::add-mask::$value"

  if [ -n "${GITHUB_ENV:-}" ]; then
    printf '%s=%s\n' "$var_name" "$value" >> "$GITHUB_ENV"
  else
    printf '%s=%s\n' "$var_name" "$value"
  fi
done
