"""Tests for the Gemini analysis workflow and fallback behavior."""

from __future__ import annotations

import pytest
from kubernetes.client.rest import ApiException

from app.agent.agent import Agent
from app.config.settings import Settings


class FakeReadOnlyKubernetesClient:
    available = True
    last_error = None
    message = "Kubernetes cluster is available"

    def is_available(self) -> bool:
        return True

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


class FakeGeminiClient:
    def __init__(self, available: bool = True, response: dict | None = None) -> None:
        self._available = available
        self._response = response or {
            "status": "critical",
            "problem": {"title": "CrashLoopBackOff", "resource_type": "Pod", "resource_name": "app-123", "namespace": "default", "current_state": "CrashLoopBackOff", "impact": "One Pod is restarting."},
            "root_cause": {"summary": "The container is repeatedly exiting during startup.", "confidence": "high", "evidence": ["Pod restart count is elevated."]},
            "recommended_actions": [{"priority": 1, "title": "Inspect logs", "description": "Review startup errors.", "command": "kubectl logs app-123 -n default", "risk": "low"}],
            "what_not_to_do": ["Do not restart unrelated workloads."],
            "verification": [{"description": "Check Pod status.", "command": "kubectl get pod app-123 -n default"}],
            "limitations": ["This conclusion is based on the supplied evidence only."],
        }

    def is_available(self) -> bool:
        return self._available

    def analyze(self, prompt: str) -> dict:
        if not self._available:
            raise RuntimeError("Gemini unavailable")
        return self._response


class CapturingGeminiClient(FakeGeminiClient):
    def __init__(self) -> None:
        super().__init__()
        self.prompt = ""

    def analyze(self, prompt: str) -> dict:
        self.prompt = prompt
        return self._response


class EvidencePodClient:
    available = True
    last_error = None
    message = "Kubernetes cluster is available"

    def __init__(self, state: str, reason: str | None = None, logs_error: bool = False) -> None:
        self.core_v1 = self.Core(state, reason, logs_error)
        self.apps_v1 = self.Apps()

    def is_available(self) -> bool:
        return True

    class Core:
        def __init__(self, state: str, reason: str | None, logs_error: bool) -> None:
            container_state = type(
                "State",
                (),
                {
                    "running": object() if state == "running" else None,
                    "waiting": type("Waiting", (), {"reason": reason, "message": "image pull failed"})()
                    if state == "waiting"
                    else None,
                    "terminated": type(
                        "Terminated",
                        (),
                        {"reason": "Error", "message": "container exited before producing logs"},
                    )()
                    if state == "terminated"
                    else None,
                },
            )()
            self.pod = type(
                "Pod",
                (),
                {
                    "metadata": type(
                        "Meta",
                        (),
                        {"namespace": "default", "name": "ai-test-broken-image", "creation_timestamp": None},
                    )(),
                    "status": type(
                        "Status",
                        (),
                        {
                            "phase": "Pending" if state == "waiting" else ("Failed" if state == "terminated" else "Running"),
                            "container_statuses": [
                                type(
                                    "Container",
                                    (),
                                    {
                                        "name": "nginx",
                                        "restart_count": 1 if state != "waiting" else 0,
                                        "state": container_state,
                                    },
                                )()
                            ],
                        },
                    )(),
                    "spec": type("Spec", (), {"node_name": "node-1"})(),
                },
            )()
            self.pod.spec.containers = [type("ContainerSpec", (), {"name": "nginx", "image": "nginx:this-image-does-not-exist"})()]
            self.pod.metadata.owner_references = []
            self.logs_error = logs_error

        def list_pod_for_all_namespaces(self):
            return type("Response", (), {"items": [self.pod]})()

        def list_event_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

        def list_service_for_all_namespaces(self):
            return type("Response", (), {"items": []})()

        def list_node(self):
            return type("Response", (), {"items": []})()

        def read_namespaced_pod_log(self, name, namespace, container=None, _request_timeout=None):
            if self.logs_error:
                raise ApiException(status=400, reason="Container has not started")
            return "application started"

    class Apps:
        def list_deployment_for_all_namespaces(self):
            return type("Response", (), {"items": []})()


def make_evidence_agent(client: EvidencePodClient) -> tuple[Agent, CapturingGeminiClient]:
    gemini = CapturingGeminiClient()
    return Agent(Settings(), gemini_client=gemini, kubernetes_client=client), gemini


def test_agent_collects_kubernetes_evidence_before_gemini() -> None:
    """The agent should send current read-only cluster evidence to Gemini."""
    settings = Settings()
    gemini = CapturingGeminiClient()
    agent = Agent(
        settings,
        gemini_client=gemini,
        kubernetes_client=FakeReadOnlyKubernetesClient(),
    )

    evidence = agent.collect_evidence()
    result = agent.analyze("What is happening in the cluster?", evidence)

    assert result["status"] == "critical"
    assert result["problem"]["title"] == "CrashLoopBackOff"
    assert '"pods": []' in gemini.prompt
    assert '"deployments": []' in gemini.prompt
    assert '"events": []' in gemini.prompt


def test_waiting_image_pull_backoff_is_recorded_without_requesting_logs() -> None:
    """Waiting ImagePullBackOff containers should produce unavailable log evidence."""
    agent, _ = make_evidence_agent(EvidencePodClient("waiting", "ImagePullBackOff"))

    evidence = agent.collect_evidence()

    assert evidence["pods"][0]["name"] == "ai-test-broken-image"
    assert evidence["logs"][0]["available"] is False
    assert evidence["logs"][0]["container_state"] == "waiting"
    assert evidence["logs"][0]["reason_detail"] == "ImagePullBackOff"


