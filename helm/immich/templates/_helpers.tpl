{{- define "immich.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "immich.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- include "immich.name" . }}
{{- end }}
{{- end }}

{{- define "immich.labels" -}}
app.kubernetes.io/name: {{ include "immich.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "immich.selectorLabels" -}}
app.kubernetes.io/name: {{ include "immich.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "immich.serverLabels" -}}
{{ include "immich.selectorLabels" . }}
app: immich-server
{{- end }}

{{- define "immich.databaseLabels" -}}
{{ include "immich.selectorLabels" . }}
app: database
{{- end }}

{{- define "immich.redisLabels" -}}
{{ include "immich.selectorLabels" . }}
app: redis
{{- end }}

{{- define "immich.mlLabels" -}}
{{ include "immich.selectorLabels" . }}
app: immich-machine-learning
{{- end }}

{{- define "immich.containerSecurityContext" -}}
allowPrivilegeEscalation: {{ .allowPrivilegeEscalation }}
privileged: {{ .privileged }}
readOnlyRootFilesystem: {{ .readOnlyRootFilesystem }}
capabilities:
  drop:
    {{- toYaml .capabilitiesDrop | nindent 4 }}
{{- end }}
