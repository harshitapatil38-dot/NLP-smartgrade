"""
LLM Service — Provider abstraction for language model interactions.

Architecture:
    RAG Service (future)
         ↓
    LLMService (this module — factory + interface)
         ↓
    Concrete Provider (e.g. GeminiProvider, OpenAIProvider)

The rest of the application calls LLMService.get_provider() and uses
the returned BaseLLMProvider instance. The concrete provider and model
are selected via environment variables, so the LLM backend can be
swapped without touching any other code.
"""

import importlib
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class LLMServiceError(Exception):
    """Base exception for all LLM service errors."""
    pass


class LLMConfigurationError(LLMServiceError):
    """Raised when required configuration (API key, provider, model) is missing or invalid."""
    pass


class LLMProviderError(LLMServiceError):
    """Raised when an LLM API call fails (network, rate-limit, server error, etc.)."""
    pass


class LLMResponseError(LLMServiceError):
    """Raised when the provider returns a response that cannot be parsed."""
    pass


# ---------------------------------------------------------------------------
# Abstract base provider
# ---------------------------------------------------------------------------

class BaseLLMProvider(ABC):
    """
    Contract that every LLM provider must implement.

    Parameters
    ----------
    model : str
        The model identifier (e.g. ``gemini-2.0-flash``, ``gpt-4o-mini``).
    api_key : str
        The secret API key for the provider.
    """

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_question: str,
        context: str,
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate an answer given a system prompt, user question, and
        retrieved context.

        Returns the generated text as a plain string.
        """
        ...


# ---------------------------------------------------------------------------
# Concrete providers
# ---------------------------------------------------------------------------

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the ``google-generativeai`` SDK."""

    def generate(
        self,
        system_prompt: str,
        user_question: str,
        context: str,
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            genai = importlib.import_module("google.generativeai")
        except ImportError:
            raise LLMConfigurationError(
                "The 'google-generativeai' package is required for the Gemini provider. "
                "Install it with: pip install google-generativeai"
            )

        try:
            genai.configure(api_key=self.api_key)

            generation_config = {"temperature": temperature}
            if max_tokens is not None:
                generation_config["max_output_tokens"] = max_tokens

            model = genai.GenerativeModel(
                model_name=self.model,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )

            prompt = (
                f"Context:\n{context}\n\n"
                f"Question: {user_question}"
            )

            response = model.generate_content(prompt)

            if not response or not response.text:
                raise LLMResponseError("Gemini returned an empty response.")

            return response.text

        except LLMServiceError:
            raise
        except Exception as exc:
            # Wrap any SDK / network error so callers never see raw provider details
            raise LLMProviderError(f"Gemini API call failed: {type(exc).__name__}") from exc



class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible provider (GPT-4o, GPT-4o-mini, etc.)."""

    def generate(
        self,
        system_prompt: str,
        user_question: str,
        context: str,
        *,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            openai = importlib.import_module("openai")
        except ImportError:
            raise LLMConfigurationError(
                "The 'openai' package is required for the OpenAI provider. "
                "Install it with: pip install openai"
            )

        try:
            client = openai.OpenAI(api_key=self.api_key)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_question}"},
            ]

            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            response = client.chat.completions.create(**kwargs)

            if not response.choices:
                raise LLMResponseError("OpenAI returned no choices.")

            return response.choices[0].message.content

        except LLMServiceError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"OpenAI API call failed: {type(exc).__name__}") from exc


# ---------------------------------------------------------------------------
# Provider registry & factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


class LLMService:
    """
    Factory that reads configuration from environment variables and
    returns the appropriate ``BaseLLMProvider`` instance.

    Environment variables
    ---------------------
    LLM_PROVIDER : str   — provider name (e.g. ``gemini``, ``openai``)
    LLM_MODEL    : str   — model identifier
    LLM_API_KEY  : str   — secret API key
    """

    @staticmethod
    def get_provider() -> BaseLLMProvider:
        provider_name = os.environ.get("LLM_PROVIDER", "").strip().lower()
        model = os.environ.get("LLM_MODEL", "").strip()
        api_key = os.environ.get("LLM_API_KEY", "").strip()

        if not provider_name:
            raise LLMConfigurationError("LLM_PROVIDER environment variable is not set.")

        if not api_key:
            raise LLMConfigurationError("LLM_API_KEY environment variable is not set.")

        if not model:
            raise LLMConfigurationError("LLM_MODEL environment variable is not set.")

        provider_cls = _PROVIDERS.get(provider_name)
        if provider_cls is None:
            supported = ", ".join(sorted(_PROVIDERS.keys()))
            raise LLMConfigurationError(
                f"Unsupported LLM provider: '{provider_name}'. Supported: {supported}"
            )

        return provider_cls(model=model, api_key=api_key)
