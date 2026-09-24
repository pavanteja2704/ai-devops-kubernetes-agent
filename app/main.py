"""Application entry point for the AI DevOps Kubernetes agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent.agent import Agent, KubernetesEvidenceError
from app.gemini.client import GeminiClient
from app.config.settings import Settings
from app.kubernetes.client import KubernetesClient
from app.kubernetes.deployments import DeploymentsCollector
from app.kubernetes.events import EventsCollector
from app.kubernetes.logs import LogsCollector
from app.kubernetes.namespaces import NamespacesCollector
from app.kubernetes.nodes import NodesCollector
from app.kubernetes.pods import PodsCollector
from app.kubernetes.services import ServicesCollector

logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request body for the read-only Kubernetes analysis API."""

    question: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


def configure_logging(level: str) -> None:
    """Configure logging in a safe, non-secret-leaking manner."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )


def get_settings() -> Settings:
    """Load settings from the local .env file when present."""
    load_dotenv(Path(".env"))
    return Settings()


def create_app(
    settings: Settings | None = None,
    kubernetes_client: KubernetesClient | None = None,
    gemini_client: GeminiClient | None = None,
) -> FastAPI:
    """Create the FastAPI application with health, Kubernetes, and AI analysis endpoints."""
    app_settings = settings or get_settings()
    app = FastAPI(title="AI DevOps Kubernetes Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    client = kubernetes_client or KubernetesClient()
    agent = Agent(app_settings, gemini_client=gemini_client, kubernetes_client=client)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"status": "ok", "message": "AI DevOps Kubernetes Agent is running"}

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/kubernetes/status")
    def kubernetes_status() -> dict[str, object]:
        return client.get_status()

    @app.get("/kubernetes/nodes")
    def kubernetes_nodes() -> list[dict[str, object]]:
        return NodesCollector(client).get_nodes()

    @app.get("/kubernetes/namespaces")
    def kubernetes_namespaces() -> list[str]:
        return NamespacesCollector(client).get_namespaces()

    @app.get("/kubernetes/pods")
    def kubernetes_pods() -> list[dict[str, object]]:
        return PodsCollector(client).get_pods()

    @app.get("/kubernetes/deployments")
    def kubernetes_deployments() -> list[dict[str, object]]:
        return DeploymentsCollector(client).get_deployments()

    @app.get("/kubernetes/services")
    def kubernetes_services() -> list[dict[str, object]]:
        return ServicesCollector(client).get_services()

    @app.get("/kubernetes/events")
    def kubernetes_events() -> list[dict[str, object]]:
        return EventsCollector(client).get_events()

    @app.get("/kubernetes/logs")
    def kubernetes_logs(
        namespace: str = Query(..., description="Namespace for the pod"),
        pod_name: str = Query(..., description="Pod name"),
        container_name: str | None = Query(default=None, description="Optional container name"),
    ) -> dict[str, str]:
        logs = LogsCollector(client).get_pod_logs(namespace, pod_name, container_name)
        if "not available" in logs.lower() or "unable" in logs.lower():
            raise HTTPException(status_code=503, detail=logs)
        return {"namespace": namespace, "pod_name": pod_name, "logs": logs}

    @app.post("/analyze")
    def analyze(payload: AnalysisRequest) -> dict[str, Any]:
        try:
            evidence = agent.collect_evidence(client)
            if payload.context:
                evidence["request_context"] = payload.context
            return agent.analyze(payload.question, evidence)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KubernetesEvidenceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    app.state.settings = app_settings
    app.state.agent = agent
    app.state.kubernetes_client = client
    return app


def main() -> None:
    """Run the application in local development mode without live cloud dependencies."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("Starting AI DevOps Kubernetes agent in read-only mode.")
    logger.info("Project environment: %s", settings.app_env)

    uvicorn.run(app=create_app(settings), host="127.0.0.1", port=8000, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
