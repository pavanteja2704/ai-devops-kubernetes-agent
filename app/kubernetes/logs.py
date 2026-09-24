"""Pod logs collection module for read-only Kubernetes inspection."""

from __future__ import annotations

import logging

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class LogsCollector:
    """Collect pod logs in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_pod_logs(self, namespace: str, pod_name: str, container_name: str | None = None) -> str:
        """Return logs for a specified pod and optional container."""
        if not self.client.available or self.client.core_v1 is None:
            return "Kubernetes cluster is not available"

        try:
            if container_name:
                return self.client.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container_name,
                    _request_timeout=10,
                )
            return self.client.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                _request_timeout=10,
            )
        except Exception:
            logger.exception("Failed to collect logs for pod %s/%s.", namespace, pod_name)
            raise
