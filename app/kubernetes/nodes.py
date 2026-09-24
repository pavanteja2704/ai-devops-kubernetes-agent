"""Nodes data collection module for read-only Kubernetes inspection."""

from __future__ import annotations

import logging
from typing import Any

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class NodesCollector:
    """Collect node metadata and status in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_nodes(self) -> list[dict[str, Any]]:
        """Return node information when the cluster is available."""
        if not self.client.available or self.client.core_v1 is None:
            return []

        try:
            response = self.client.core_v1.list_node()
            nodes: list[dict[str, Any]] = []
            for item in response.items:
                status = "unknown"
                ready_condition = next(
                    (condition for condition in (item.status.conditions or []) if condition.type == "Ready"),
                    None,
                )
                if ready_condition is not None:
                    status = ready_condition.status

                nodes.append(
                    {
                        "name": item.metadata.name,
                        "status": status,
                        "kubernetes_version": item.status.node_info.kubelet_version if item.status and item.status.node_info else "unknown",
                        "cpu_capacity": item.status.capacity.get("cpu", "0") if item.status and item.status.capacity else "0",
                        "memory_capacity": item.status.capacity.get("memory", "0") if item.status and item.status.capacity else "0",
                    }
                )
            return nodes
        except Exception:
            logger.exception("Failed to collect node evidence.")
            raise
