"""Unit tests for provider registry and base classes.

Tests cover:
- Provider registry creation and singleton behavior
- Provider registration and retrieval
- Credential loading from environment
- Provider type filtering
- Error handling for missing credentials
"""

import pytest
import os
from typing import Any
from unittest.mock import Mock, patch

from app.providers import (
    ProviderRegistry,
    CredentialLoader,
    Provider,
    ProviderCapabilities,
    ProviderType,
    ExecutionMetadata,
    ProviderError,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
)


class MockProvider(Provider):
    """Mock provider for testing.
    
    Minimal implementation of Provider ABC for testing purposes.
    """

    def __init__(self, provider_id: str, credentials: dict[str, Any]) -> None:
        """Initialize mock provider."""
        super().__init__(provider_id, credentials)
        self.model = credentials.get("model", "test-model")
        self.executed_prompts: list[str] = []

    def _validate_credentials(self) -> None:
        """Validate credentials (minimal for testing)."""
        if "api_key" not in self.credentials:
            raise ValueError("api_key required")

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return mock capabilities."""
        return ProviderCapabilities(
            max_input_tokens=4096,
            max_output_tokens=2048,
            supports_streaming=True,
            supports_functions=True,
        )

    @property
    def pricing_per_1k_tokens(self) -> dict[str, float]:
        """Return mock pricing."""
        return {"input": 0.001, "output": 0.002}

    async def execute(self, prompt: str, metadata=None, **kwargs) -> Any:
        """Mock execution."""
        self.executed_prompts.append(prompt)
        from app.providers.base import ProviderResponse
        return ProviderResponse(
            output="Mock response",
            tokens_used=100,
            tokens_input=50,
            tokens_output=50,
            cost_usd=0.10,
            latency_ms=100,
            model_used=self.model,
            provider_id=self.provider_id,
        )

    async def execute_streaming(self, prompt: str, metadata=None, **kwargs):
        """Mock streaming execution."""
        yield "Mock "
        yield "response"

    def count_tokens(self, text: str) -> int:
        """Mock token counting."""
        return len(text.split())

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Mock cost estimation."""
        pricing = self.pricing_per_1k_tokens
        return (
            input_tokens / 1000 * pricing["input"] +
            output_tokens / 1000 * pricing["output"]
        )

    def get_available_models(self) -> list[str]:
        """Return mock available models."""
        return [self.model, "test-model-2", "test-model-3"]


