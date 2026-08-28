"""
Provider-independent AI abstraction.

The rest of the app (app/ai/engine.py) talks only to `AIProvider`, never to
a specific vendor SDK. This makes it possible to swap OpenAI for Anthropic,
a local model, etc. by adding a new subclass — nothing else in the codebase
needs to change.
"""
from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when the underlying LLM call fails (network, auth, rate limit, etc.)."""


class AIProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a system+user prompt to the LLM and return the raw text response.
        Implementations should raise AIProviderError on failure rather than
        letting vendor-specific exceptions leak out.
        """
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """Default provider, backed by the OpenAI-compatible /chat/completions API."""

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise AIProviderError("No API key configured for OpenAIProvider.")
        # Imported lazily so the package is only required when this provider
        # is actually instantiated (keeps rule-checker-only mode dependency-light).
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001 - intentionally broad, wrapped below
            raise AIProviderError(f"OpenAI API call failed: {e}") from e


def get_ai_provider(api_key: str, model: str) -> AIProvider:
    """
    Factory for the configured AI provider.
    Currently only OpenAI is implemented; this is the single place to add
    branching logic (e.g. by AI_PROVIDER env var) for additional vendors later.
    """
    return OpenAIProvider(api_key=api_key, model=model)
