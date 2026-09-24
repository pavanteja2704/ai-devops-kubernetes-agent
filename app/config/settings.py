"""Application settings and environment variable handling."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Store environment-driven application configuration."""

    app_env: str = "development"
    read_only_mode: bool = True
    kubeconfig_path: str = "~/.kube/config"
    kubernetes_context: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    log_level: str = "INFO"

    def __init__(self) -> None:
        object.__setattr__(self, "app_env", os.getenv("APP_ENV", self.app_env))
        object.__setattr__(self, "read_only_mode", str(os.getenv("READ_ONLY_MODE", "true")).lower() == "true")
        object.__setattr__(self, "kubeconfig_path", os.getenv("KUBECONFIG_PATH", self.kubeconfig_path))
        object.__setattr__(self, "kubernetes_context", os.getenv("KUBERNETES_CONTEXT", self.kubernetes_context))
        object.__setattr__(self, "google_cloud_project", os.getenv("GOOGLE_CLOUD_PROJECT", self.google_cloud_project))
        object.__setattr__(self, "google_cloud_location", os.getenv("GOOGLE_CLOUD_LOCATION", self.google_cloud_location))
        object.__setattr__(self, "gemini_api_key", os.getenv("GEMINI_API_KEY", self.gemini_api_key))
        object.__setattr__(self, "gemini_model", os.getenv("GEMINI_MODEL", self.gemini_model))
        object.__setattr__(self, "log_level", os.getenv("LOG_LEVEL", self.log_level).upper())

    def validate(self) -> None:
        """Validate mandatory values for local development."""
        if not self.app_env:
            raise ValueError("APP_ENV cannot be empty.")
        if not self.log_level:
            raise ValueError("LOG_LEVEL cannot be empty.")