class TestProviderRegistry:
    """Tests for ProviderRegistry singleton."""

    def setup_method(self):
        """Reset registry before each test."""
        ProviderRegistry.reset()

    def teardown_method(self):
        """Clean up after each test."""
        ProviderRegistry.reset()

    def test_singleton_pattern(self):
        """Test that registry uses singleton pattern."""
        registry1 = ProviderRegistry.instance()
        registry2 = ProviderRegistry.instance()
        
        assert registry1 is registry2, "Registry should be same instance"

    def test_register_provider(self):
        """Test registering a provider."""
        registry = ProviderRegistry.instance()
        provider = MockProvider("test", {"api_key": "test-key", "model": "test"})
        
        registry.register("test", provider, ProviderType.LLM)
        
        assert registry.is_registered("test")
        assert registry.get_provider("test") is provider

    def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        registry = ProviderRegistry.instance()
        
        for i in range(3):
            provider = MockProvider(
                f"test-{i}",
                {"api_key": f"key-{i}", "model": f"model-{i}"}
            )
            registry.register(f"test-{i}", provider)
        
        assert len(registry.list_providers()) == 3
        assert all(registry.is_registered(f"test-{i}") for i in range(3))

    def test_get_nonexistent_provider_raises_keyerror(self):
        """Test that getting nonexistent provider raises KeyError."""
        registry = ProviderRegistry.instance()
        
        with pytest.raises(KeyError, match="not registered"):
            registry.get_provider("nonexistent")

    def test_register_invalid_type_raises_typeerror(self):
        """Test that registering non-Provider object raises TypeError."""
        registry = ProviderRegistry.instance()
        
        with pytest.raises(TypeError, match="must inherit from Provider"):
            registry.register("invalid", "not a provider")

    def test_list_providers(self):
        """Test listing all registered providers."""
        registry = ProviderRegistry.instance()
        
        provider1 = MockProvider("p1", {"api_key": "k1", "model": "m1"})
        provider2 = MockProvider("p2", {"api_key": "k2", "model": "m2"})
        
        registry.register("p1", provider1)
        registry.register("p2", provider2)
        
        providers = registry.list_providers()
        assert set(providers) == {"p1", "p2"}

    def test_get_provider_by_type(self):
        """Test filtering providers by type."""
        registry = ProviderRegistry.instance()
        
        llm_provider = MockProvider("llm", {"api_key": "key", "model": "m"})
        registry.register("llm", llm_provider, ProviderType.LLM)
        
        llm_providers = registry.get_provider_by_type(ProviderType.LLM)
        assert len(llm_providers) == 1
        assert llm_providers[0] is llm_provider

    def test_list_models(self):
        """Test listing models from all providers."""
        registry = ProviderRegistry.instance()
        
        provider = MockProvider("test", {"api_key": "key", "model": "test-model"})
        registry.register("test", provider)
        
        models = registry.list_models()
        assert "test" in models
        assert "test-model" in models["test"]
        assert len(models["test"]) == 3  # Mock returns 3 models

    def test_unregister_provider(self):
        """Test unregistering a provider."""
        registry = ProviderRegistry.instance()
        
        provider = MockProvider("test", {"api_key": "key", "model": "m"})
        registry.register("test", provider)
        assert registry.is_registered("test")
        
        registry.unregister("test")
        assert not registry.is_registered("test")

    def test_unregister_nonexistent_raises_keyerror(self):
        """Test that unregistering nonexistent provider raises KeyError."""
        registry = ProviderRegistry.instance()
        
        with pytest.raises(KeyError, match="not registered"):
            registry.unregister("nonexistent")

    def test_get_stats(self):
        """Test getting registry statistics."""
        registry = ProviderRegistry.instance()
        
        provider = MockProvider("test", {"api_key": "key", "model": "m"})
        registry.register("test", provider, ProviderType.LLM)
        
        stats = registry.get_stats()
        assert stats["provider_count"] == 1
        assert "test" in stats["providers"]
        assert stats["models_available"] == 3

    def test_repr(self):
        """Test string representation."""
        registry = ProviderRegistry.instance()
        
        provider = MockProvider("test", {"api_key": "key", "model": "m"})
        registry.register("test", provider)
        
        repr_str = repr(registry)
        assert "ProviderRegistry" in repr_str
        assert "test" in repr_str


