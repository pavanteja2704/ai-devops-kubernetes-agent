"""Kubernetes client abstraction for local development and future GKE use."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.config.config_exception import ConfigException

logger = logging.getLogger(__name__)


class KubernetesClient:
    """Read-only Kubernetes client wrapper.

    Supports local kubeconfig authentication and in-cluster configuration for
    future GKE deployment. It never performs write or mutating operations.
    """

    def __init__(self, kubeconfig_path: str | None = None, context: str | None = None) -> None:
        self.kubeconfig_path = kubeconfig_path or os.getenv("KUBECONFIG_PATH", "~/.kube/config")
        self.context = context or os.getenv("KUBERNETES_CONTEXT")
        self.core_v1: k8s_client.CoreV1Api | None = None
        self.apps_v1: k8s_client.AppsV1Api | None = None
        self.available = False
        self.message = "Kubernetes cluster is not available"
        self.last_error: str | None = None
        self._initialize()

    def _initialize(self) -> None:
        """Attempt to load either a local kubeconfig or in-cluster config."""
        try:
            config_path = str(Path(self.kubeconfig_path).expanduser()) if self.kubeconfig_path else None
            if config_path and os.path.exists(config_path):
                k8s_config.load_kube_config(context=self.context, config_file=config_path)
            elif self.context:
                k8s_config.load_kube_config(context=self.context)
            else:
                try:
                    k8s_config.load_kube_config()
                except ConfigException:
                    k8s_config.load_incluster_config()

            self.available = True
            self.message = "Kubernetes cluster is available"
            self.last_error = None
            self.core_v1 = k8s_client.CoreV1Api()
            self.apps_v1 = k8s_client.AppsV1Api()
            logger.info("Kubernetes client initialized successfully for context '%s'.", self.context or "default")
        except (ConfigException, FileNotFoundError, OSError) as exc:
            self.available = False
            self.message = "Kubernetes cluster is not available"
            self.last_error = str(exc)
            logger.warning("Kubernetes connectivity unavailable: %s", exc)

    def is_available(self) -> bool:
        """Return whether a valid Kubernetes client configuration is available."""
        return self.available

    def connect(self) -> dict[str, Any]:
        """Return a status payload instead of failing the application."""
        if not self.available:
            logger.warning("Kubernetes client cannot connect: %s", self.last_error or "no configuration found")
            return self.get_status()

        logger.info("Kubernetes connection ready for read-only inspection.")
        return self.get_status()

    def get_status(self) -> dict[str, Any]:
        """Return a structured status payload for the health endpoint."""
        return {
            "available": self.available,
            "message": self.message,
            "context": self.context or "default",
        }

    def get_cluster_info(self) -> dict[str, Any]:
        """Collect read-only cluster metadata when available."""
        if not self.available or self.core_v1 is None:
            return {
                "available": False,
                "message": "Kubernetes cluster is not available",
                "context": self.context or "default",
                "error": self.last_error or "No cluster configuration found.",
            }

        try:
            version = self.core_v1.api_client.call_api(
                "/version",
                "GET",
                _request_timeout=10,
            )
            return {
                "available": True,
                "message": "Kubernetes cluster is available",
                "context": self.context or "default",
                "version": version,
            }
        except Exception as exc:
            logger.warning("Unable to fetch Kubernetes version information: %s", exc)
            return {
                "available": True,
                "message": "Kubernetes cluster is available but version metadata is unavailable",
                "context": self.context or "default",
                "error": str(exc),
            }
