"""
Tests for Step 6A — LLM Provider Foundation.

All tests use mocks. No real LLM API calls are made.
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from app.services.llm_service import (
    LLMService,
    BaseLLMProvider,
    GeminiProvider,
    OpenAIProvider,
    LLMConfigurationError,
    LLMProviderError,
    LLMResponseError,
)


# ---------------------------------------------------------------------------
# 1. Provider configuration loads correctly
# ---------------------------------------------------------------------------

@patch.dict(os.environ, {
    "LLM_PROVIDER": "gemini",
    "LLM_MODEL": "gemini-2.0-flash",
    "LLM_API_KEY": "test-key-123",
})
def test_provider_configuration_loads_gemini():
    provider = LLMService.get_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.0-flash"
    assert provider.api_key == "test-key-123"


@patch.dict(os.environ, {
    "LLM_PROVIDER": "openai",
    "LLM_MODEL": "gpt-4o-mini",
    "LLM_API_KEY": "sk-test-key",
})
def test_provider_configuration_loads_openai():
    provider = LLMService.get_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-4o-mini"
    assert provider.api_key == "sk-test-key"


# ---------------------------------------------------------------------------
# 2. Missing API key is handled correctly
# ---------------------------------------------------------------------------

@patch.dict(os.environ, {
    "LLM_PROVIDER": "gemini",
    "LLM_MODEL": "gemini-2.0-flash",
    "LLM_API_KEY": "",
}, clear=False)
def test_missing_api_key_raises_error():
    # Ensure LLM_API_KEY is effectively empty
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        LLMService.get_provider()


@patch.dict(os.environ, {
    "LLM_PROVIDER": "gemini",
    "LLM_MODEL": "",
    "LLM_API_KEY": "key",
}, clear=False)
def test_missing_model_raises_error():
    with pytest.raises(LLMConfigurationError, match="LLM_MODEL"):
        LLMService.get_provider()


@patch.dict(os.environ, {
    "LLM_PROVIDER": "",
    "LLM_MODEL": "model",
    "LLM_API_KEY": "key",
}, clear=False)
def test_missing_provider_raises_error():
    with pytest.raises(LLMConfigurationError, match="LLM_PROVIDER"):
        LLMService.get_provider()


# ---------------------------------------------------------------------------
# 3. Unsupported provider is rejected
# ---------------------------------------------------------------------------

@patch.dict(os.environ, {
    "LLM_PROVIDER": "anthropic",
    "LLM_MODEL": "claude-4",
    "LLM_API_KEY": "key",
})
def test_unsupported_provider_raises_error():
    with pytest.raises(LLMConfigurationError, match="Unsupported LLM provider"):
        LLMService.get_provider()


# ---------------------------------------------------------------------------
# 4. LLM request is constructed correctly (Gemini)
# ---------------------------------------------------------------------------

@patch("app.services.llm_service.GeminiProvider.generate")
@patch.dict(os.environ, {
    "LLM_PROVIDER": "gemini",
    "LLM_MODEL": "gemini-2.0-flash",
    "LLM_API_KEY": "test-key",
})
def test_gemini_request_constructed_correctly(mock_generate):
    mock_generate.return_value = "Mocked answer"

    provider = LLMService.get_provider()
    result = provider.generate(
        system_prompt="You are a college assistant.",
        user_question="What are the library hours?",
        context="The library is open from 9 AM to 5 PM.",
    )

    mock_generate.assert_called_once_with(
        system_prompt="You are a college assistant.",
        user_question="What are the library hours?",
        context="The library is open from 9 AM to 5 PM.",
    )
    assert result == "Mocked answer"


# ---------------------------------------------------------------------------
# 5. Mock LLM response is returned correctly (OpenAI)
# ---------------------------------------------------------------------------

@patch("app.services.llm_service.OpenAIProvider.generate")
@patch.dict(os.environ, {
    "LLM_PROVIDER": "openai",
    "LLM_MODEL": "gpt-4o-mini",
    "LLM_API_KEY": "sk-test",
})
def test_openai_mock_response_returned(mock_generate):
    mock_generate.return_value = "The library is open 9 AM to 5 PM on weekdays."

    provider = LLMService.get_provider()
    result = provider.generate(
        system_prompt="Answer based on context.",
        user_question="Library hours?",
        context="Library: 9 AM – 5 PM weekdays.",
    )

    assert result == "The library is open 9 AM to 5 PM on weekdays."


# ---------------------------------------------------------------------------
# 6. LLM provider failures are handled correctly
# ---------------------------------------------------------------------------

def test_gemini_provider_wraps_sdk_errors():
    """Verify that raw SDK exceptions are wrapped in LLMProviderError."""
    provider = GeminiProvider(model="gemini-2.0-flash", api_key="fake-key")

    # Mock the google.generativeai module so we don't need it installed
    mock_genai = MagicMock()
    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.side_effect = RuntimeError("Network timeout")
    mock_genai.GenerativeModel.return_value = mock_model_instance

    with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": MagicMock()}):
        with pytest.raises(LLMProviderError, match="Gemini API call failed"):
            provider.generate(
                system_prompt="test",
                user_question="test",
                context="test",
            )


def test_openai_provider_wraps_sdk_errors():
    """Verify that raw SDK exceptions are wrapped in LLMProviderError."""
    provider = OpenAIProvider(model="gpt-4o-mini", api_key="fake-key")

    mock_openai = MagicMock()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = ConnectionError("API unreachable")
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict("sys.modules", {"openai": mock_openai}):
        with pytest.raises(LLMProviderError, match="OpenAI API call failed"):
            provider.generate(
                system_prompt="test",
                user_question="test",
                context="test",
            )


def test_gemini_empty_response_raises_response_error():
    """Verify that an empty Gemini response raises LLMResponseError."""
    provider = GeminiProvider(model="gemini-2.0-flash", api_key="fake-key")

    mock_genai = MagicMock()
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""  # empty
    mock_model_instance.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model_instance

    with patch.dict("sys.modules", {"google.generativeai": mock_genai, "google": MagicMock()}):
        with pytest.raises(LLMResponseError, match="empty response"):
            provider.generate(
                system_prompt="test",
                user_question="test",
                context="test",
            )


def test_provider_is_instance_of_base():
    """All providers must inherit from BaseLLMProvider."""
    assert issubclass(GeminiProvider, BaseLLMProvider)
    assert issubclass(OpenAIProvider, BaseLLMProvider)

    provider = GeminiProvider(model="m", api_key="k")
    assert isinstance(provider, BaseLLMProvider)
