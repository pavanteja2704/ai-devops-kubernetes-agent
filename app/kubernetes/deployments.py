"""Deployments data collection module for read-only Kubernetes inspection."""

from __future__ import annotations

import logging
from typing import Any

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class DeploymentsCollector:
    """Collect deployment metadata in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_deployments(self) -> list[dict[str, Any]]:
        """Return deployment information when the cluster is available."""
        if not self.client.available or self.client.apps_v1 is None:
            return []

        try:
            response = self.client.apps_v1.list_deployment_for_all_namespaces()
            deployments: list[dict[str, Any]] = []
            for item in response.items:
                deployments.append(
                    {
                        "namespace": item.metadata.namespace,
                        "name": item.metadata.name,
                        "desired_replicas": item.spec.replicas,
                        "available_replicas": item.status.available_replicas,
                        "ready_replicas": item.status.ready_replicas,
                    }
                )
            return deployments
        except Exception:
            logger.exception("Failed to collect deployment evidence.")
            raise
