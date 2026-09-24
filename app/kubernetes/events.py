"""Events data collection module for read-only Kubernetes inspection."""

from __future__ import annotations

import logging
from typing import Any

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class EventsCollector:
    """Collect recent Kubernetes events in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_events(self) -> list[dict[str, Any]]:
        """Return recent event entries from the cluster when available."""
        if not self.client.available or self.client.core_v1 is None:
            return []

        try:
            response = self.client.core_v1.list_event_for_all_namespaces()
            events: list[dict[str, Any]] = []
            for item in response.items:
                events.append(
                    {
                        "namespace": item.metadata.namespace,
                        "name": item.metadata.name,
                        "type": item.type,
                        "reason": item.reason,
                        "message": item.message,
                        "count": item.count,
                        "first_timestamp": item.first_timestamp,
                        "last_timestamp": item.last_timestamp,
                    }
                )
            return events
        except Exception:
            logger.exception("Failed to collect Kubernetes events.")
            raise
