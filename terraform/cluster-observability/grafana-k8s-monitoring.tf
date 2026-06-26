resource "helm_release" "grafana-k8s-monitoring" {
  name             = "grafana-k8s-monitoring"
  repository       = "https://grafana.github.io/helm-charts"
  chart            = "k8s-monitoring"
  version          = "^4"
  namespace        = var.namespace
  create_namespace = true
  atomic           = true
  timeout          = 300

  values = [file("${path.module}/values.yaml")]

  set {
    name  = "cluster.name"
    value = var.cluster_name
  }

  set {
    name  = "destinations.grafana-cloud-logs.url"
    value = var.destinations_loki_url
  }

  set_sensitive {
    name  = "destinations.grafana-cloud-logs.auth.username"
    value = var.destinations_loki_username
  }

  set_sensitive {
    name  = "destinations.grafana-cloud-logs.auth.password"
    value = var.destinations_loki_password
  }

  set {
    name  = "collectorCommon.alloy.remoteConfig.url"
    value = var.fleetmanagement_url
  }

  set_sensitive {
    name  = "collectorCommon.alloy.remoteConfig.auth.username"
    value = var.fleetmanagement_username
  }

  set_sensitive {
    name  = "collectorCommon.alloy.remoteConfig.auth.password"
    value = var.fleetmanagement_password
  }
}
