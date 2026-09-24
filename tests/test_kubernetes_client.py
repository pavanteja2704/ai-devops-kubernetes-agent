"""Tests for Kubernetes connectivity and read-only collectors."""

from pathlib import Path

import pytest

from app.kubernetes.client import KubernetesClient
from app.kubernetes.deployments import DeploymentsCollector
from app.kubernetes.events import EventsCollector
from app.kubernetes.logs import LogsCollector
from app.kubernetes.nodes import NodesCollector
from app.kubernetes.pods import PodsCollector


class FakeNode:
    def __init__(self, name: str, ready: str = "True") -> None:
        self.metadata = type("Meta", (), {"name": name})()
        self.status = type(
            "Status",
            (),
            {
                "conditions": [type("Condition", (), {"type": "Ready", "status": ready})()],
                "capacity": {"cpu": "2", "memory": "4Gi"},
                "node_info": type("NodeInfo", (), {"kubelet_version": "v1.30.0"})(),
            },
        )()


class FakePod:
    def __init__(self, namespace: str, name: str, phase: str, node: str) -> None:
        self.metadata = type(
            "Meta",
            (),
            {"namespace": namespace, "name": name, "creation_timestamp": "2024-01-01T00:00:00Z"},
        )()
        self.status = type(
            "Status",
            (),
            {
                "phase": phase,
                "container_statuses": [
                    type(
                        "Container",
                        (),
                        {"name": "app", "restart_count": 2, "state": type("State", (), {"running": True})()},
                    )()
                ],
            },
        )()
        self.spec = type(
            "Spec",
            (),
            {
                "node_name": node,
                "containers": [type("ContainerSpec", (), {"name": "app", "image": "nginx:latest"})()],
            },
        )()
        self.metadata.owner_references = []


class FakeDeployment:
    def __init__(self, namespace: str, name: str, desired: int, available: int, ready: int) -> None:
        self.metadata = type("Meta", (), {"namespace": namespace, "name": name})()
        self.spec = type("Spec", (), {"replicas": desired})()
        self.status = type("Status", (), {"available_replicas": available, "ready_replicas": ready})()


class FakeEvent:
    def __init__(self, namespace: str, name: str, reason: str, message: str) -> None:
        self.metadata = type("Meta", (), {"namespace": namespace, "name": name})()
        self.type = "Warning"
        self.reason = reason
        self.message = message
        self.count = 1
        self.first_timestamp = "2024-01-01T00:00:00Z"
        self.last_timestamp = "2024-01-01T00:00:00Z"


class FakeCoreV1Api:
    def list_node(self):
        return type("Response", (), {"items": [FakeNode("node-1")]})()

    def list_pod_for_all_namespaces(self):
        return type("Response", (), {"items": [FakePod("default", "pod-1", "Running", "node-1")]})()

    def list_event_for_all_namespaces(self):
        return type("Response", (), {"items": [FakeEvent("default", "pod-1", "BackOff", "Container restarting")]})()

    def list_service_for_all_namespaces(self):
        return type("Response", (), {"items": []})()

    def read_namespaced_pod_log(self, name, namespace, container=None, _request_timeout=None):
        return "Error: application failed to start"


class FailingLogsCoreV1Api(FakeCoreV1Api):
    def read_namespaced_pod_log(self, name, namespace, container=None, _request_timeout=None):
        from kubernetes.client.rest import ApiException

        raise ApiException(status=400, reason="Container has not started")


class FakeAppsV1Api:
    def list_deployment_for_all_namespaces(self):
        return type("Response", (), {"items": [FakeDeployment("default", "app", 3, 2, 2)]})()


def test_kubernetes_client_handles_missing_configuration(tmp_path: Path) -> None:
    """A missing kubeconfig should fail gracefully without crashing the app."""
    missing_config = tmp_path / "missing-kubeconfig"

    client = KubernetesClient(kubeconfig_path=str(missing_config), context="local-dev")

    assert client.is_available() is False
    payload = client.get_cluster_info()
    assert payload["available"] is False
    assert payload["context"] == "local-dev"
    assert "error" in payload


def test_nodes_collector_returns_read_only_metadata() -> None:
    """Node collector should return safe node summary fields from mocked API data."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.core_v1 = FakeCoreV1Api()

    nodes = NodesCollector(client).get_nodes()

    assert len(nodes) == 1
    assert nodes[0]["name"] == "node-1"
    assert nodes[0]["status"] == "True"
    assert nodes[0]["cpu_capacity"] == "2"


def test_pod_collector_returns_status_data() -> None:
    """Pod collector should summarize phase, node, and restart counters."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.core_v1 = FakeCoreV1Api()

    pods = PodsCollector(client).get_pods()

    assert len(pods) == 1
    assert pods[0]["namespace"] == "default"
    assert pods[0]["phase"] == "Running"
    assert pods[0]["restart_counts"]["app"] == 2


def test_deployment_collector_returns_replica_data() -> None:
    """Deployment collector should expose desired, available, and ready replicas."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.apps_v1 = FakeAppsV1Api()

    deployments = DeploymentsCollector(client).get_deployments()

    assert len(deployments) == 1
    assert deployments[0]["name"] == "app"
    assert deployments[0]["desired_replicas"] == 3
    assert deployments[0]["available_replicas"] == 2


def test_event_collector_returns_recent_events() -> None:
    """Event collector should return recent warnings and messages without mutating the cluster."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.core_v1 = FakeCoreV1Api()

    events = EventsCollector(client).get_events()

    assert len(events) == 1
    assert events[0]["reason"] == "BackOff"
    assert "Container restarting" in events[0]["message"]


def test_logs_collector_returns_logs_for_running_container() -> None:
    """Running containers should continue to expose available logs."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.core_v1 = FakeCoreV1Api()

    assert LogsCollector(client).get_pod_logs("default", "pod-1", "app") == "Error: application failed to start"


def test_logs_collector_surfaces_api_error_for_agent_to_record() -> None:
    """Individual Kubernetes log errors should be catchable by evidence collection."""
    client = KubernetesClient(kubeconfig_path="/tmp/unused")
    client.available = True
    client.core_v1 = FailingLogsCoreV1Api()

    with pytest.raises(Exception, match="Container has not started"):
        LogsCollector(client).get_pod_logs("default", "pod-1", "app")