class TestCredentialLoader:
    """Tests for CredentialLoader."""

    def test_load_openai_credentials(self):
        """Test loading OpenAI credentials from environment."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test123",
            "OPENAI_MODEL": "gpt-4",
        }):
            creds = CredentialLoader.load_provider_credentials("openai")
            
            assert creds["api_key"] == "sk-test123"
            assert creds["model"] == "gpt-4"

    def test_load_missing_required_credentials_raises_error(self):
        """Test that missing required credentials raise ValueError."""
        with patch.dict(os.environ, clear=True):
            with pytest.raises(ValueError, match="Missing required"):
                CredentialLoader.load_provider_credentials("openai")

    def test_load_anthropic_credentials(self):
        """Test loading Anthropic credentials."""
        with patch.dict(os.environ, {
            "ANTHROPIC_API_KEY": "sk-ant-test123",
            "ANTHROPIC_MODEL": "claude-3-sonnet",
        }):
            creds = CredentialLoader.load_provider_credentials("anthropic")
            
            assert creds["api_key"] == "sk-ant-test123"
            assert creds["model"] == "claude-3-sonnet"

    def test_load_all_providers(self):
        """Test loading credentials for multiple providers."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-openai",
            "OPENAI_MODEL": "gpt-4",
            "ANTHROPIC_API_KEY": "sk-ant-anthropic",
            "ANTHROPIC_MODEL": "claude-3",
        }):
            creds = CredentialLoader.load_all_providers(["openai", "anthropic"])
            
            assert "openai" in creds
            assert "anthropic" in creds
            assert creds["openai"]["api_key"] == "sk-openai"
            assert creds["anthropic"]["api_key"] == "sk-ant-anthropic"

    def test_load_all_providers_skips_missing(self):
        """Test that load_all_providers skips unconfigured providers."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4",
        }):
            creds = CredentialLoader.load_all_providers(["openai", "anthropic"])
            
            assert "openai" in creds
            assert "anthropic" not in creds

    def test_is_provider_configured(self):
        """Test checking if provider is configured."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4",
        }):
            assert CredentialLoader.is_provider_configured("openai")
            assert not CredentialLoader.is_provider_configured("anthropic")

    def test_get_configured_providers(self):
        """Test getting list of configured providers."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-openai",
            "OPENAI_MODEL": "gpt-4",
            "ANTHROPIC_API_KEY": "sk-ant-anthropic",
            "ANTHROPIC_MODEL": "claude-3",
        }):
            configured = CredentialLoader.get_configured_providers()
            
            assert set(configured) >= {"openai", "anthropic"}

    def test_validate_credentials_success(self):
        """Test successful credential validation."""
        is_valid, msg = CredentialLoader.validate_credentials(
            "openai",
            {"api_key": "sk-test123", "model": "gpt-4"}
        )
        
        assert is_valid
        assert msg == "OK"

    def test_validate_credentials_missing_keys(self):
        """Test validation fails with missing required keys."""
        is_valid, msg = CredentialLoader.validate_credentials(
            "openai",
            {"model": "gpt-4"}  # Missing api_key
        )
        
        assert not is_valid
        assert "Missing required keys" in msg

    def test_validate_credentials_empty_value(self):
        """Test validation fails with empty credential value."""
        is_valid, msg = CredentialLoader.validate_credentials(
            "openai",
            {"api_key": "", "model": "gpt-4"}
        )
        
        assert not is_valid

    def test_validate_openai_api_key_format(self):
        """Test OpenAI API key format validation."""
        # Valid OpenAI key format
        is_valid, msg = CredentialLoader.validate_credentials(
            "openai",
            {"api_key": "sk-1234567890"}
        )
        assert is_valid

        # Invalid format
        is_valid, msg = CredentialLoader.validate_credentials(
            "openai",
            {"api_key": "invalid-key"}
        )
        assert not is_valid
        assert "should start with 'sk-'" in msg

    def test_validate_anthropic_api_key_format(self):
        """Test Anthropic API key format validation."""
        # Valid Anthropic key format
        is_valid, msg = CredentialLoader.validate_credentials(
            "anthropic",
            {"api_key": "sk-ant-1234567890"}
        )
        assert is_valid

        # Invalid format
        is_valid, msg = CredentialLoader.validate_credentials(
            "anthropic",
            {"api_key": "sk-1234567890"}
        )
        assert not is_valid
        assert "should start with 'sk-ant-'" in msg


class TestProviderExceptions:
    """Tests for provider exception types."""

    def test_provider_error(self):
        """Test base ProviderError exception."""
        error = ProviderError(
            provider_id="test",
            message="Test error",
            is_retryable=True,
        )
        
        assert error.provider_id == "test"
        assert error.is_retryable is True

    def test_authentication_error_not_retryable(self):
        """Test AuthenticationError is not retryable."""
        error = AuthenticationError(provider_id="test")
        
        assert error.is_retryable is False

    def test_rate_limit_error_is_retryable(self):
        """Test RateLimitError is retryable and includes retry_after."""
        error = RateLimitError(
            provider_id="test",
            retry_after_seconds=60,
        )
        
        assert error.is_retryable is True
        assert error.retry_after_seconds == 60

    def test_unavailable_error_is_retryable(self):
        """Test ProviderUnavailableError is retryable."""
        error = ProviderUnavailableError(provider_id="test")
        
        assert error.is_retryable is True


class TestMockProvider:
    """Tests for MockProvider test implementation."""

    def test_mock_provider_properties(self):
        """Test mock provider returns expected properties."""
        provider = MockProvider("test", {
            "api_key": "test-key",
            "model": "test-model"
        })
        
        assert provider.provider_id == "test"
        assert provider.model == "test-model"
        assert provider.capabilities.max_input_tokens == 4096

    @pytest.mark.asyncio
    async def test_mock_provider_execute(self):
        """Test mock provider execution."""
        provider = MockProvider("test", {
            "api_key": "test-key",
            "model": "test-model"
        })
        
        response = await provider.execute("Test prompt")
        
        assert response.output == "Mock response"
        assert response.tokens_used == 100
        assert response.provider_id == "test"

    def test_mock_provider_token_counting(self):
        """Test mock provider token counting."""
        provider = MockProvider("test", {
            "api_key": "test-key",
            "model": "test-model"
        })
        
        tokens = provider.count_tokens("one two three")
        assert tokens == 3

    def test_mock_provider_cost_estimation(self):
        """Test mock provider cost estimation."""
        provider = MockProvider("test", {
            "api_key": "test-key",
            "model": "test-model"
        })
        
        # 1000 input tokens @ 0.001 + 1000 output tokens @ 0.002 = $0.003
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost == 0.003
