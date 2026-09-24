"""Services collector for read-only Kubernetes inspection."""

from __future__ import annotations

import logging
from typing import Any

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class ServicesCollector:
    """Return service metadata without mutating cluster state."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_services(self) -> list[dict[str, Any]]:
        """List service details from the cluster when available."""
        if not self.client.available or self.client.core_v1 is None:
            return []

        try:
            response = self.client.core_v1.list_service_for_all_namespaces()
            services: list[dict[str, Any]] = []
            for item in response.items:
                ports = [
                    {
                        "name": port.name,
                        "port": port.port,
                        "target_port": port.target_port,
                        "protocol": port.protocol,
                    }
                    for port in (item.spec.ports or [])
                ]
                services.append(
                    {
                        "namespace": item.metadata.namespace,
                        "name": item.metadata.name,
                        "type": item.spec.type,
                        "cluster_ip": item.spec.cluster_ip,
                        "ports": ports,
                    }
                )
            return services
        except Exception:
            logger.exception("Failed to collect service evidence.")
            raise
