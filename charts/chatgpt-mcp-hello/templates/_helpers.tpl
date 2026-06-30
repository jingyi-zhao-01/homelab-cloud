{{- define "chatgpt-mcp-hello.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "chatgpt-mcp-hello.fullname" -}}
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

{{- define "chatgpt-mcp-hello.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "chatgpt-mcp-hello.labels" -}}
helm.sh/chart: {{ include "chatgpt-mcp-hello.chart" . }}
{{ include "chatgpt-mcp-hello.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "chatgpt-mcp-hello.selectorLabels" -}}
app.kubernetes.io/name: {{ include "chatgpt-mcp-hello.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "chatgpt-mcp-hello.namespace" -}}
{{- if .Values.namespaceOverride }}
{{- .Values.namespaceOverride }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{- define "chatgpt-mcp-hello.secretName" -}}
{{- if .Values.externalSecrets.enabled }}
{{- .Values.externalSecrets.targetSecretName }}
{{- end }}
{{- end }}

{{- define "chatgpt-mcp-hello.ssmParameters" -}}
{{- $common := include "ssm-common.ssmParameters" . | fromYaml }}
{{- $path := .Values.externalSecrets.parameterMapFile | default "ssm-parameter-keys.yaml" -}}
{{- $raw := .Files.Get $path -}}
{{- if not $raw -}}
{{- fail (printf "chatgpt-mcp-hello external secret map file not found: %s" $path) -}}
{{- end -}}
{{- $local := $raw | fromYaml }}
{{- $merged := merge $common $local -}}
{{- toYaml $merged }}
{{- end }}
