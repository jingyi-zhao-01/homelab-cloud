{{/*
Expand the name of the chart.
*/}}
{{- define "leetcode-intelligence.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "leetcode-intelligence.fullname" -}}
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
{{- define "leetcode-intelligence.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "leetcode-intelligence.labels" -}}
helm.sh/chart: {{ include "leetcode-intelligence.chart" . }}
{{ include "leetcode-intelligence.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "leetcode-intelligence.selectorLabels" -}}
app.kubernetes.io/name: {{ include "leetcode-intelligence.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Get namespace
*/}}
{{- define "leetcode-intelligence.namespace" -}}
{{- if .Values.namespaceOverride }}
{{- .Values.namespaceOverride }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "leetcode-intelligence.ssmParameters" -}}
{{- $common := include "ssm-common.ssmParameters" . | fromYaml }}
{{- $path := .Values.externalSecrets.parameterMapFile | default "ssm-parameter-keys.yaml" -}}
{{- $raw := .Files.Get $path -}}
{{- if not $raw -}}
{{- fail (printf "leetcode-intelligence external secret map file not found: %s" $path) -}}
{{- end -}}
{{- $local := $raw | fromYaml }}
{{- $merged := merge $common $local -}}
{{- toYaml $merged }}
{{- end }}

{{/*
Get runtime secret name
*/}}
{{- define "leetcode-intelligence.secretName" -}}
{{- if .Values.externalSecrets.enabled }}
{{- .Values.externalSecrets.targetSecretName }}
{{- else }}
{{- .Values.secrets.existingSecretName }}
{{- end }}
{{- end }}
