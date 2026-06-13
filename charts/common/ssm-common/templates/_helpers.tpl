{{- define "ssm-common.ssmParameters" -}}
{{- $raw := .Files.Get "ssm-parameter-keys.yaml" -}}
{{- if not $raw -}}
{{- fail "ssm-common external secret map file not found: ssm-parameter-keys.yaml" -}}
{{- end -}}
{{- $raw -}}
{{- end -}}
