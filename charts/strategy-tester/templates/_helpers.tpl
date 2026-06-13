{{/*
Expand the name of the chart.
*/}}
{{- define "strategy-tester.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "strategy-tester.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "strategy-tester.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "strategy-tester.labels" -}}
helm.sh/chart: {{ include "strategy-tester.chart" . }}
{{ include "strategy-tester.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "strategy-tester.selectorLabels" -}}
app.kubernetes.io/name: {{ include "strategy-tester.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Get namespace
*/}}
{{- define "strategy-tester.namespace" -}}
{{- if .Values.namespaceOverride }}
{{- .Values.namespaceOverride }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "strategy-tester.ssmParameters" -}}
{{- $common := include "ssm-common.ssmParameters" . | fromYaml }}
{{- $path := .Values.externalSecrets.parameterMapFile | default "ssm-parameter-keys.yaml" -}}
{{- $raw := .Files.Get $path -}}
{{- if not $raw -}}
{{- fail (printf "strategy-tester external secret map file not found: %s" $path) -}}
{{- end -}}
{{- $local := $raw | fromYaml }}
{{- $merged := merge $common $local -}}
{{- toYaml $merged }}
{{- end }}
