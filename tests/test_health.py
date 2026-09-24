"""Tests for the FastAPI health endpoint."""

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


class UnavailableKubernetesClient:
    available = False
    last_error = "API server unavailable"
    message = "Kubernetes cluster is not available"

    def is_available(self) -> bool:
        return False


class AvailableKubernetesClient:
    available = True
    last_error = None
    message = "Kubernetes cluster is available"

    class Core:
        def list_node(self):
            return type("Response", (), {"items": []})()

        def list_pod_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

        def list_event_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

        def list_service_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

    class Apps:
        def list_deployment_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

    core_v1 = Core()
    apps_v1 = Apps()

    def is_available(self) -> bool:
        return True


class CapturingGeminiClient:
    def __init__(self) -> None:
        self.prompt = ""

    def is_available(self) -> bool:
        return True

    def analyze(self, prompt: str) -> dict:
        self.prompt = prompt
        return {
            "status": "unknown",
            "problem": {"title": "Unknown", "resource_type": "Cluster", "resource_name": "", "namespace": "", "current_state": "Unknown", "impact": "Unknown"},
            "root_cause": {"summary": "Unknown.", "confidence": "low", "evidence": []},
            "recommended_actions": [],
            "what_not_to_do": [],
            "verification": [],
            "limitations": [],
        }


def test_health_endpoint_returns_healthy() -> None:
    """The service should expose a simple health check without cloud dependencies."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_returns_collection_error_when_kubernetes_is_unavailable() -> None:
    """Analysis must not pretend that failed Kubernetes collection is empty evidence."""
    app = create_app(Settings(), kubernetes_client=UnavailableKubernetesClient())
    client = TestClient(app)

    response = client.post("/analyze", json={"question": "Why is the workload failing?"})

    assert response.status_code == 503
    assert "API server unavailable" in response.json()["detail"]


def test_analyze_collects_evidence_before_invoking_gemini() -> None:
    """The API should pass collected Kubernetes evidence into the Gemini prompt."""
    gemini = CapturingGeminiClient()
    app = create_app(
        Settings(),
        kubernetes_client=AvailableKubernetesClient(),
        gemini_client=gemini,
    )
    client = TestClient(app)

    response = client.post("/analyze", json={"question": "What is happening in the cluster?"})

    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert '"pods": []' in gemini.prompt
    assert '"deployments": []' in gemini.prompt
    assert '"services": []' in gemini.prompt
    assert '"events": []' in gemini.prompt