def test_image_pull_backoff_returns_structured_diagnosis_and_safe_commands() -> None:
    """A broken image remains visible in the structured incident response."""
    client = EvidencePodClient("waiting", "ImagePullBackOff")
    agent = Agent(Settings(), gemini_client=FakeGeminiClient(available=False), kubernetes_client=client)
    result = agent.analyze("What command should I run to fix this?", agent.collect_evidence())

    assert result["status"] == "critical"
    assert result["problem"]["resource_name"] == "ai-test-broken-image"
    assert result["root_cause"]["confidence"] == "high"
    assert "ImagePullBackOff" in result["root_cause"]["evidence"][0]
    assert "ai-test-broken-image" in result["verification"][0]["command"]
    assert "Do not delete the Pod blindly" in result["what_not_to_do"][0]
    assert "nginx:this-image-does-not-exist" in result["root_cause"]["evidence"][-1]


def test_delete_question_generates_warning_for_unowned_pod() -> None:
    """A delete recommendation is generated only from observed resource identity."""
    agent, _ = make_evidence_agent(EvidencePodClient("waiting", "ErrImagePull"))

    result = Agent(
        Settings(),
        gemini_client=FakeGeminiClient(available=False),
        kubernetes_client=agent.kubernetes_client,
    ).analyze("How do I delete this pod?", agent.collect_evidence())

    assert result["recommended_actions"][0]["command"] == "kubectl delete pod ai-test-broken-image -n default"
    assert result["recommended_actions"][0]["risk"] == "high"
    assert "Review before executing" in result["what_not_to_do"][0]


def test_controller_ownership_changes_restart_guidance() -> None:
    """Controller-owned Pods must not receive blind delete guidance."""
    client = EvidencePodClient("waiting", "ImagePullBackOff")
    client.core_v1.pod.metadata.owner_references = [
        type("Owner", (), {"kind": "Deployment", "name": "web", "uid": "uid-1"})()
    ]
    agent = Agent(Settings(), gemini_client=FakeGeminiClient(available=False), kubernetes_client=client)

    result = agent.analyze("How do I restart this pod?", agent.collect_evidence())

    assert "kubectl get deployment web -n default" == result["recommended_actions"][0]["command"]
    assert "controller-managed" in result["recommended_actions"][0]["description"]


def test_running_container_logs_are_available() -> None:
    """Running containers should retain their collected log text."""
    agent, _ = make_evidence_agent(EvidencePodClient("running"))

    evidence = agent.collect_evidence()

    assert evidence["logs"][0]["available"] is True
    assert evidence["logs"][0]["text"] == "application started"


def test_log_api_400_is_recorded_and_analysis_continues() -> None:
    """A log API 400 must not prevent Gemini from receiving pod evidence."""
    agent, gemini = make_evidence_agent(EvidencePodClient("terminated", logs_error=True))

    evidence = agent.collect_evidence()
    result = agent.analyze("Why is this pod failing?", evidence)

    assert evidence["pods"][0]["name"] == "ai-test-broken-image"
    assert evidence["logs"][0]["available"] is False
    assert "Kubernetes log" in evidence["logs"][0]["reason"]
    assert result["status"] == "critical"
    assert "ai-test-broken-image" in gemini.prompt


def test_agent_successful_analysis() -> None:
    """A mock Gemini response should be returned in the expected structure."""
    settings = Settings()
    agent = Agent(settings, gemini_client=FakeGeminiClient())

    response = agent.analyze(
        "Why is my application restarting?",
        {
            "pods": [{"name": "app-123", "phase": "Running"}],
            "events": [{"reason": "BackOff", "message": "Container restarting"}],
            "logs": ["Error: port 8080 already in use"],
        },
    )

    assert response["root_cause"]["summary"] == "The container is repeatedly exiting during startup."
    assert response["recommended_actions"][0]["command"] == "kubectl logs app-123 -n default"


def test_agent_falls_back_when_gemini_is_unavailable() -> None:
    """The agent should return a conservative response when Gemini is unavailable."""
    settings = Settings()
    agent = Agent(settings, gemini_client=FakeGeminiClient(available=False))

    result = agent.analyze("Why is it failing?", {"pods": [{"name": "app", "phase": "CrashLoopBackOff"}]})

    assert result["status"] in {"critical", "warning", "healthy", "unknown"}
    assert any("Gemini analysis is unavailable" in item for item in result["limitations"])


def test_agent_rejects_malformed_input() -> None:
    """Malformed input should raise a validation error."""
    settings = Settings()
    agent = Agent(settings, gemini_client=FakeGeminiClient())

    with pytest.raises(ValueError):
        agent.analyze("")


def test_agent_handles_insufficient_evidence() -> None:
    """If no evidence is provided, the result should state the diagnosis is uncertain."""
    settings = Settings()
    agent = Agent(settings, gemini_client=FakeGeminiClient())

    result = agent.analyze("Why is it failing?", {})

    assert result["status"] == "unknown"
    assert result["root_cause"]["confidence"] == "low"
    assert any("limited to the Kubernetes evidence" in item for item in result["limitations"])


def test_agent_handles_gemini_error() -> None:
    """A runtime error from Gemini should not crash the agent."""
    settings = Settings()

    class FailingGeminiClient(FakeGeminiClient):
        def analyze(self, prompt: str) -> dict:
            raise RuntimeError("API call failed")

    agent = Agent(settings, gemini_client=FailingGeminiClient())
    result = agent.analyze("Why is it failing?", {"events": [{"reason": "BackOff"}]})

    assert result["status"] in {"critical", "warning", "healthy", "unknown"}
    assert any("Gemini analysis is unavailable" in item for item in result["limitations"])
