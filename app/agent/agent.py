"""Core orchestration logic for the Kubernetes troubleshooting agent."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config.settings import Settings
from app.gemini.client import GeminiClient
from app.kubernetes.client import KubernetesClient
from app.kubernetes.deployments import DeploymentsCollector
from app.kubernetes.events import EventsCollector
from app.kubernetes.logs import LogsCollector
from app.kubernetes.nodes import NodesCollector
from app.kubernetes.pods import PodsCollector
from app.kubernetes.services import ServicesCollector

logger = logging.getLogger(__name__)


class KubernetesEvidenceError(RuntimeError):
    """Raised when current cluster evidence cannot be collected."""


def _empty_incident() -> dict[str, Any]:
    return {
        "status": "unknown",
        "problem": {
            "title": "No confirmed workload problem",
            "resource_type": "Cluster",
            "resource_name": "",
            "namespace": "",
            "current_state": "Unknown",
            "impact": "The available evidence does not establish a specific impact.",
        },
        "root_cause": {
            "summary": "There is not enough evidence to identify a root cause.",
            "confidence": "low",
            "evidence": [],
        },
        "recommended_actions": [],
        "what_not_to_do": ["Do not make changes to the cluster based on incomplete evidence."],
        "verification": [],
        "limitations": ["The conclusion is limited to the Kubernetes evidence collected for this request."],
    }


class Agent:
    """Coordinates collection of cluster data, AI analysis, and responses."""

    def __init__(
        self,
        settings: Settings,
        gemini_client: GeminiClient | None = None,
        kubernetes_client: KubernetesClient | None = None,
    ) -> None:
        self.settings = settings
        self.kubernetes_client = kubernetes_client
        self.gemini_client = gemini_client or GeminiClient(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            project_id=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    def collect_evidence(self, selected_client: KubernetesClient | None = None) -> dict[str, Any]:
        """Collect current read-only Kubernetes evidence for an analysis."""
        client = selected_client or self.kubernetes_client
        if client is None:
            raise KubernetesEvidenceError("Kubernetes client is not configured for analysis.")
        if not client.is_available():
            raise KubernetesEvidenceError(
                f"Kubernetes evidence collection unavailable: {client.last_error or client.message}"
            )

        logger.info("Collecting Kubernetes evidence for analysis.")
        try:
            pods = PodsCollector(client).get_pods()
            deployments = DeploymentsCollector(client).get_deployments()
            services = ServicesCollector(client).get_services()
            nodes = NodesCollector(client).get_nodes()
            events = [event for event in EventsCollector(client).get_events() if event.get("type") == "Warning"]
            logs: list[dict[str, Any]] = []
            for pod in pods:
                restart_counts = pod.get("restart_counts") or {}
                states = pod.get("container_states") or []
                if not any(restart_counts.values()) and pod.get("phase") == "Running":
                    continue
                for container in states or [{"name": None}]:
                    container_name = container.get("name")
                    container_state = container.get("state", "unknown")
                    state_reason = container.get("reason")
                    state_detail = container.get("detail")
                    if container_state == "waiting":
                        logs.append(
                            {
                                "available": False,
                                "namespace": pod["namespace"],
                                "pod": pod["name"],
                                "container": container_name,
                                "reason": "Container has not started; logs are unavailable",
                                "container_state": container_state,
                                "reason_detail": state_reason or state_detail or "unknown",
                            }
                        )
                        logger.info(
                            "Skipping logs for waiting container %s/%s/%s (%s).",
                            pod.get("namespace"),
                            pod.get("name"),
                            container_name,
                            state_reason or "unknown reason",
                        )
                        continue
                    logger.info(
                        "Collecting logs for pod %s/%s%s.",
                        pod.get("namespace"),
                        pod.get("name"),
                        f" container {container_name}" if container_name else "",
                    )
                    try:
                        log_text = LogsCollector(client).get_pod_logs(
                            pod["namespace"],
                            pod["name"],
                            container_name,
                        )
                        logs.append(
                            {
                                "available": True,
                                "namespace": pod["namespace"],
                                "pod": pod["name"],
                                "container": container_name,
                                "text": log_text[-4000:],
                                "container_state": container_state,
                            }
                        )
                    except Exception as exc:
                        logs.append(
                            {
                                "available": False,
                                "namespace": pod["namespace"],
                                "pod": pod["name"],
                                "container": container_name,
                                "reason": "Kubernetes logs API request failed",
                                "container_state": container_state,
                                "reason_detail": state_reason or state_detail,
                                "error": str(exc),
                            }
                        )
                        logger.warning(
                            "Logs unavailable for %s/%s/%s; continuing evidence collection: %s",
                            pod["namespace"],
                            pod["name"],
                            container_name,
                            exc,
                        )
        except Exception as exc:
            logger.exception("Kubernetes evidence collection failed.")
            raise KubernetesEvidenceError(f"Kubernetes evidence collection failed: {exc}") from exc

        evidence = {
            "pods": pods,
            "deployments": deployments,
            "services": services,
            "nodes": nodes,
            "events": events,
            "logs": logs,
        }
        logger.info(
            "Kubernetes evidence collected: %d pods, %d deployments, %d services, "
            "%d nodes, %d warning events, %d log entries.",
            len(pods),
            len(deployments),
            len(services),
            len(nodes),
            len(events),
            len(logs),
        )
        return evidence

    def health(self) -> dict[str, str | bool]:
        """Return a minimal health payload for local development."""
        return {
            "status": "healthy",
            "read_only_mode": self.settings.read_only_mode,
        }

    def _build_prompt(self, question: str, context: dict[str, Any]) -> str:
        """Construct the evidence-only analysis prompt for Gemini."""
        compact_context = json.dumps(context, default=str, sort_keys=True)
        return (
            "You are an AI-powered Kubernetes DevOps troubleshooting assistant. "
            "Analyze only the supplied evidence. Distinguish observed facts from assumptions. "
            "Do not invent Kubernetes information. If evidence is insufficient, say so and recommend "
            "safe next checks for a human. Never claim an action was performed. "
            "Return only concise JSON matching this schema: "
            '{"status":"critical|warning|healthy|unknown","problem":{"title":"",'
            '"resource_type":"","resource_name":"","namespace":"","current_state":"","impact":""},'
            '"root_cause":{"summary":"","confidence":"high|medium|low","evidence":[]},'
            '"recommended_actions":[{"priority":1,"title":"","description":"","command":"","risk":"low|medium|high"}],'
            '"what_not_to_do":[],"verification":[{"description":"","command":""}],"limitations":[]}. '
            "Do not include Markdown fences, chain-of-thought, or legacy fields. "
            "Commands are recommendations only and must use only resource names and namespaces present in the evidence. "
            "If ownership is uncertain, say so instead of recommending blind Pod deletion. "
            "For any destructive command, include the warning 'Review before executing — this changes cluster state.' "
            "Do not execute kubectl, gcloud, shell, or Python commands. "
            "The answer must remain read-only and conservative. Treat log entries with "
            "available=false as unavailable evidence, not as proof that no workload problem exists. "
            "Distinguish observed workload problems from Kubernetes API errors and unavailable logs.\n\n"
            f"Question: {question}\n\nContext: {compact_context}"
        )

    def _fallback_response(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        """Return a concise evidence-grounded incident response when Gemini is unavailable."""
        pods = context.get("pods") or []
        events = context.get("events") or []
        logs = context.get("logs") or []

        if not pods and not events and not logs:
            result = _empty_incident()
            result["limitations"].append("Gemini analysis is unavailable; no diagnosis was generated.")
            return result

        broken_pod = next(
            (
                pod
                for pod in pods
                if any(
                    str(container.get("reason", "")).lower() in {"imagepullbackoff", "errimagepull"}
                    for container in pod.get("container_states", [])
                )
            ),
            None,
        )
        warning = next((event for event in events if event.get("reason") in {"FailedScheduling", "FailedMount", "Unhealthy"}), None)
        explicit_command = any(word in question.lower() for word in ("command", "fix", "delete", "restart", "verify"))
        if broken_pod:
            namespace = broken_pod.get("namespace", "")
            name = broken_pod.get("name", "")
            state = next(
                (container for container in broken_pod.get("container_states", []) if container.get("reason")),
                {},
            )
            owner_references = broken_pod.get("owner_references") or []
            owner = owner_references[0] if owner_references else None
            image = state.get("image")
            command = f"kubectl get pod {name} -n {namespace}" if explicit_command else ""
            requested_delete = "delete" in question.lower()
            requested_restart = "restart" in question.lower()
            if requested_delete:
                if owner:
                    action_title = "Inspect the controller before deleting the Pod"
                    action_description = (
                        f"This Pod is managed by {owner.get('kind', 'a controller')} "
                        f"{owner.get('name', 'with unknown name')}. Fix or restart the controller instead of deleting the Pod directly."
                    )
                    command = f"kubectl get {str(owner.get('kind', 'resource')).lower()} {owner.get('name')} -n {namespace}"
                else:
                    action_title = "Review the standalone Pod before deleting it"
                    action_description = "No controller ownership was established. Review this destructive command before executing it."
                    command = f"kubectl delete pod {name} -n {namespace}"
            elif requested_restart:
                action_title = "Inspect the workload before restarting it"
                action_description = (
                    f"This Pod is controller-managed by {owner.get('kind')} {owner.get('name')}; "
                    "restart or fix the controller rather than deleting the Pod directly."
                    if owner
                    else "Controller ownership is uncertain; inspect the Pod before choosing a restart command."
                )
                command = (
                    f"kubectl get {str(owner.get('kind', 'resource')).lower()} {owner.get('name')} -n {namespace}"
                    if owner
                    else f"kubectl get pod {name} -n {namespace}"
                )
            else:
                action_title = "Inspect the workload before correcting the image"
                action_description = "Confirm the image name, tag, and controller ownership before making a change."
            result = {
                "status": "critical",
                "problem": {
                    "title": "ImagePullBackOff",
                    "resource_type": "Pod",
                    "resource_name": name,
                    "namespace": namespace,
                    "current_state": state.get("reason", "ImagePullBackOff"),
                    "impact": "One Pod is unable to start and cannot serve its workload.",
                },
                "root_cause": {
                    "summary": "The container image cannot be pulled because the configured image or tag is unavailable.",
                    "confidence": "high",
                    "evidence": [
                        f"Pod {name} is in {state.get('reason', 'ImagePullBackOff')}.",
                        "The container is waiting and has not started, so logs are unavailable.",
                        *([f"Configured image: {image}."] if image else []),
                        *[
                            event.get("message", "")
                            for event in events
                            if event.get("reason") in {"Failed", "BackOff", "FailedScheduling"}
                        ][:2],
                    ],
                },
                "recommended_actions": [
                    {
                        "priority": 1,
                        "title": action_title,
                        "description": action_description,
                        "command": command,
                        "risk": "high" if requested_delete else "medium",
                    }
                ],
                "what_not_to_do": [
                    "Review before executing — this changes cluster state." if requested_delete else "Do not delete the Pod blindly if it is managed by a controller.",
                    "Do not change RBAC or restart the entire cluster.",
                ],
                "verification": [
                    {
                        "description": "Check whether the Pod can pull the corrected image.",
                        "command": f"kubectl get pod {name} -n {namespace}",
                    }
                ],
                "limitations": [
                    (
                        f"Controller ownership was established as {owner.get('kind')} {owner.get('name')}."
                        if owner
                        else "Controller ownership was not established from the available Pod evidence."
                    ),
                    "Gemini analysis is unavailable; this is a conservative evidence-based fallback.",
                ],
            }
            return result

        result = _empty_incident()
        result["status"] = "warning" if warning else "healthy"
        result["problem"]["title"] = warning.get("reason", "Cluster requires review") if warning else "No critical problem detected"
        result["problem"]["current_state"] = "Warning events present" if warning else "Evidence collected"
        result["root_cause"]["summary"] = warning.get("message", "No specific root cause was established.") if warning else "No specific root cause was established from the supplied evidence."
        result["root_cause"]["evidence"] = [warning.get("message", "")] if warning else []
        result["limitations"].append("Gemini analysis is unavailable; this is a conservative evidence-based fallback.")
        return result

    def _normalize_result(self, result: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Accept only the public structured response shape from Gemini."""
        required = {"status", "problem", "root_cause", "recommended_actions", "what_not_to_do", "verification", "limitations"}
        if required.issubset(result):
            return {key: result[key] for key in required}
        logger.warning("Gemini returned a non-structured response; using evidence-based fallback.")
        return self._fallback_response("", context)

    def analyze(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Analyze Kubernetes evidence and return a structured troubleshooting result."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must be a non-empty string.")

        payload = context or {}
        if not isinstance(payload, dict):
            raise ValueError("Context must be a dictionary.")

        if not payload:
            return self._fallback_response(question, {})

        prompt = self._build_prompt(question, payload)

        if not self.gemini_client or not self.gemini_client.is_available():
            logger.warning("Gemini is unavailable; using conservative fallback analysis.")
            return self._fallback_response(question, payload)

        try:
            logger.info("Invoking Gemini analysis with collected Kubernetes evidence.")
            result = self.gemini_client.analyze(prompt)
            if isinstance(result, dict):
                return self._normalize_result(result, payload)
            return self._fallback_response(question, payload)
        except Exception as exc:
            logger.warning("Gemini analysis raised an error: %s", exc)
            return self._fallback_response(question, payload)

    def run(self) -> dict[str, str | bool]:
        """Entry point for the agent workflow in local development mode."""
        logger.info("Agent initialized with read-only mode enabled.")
        logger.info("Gemini analysis will use a read-only evidence-based workflow.")
        return self.health()
