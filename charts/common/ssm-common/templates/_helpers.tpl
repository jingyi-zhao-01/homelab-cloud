{{- define "ssm-common.ssmParameters" -}}
OTEL_EXPORTER_OTLP_ENDPOINT:
  path: /grafana/OTEL_EXPORTER_OTLP_ENDPOINT
  optional: false

OTEL_EXPORTER_OTLP_HEADERS:
  path: /grafana/OTEL_EXPORTER_OTLP_HEADERS
  optional: false
{{- end -}}
