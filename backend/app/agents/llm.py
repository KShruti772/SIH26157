"""
Local, air-gapped LLM client adapter for Module 6 — Local Agentic AI.

Connects strictly to a local model runner (e.g. Ollama at localhost:11434).
Contains NO cloud APIs, external endpoints, or telemetry.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from app.agents.config import (
    LOCAL_LLM_PROVIDER,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    LLM_TIMEOUT_SECONDS,
)


class LocalLLMError(RuntimeError):
    """Raised when the local LLM cannot be reached or returns an error."""
    pass


class LocalLLMClient:
    """
    Offline client for interacting with a local open-weight model via Ollama.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = LOCAL_LLM_MODEL,
        provider: str = LOCAL_LLM_PROVIDER,
        timeout: float = LLM_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = provider
        self.timeout = timeout

    def check_availability(self) -> bool:
        """
        Check if the local Ollama instance is reachable and responsive.
        """
        if self.provider.lower() != "ollama":
            return False

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"User-Agent": "SAT-SA-Airgapped-Agent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_json(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """
        Send prompt to local Ollama instance requesting JSON-structured output.
        """
        if not self.check_availability():
            raise LocalLLMError(
                f"Local LLM provider '{self.provider}' at '{self.base_url}' is currently unreachable."
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic, factual reasoning
                "top_p": 0.9,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res_body = resp.read().decode("utf-8")
                res_json = json.loads(res_body)
                raw_response = res_json.get("response", "{}")
                return json.loads(raw_response)
        except urllib.error.URLError as e:
            raise LocalLLMError(f"Connection to local LLM failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise LocalLLMError(f"Failed to decode JSON from local LLM response: {str(e)}")
        except Exception as e:
            raise LocalLLMError(f"Unexpected error executing local LLM query: {str(e)}")
