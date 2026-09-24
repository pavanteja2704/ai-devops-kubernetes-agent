"""Pods data collection module for read-only Kubernetes inspection."""

from __future__ import annotations

import logging
from typing import Any

from app.kubernetes.client import KubernetesClient

logger = logging.getLogger(__name__)


class PodsCollector:
    """Collect pod metadata and health indicators in read-only mode."""

    def __init__(self, client: KubernetesClient) -> None:
        self.client = client

    def get_pods(self) -> list[dict[str, Any]]:
        """Return pod entries with health markers for the agent."""
        if not self.client.available or self.client.core_v1 is None:
            return []

        try:
            response = self.client.core_v1.list_pod_for_all_namespaces()
            pods: list[dict[str, Any]] = []
            for item in response.items:
                container_states: list[dict[str, Any]] = []
                restart_counts: dict[str, int] = {}
                container_specs = {
                    container.name: container
                    for container in (item.spec.containers or [])
                    if container.name
                }
                for container in (item.status.container_statuses or []):
                    if container.name:
                        restart_counts[container.name] = container.restart_count
                    state = container.state
                    if state:
                        current_state = "waiting"
                        state_reason = None
                        state_detail = None
                        if state.running is not None:
                            current_state = "running"
                        elif state.terminated is not None:
                            current_state = "terminated"
                            state_reason = state.terminated.reason
                            state_detail = state.terminated.message
                        elif state.waiting is not None:
                            state_reason = state.waiting.reason
                            state_detail = state.waiting.message
                        container_states.append(
                            {
                                "name": container.name,
                                "state": current_state,
                                "reason": state_reason,
                                "detail": state_detail,
                                "image": getattr(container_specs.get(container.name), "image", None),
                            }
                        )

                pods.append(
                    {
                        "namespace": item.metadata.namespace,
                        "name": item.metadata.name,
                        "phase": item.status.phase,
                        "container_states": container_states,
                        "restart_counts": restart_counts,
                        "node": item.spec.node_name,
                        "creation_timestamp": item.metadata.creation_timestamp,
                        "owner_references": [
                            {
                                "kind": owner.kind,
                                "name": owner.name,
                                "uid": owner.uid,
                            }
                            for owner in (item.metadata.owner_references or [])
                        ],
                    }
                )
            return pods
        except Exception:
            logger.exception("Failed to collect pod evidence.")
            raise
