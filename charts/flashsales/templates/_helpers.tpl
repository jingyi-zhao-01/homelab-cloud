{{- define "flashsales.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "flashsales.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s" (include "flashsales.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "flashsales.namespace" -}}
{{- default .Release.Namespace .Values.namespaceOverride -}}
{{- end -}}

{{- define "flashsales.ssmParameters" -}}
{{- $path := .Values.externalSecrets.parameterMapFile | default "ssm-parameter-keys.yaml" -}}
{{- $raw := .Files.Get $path -}}
{{- if not $raw -}}
{{- fail (printf "flashsales external secret map file not found: %s" $path) -}}
{{- end -}}
{{- $raw -}}
{{- end -}}

{{- define "flashsales.labels" -}}
app.kubernetes.io/name: {{ include "flashsales.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
