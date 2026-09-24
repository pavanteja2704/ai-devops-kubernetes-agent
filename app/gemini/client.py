"""Gemini client abstraction for Kubernetes troubleshooting analysis."""

from __future__ import annotations

import logging
import os
import json
import re
from typing import Any

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:  # pragma: no cover - dependency is optional for tests.
    genai = None


class GeminiClient:
    """Wraps the official Gemini SDK for cluster problem analysis.

    The client is safe to instantiate without real credentials. If the SDK is not
    available or no credential is configured, the client reports unavailable and
    the agent falls back to evidence-based analysis.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        project_id: str | None = None,
        location: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self._client: Any | None = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the SDK client only when credentials are present."""
        if not self.api_key and not self.project_id:
            logger.info("Gemini client not configured; model analysis will use local fallback logic.")
            return

        if genai is None:
            logger.warning("Google Gen AI SDK is not installed; Gemini analysis is unavailable.")
            return

        try:
            if self.api_key:
                self._client = genai.Client(api_key=self.api_key)
            else:
                self._client = genai.Client(vertexai=True, project=self.project_id, location=self.location)
            logger.info("Gemini client initialized for model '%s'.", self.model_name)
        except Exception as exc:  # pragma: no cover - environment-dependent path.
            logger.warning("Gemini client initialization failed: %s", exc)
            self._client = None

    def is_available(self) -> bool:
        """Return whether Gemini is ready to analyze data."""
        return self._client is not None

    def analyze(self, prompt: str) -> dict[str, Any]:
        """Send the supplied prompt to Gemini and return a structured result."""
        if self._client is None:
            raise RuntimeError("Gemini is unavailable; no valid configuration was detected.")

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            text = getattr(response, "text", "") or ""
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Gemini returned invalid structured JSON.") from exc
            if not isinstance(parsed, dict):
                raise RuntimeError("Gemini returned structured JSON with an invalid root value.")
            return parsed
        except Exception as exc:  # pragma: no cover - depends on real runtime configuration.
            logger.warning("Gemini analysis request failed: %s", exc)
            raise RuntimeError(f"Gemini analysis request failed: {exc}") from exc
