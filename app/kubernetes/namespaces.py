"""Namespaces collector for read-only Kubernetes inspection."""

from __future__ import annotations

from typing import Any

from app.kubernetes.client import KubernetesClient


class NamespacesCollector:
    """Return current namespace metadata in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_namespaces(self) -> list[str]:
        """List namespace names when the cluster is reachable."""
        if not self.client.available or self.client.core_v1 is None:
            return []

        try:
            response = self.client.core_v1.list_namespace()
            return [item.metadata.name for item in response.items if item.metadata and item.metadata.name]
        except Exception:
            return []
