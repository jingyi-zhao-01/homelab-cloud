from __future__ import annotations

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


class KubernetesTriage:
    def __init__(self) -> None:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()
        self._core = client.CoreV1Api()
        self._apps = client.AppsV1Api()

    def collect_namespace_snapshot(self, namespace: str) -> dict:
        pods = self._core.list_namespaced_pod(namespace=namespace).items
        deployments = self._apps.list_namespaced_deployment(namespace=namespace).items
        events = self._core.list_namespaced_event(namespace=namespace).items

        pod_summaries = []
        for pod in pods[:20]:
            statuses = pod.status.container_statuses or []
            waiting = [status.state.waiting.reason for status in statuses if status.state and status.state.waiting]
            terminated = [status.state.terminated.reason for status in statuses if status.state and status.state.terminated]
            pod_summaries.append(
                {
                    "name": pod.metadata.name,
                    "phase": pod.status.phase,
                    "node": pod.spec.node_name,
                    "waiting": waiting,
                    "terminated": terminated,
                    "restarts": sum(status.restart_count for status in statuses),
                }
            )

        deployment_summaries = [
            {
                "name": deployment.metadata.name,
                "ready": f"{deployment.status.ready_replicas or 0}/{deployment.status.replicas or 0}",
                "updated": deployment.status.updated_replicas or 0,
                "available": deployment.status.available_replicas or 0,
            }
            for deployment in deployments[:20]
        ]

        event_summaries = [
            {
                "reason": event.reason,
                "message": event.message,
                "type": event.type,
                "object": event.involved_object.name,
            }
            for event in sorted(events, key=lambda item: item.last_timestamp or item.event_time or item.metadata.creation_timestamp)[-20:]
        ]

        return {
            "namespace": namespace,
            "pods": pod_summaries,
            "deployments": deployment_summaries,
            "events": event_summaries,
        }
