"""Unit tests for Anthropic provider implementation.

Tests cover:
- Provider initialization and validation
- Token counting accuracy
- Cost calculation
- Model capabilities
- Error handling (auth, rate limits, service errors)
- Retry logic
- Streaming responses
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from httpx import HTTPStatusError, RequestError, Response, Request

from app.providers.anthropic_provider_new import AnthropicProvider
from app.providers.base import (
    ExecutionMetadata,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
    ProviderError,
)


class TestAnthropicProviderInitialization:
    """Tests for Anthropic provider initialization."""

    def test_init_with_valid_api_key(self):
        """Test initializing provider with valid API key."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-sonnet-20240229"
        )
        
        assert provider.api_key == "sk-ant-test123"
        assert provider.model == "claude-3-sonnet-20240229"
        assert provider.provider_id == "anthropic"

    def test_init_with_default_model(self):
        """Test that model defaults to claude-3-sonnet."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        assert provider.model == AnthropicProvider.DEFAULT_MODEL

    def test_init_with_invalid_api_key_format(self):
        """Test that invalid API key format raises ValueError."""
        with pytest.raises(ValueError, match="sk-ant-"):
            AnthropicProvider(api_key="sk-invalid", model="claude-3-sonnet")

    def test_init_with_unsupported_model(self):
        """Test that unsupported model raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            AnthropicProvider(
                api_key="sk-ant-test123",
                model="unknown-model"
            )

    def test_init_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError):
            AnthropicProvider(api_key="", model="claude-3-sonnet")

    def test_init_with_model_alias(self):
        """Test initialization with model alias."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-sonnet"  # Alias
        )
        
        assert provider.model == "claude-3-sonnet"


class TestAnthropicProviderCapabilities:
    """Tests for provider capabilities and pricing."""

    def test_capabilities_opus(self):
        """Test Claude 3 Opus capabilities."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-opus-20240229"
        )
        
        caps = provider.capabilities
        assert caps.max_input_tokens > 0
        assert caps.max_output_tokens > 0
        assert caps.supports_streaming is True
        assert caps.supports_functions is True
        assert caps.supports_vision is True

    def test_capabilities_sonnet(self):
        """Test Claude 3 Sonnet capabilities."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-sonnet-20240229"
        )
        
        caps = provider.capabilities
        assert caps.supports_vision is True
        assert caps.max_input_tokens >= 100000

    def test_capabilities_haiku(self):
        """Test Claude 3 Haiku capabilities."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-haiku-20240307"
        )
        
        caps = provider.capabilities
        assert caps.supports_vision is True
        assert caps.supports_functions is False  # Haiku doesn't have functions

    def test_pricing_opus(self):
        """Test Claude 3 Opus pricing (most expensive)."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-opus-20240229"
        )
        
        pricing = provider.pricing_per_1k_tokens
        assert pricing["input"] == 0.015
        assert pricing["output"] == 0.075

    def test_pricing_sonnet(self):
        """Test Claude 3 Sonnet pricing (balanced)."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-sonnet-20240229"
        )
        
        pricing = provider.pricing_per_1k_tokens
        assert pricing["input"] == 0.003
        assert pricing["output"] == 0.015

    def test_pricing_haiku(self):
        """Test Claude 3 Haiku pricing (cheapest)."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-haiku-20240307"
        )
        
        pricing = provider.pricing_per_1k_tokens
        assert pricing["input"] < 0.001  # Cheapest
        assert pricing["output"] < 0.002

    def test_get_available_models(self):
        """Test listing available models."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        models = provider.get_available_models()
        assert len(models) >= 6  # Includes aliases
        assert "claude-3-opus-20240229" in models
        assert "claude-3-sonnet" in models
        assert "claude-3-haiku" in models


class TestAnthropicTokenCounting:
    """Tests for token counting accuracy."""

    def test_count_tokens_short_text(self):
        """Test token counting for short text."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        tokens = provider.count_tokens("Hello, world!")
        assert tokens > 0
        assert tokens <= 10  # Conservative estimate

    def test_count_tokens_longer_text(self):
        """Test token counting for longer text."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        text = "This is a longer text. " * 10
        tokens = provider.count_tokens(text)
        assert tokens > 20
        assert tokens < 200

    def test_count_tokens_empty_string(self):
        """Test token counting for empty string."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        tokens = provider.count_tokens("")
        assert tokens >= 0

    def test_token_counting_consistency(self):
        """Test that token counting is consistent."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        text = "test text"
        count1 = provider.count_tokens(text)
        count2 = provider.count_tokens(text)
        assert count1 == count2


class TestAnthropicCostCalculation:
    """Tests for cost estimation accuracy."""

    def test_estimate_cost_opus(self):
        """Test cost estimation for Claude 3 Opus."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-opus-20240229"
        )
        
        # 1000 input @ $0.015/1k + 1000 output @ $0.075/1k = $0.09
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost == pytest.approx(0.09, abs=0.001)

    def test_estimate_cost_sonnet(self):
        """Test cost estimation for Claude 3 Sonnet."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-sonnet-20240229"
        )
        
        # 1000 input @ $0.003/1k + 1000 output @ $0.015/1k = $0.018
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost == pytest.approx(0.018, abs=0.001)

    def test_estimate_cost_haiku(self):
        """Test cost estimation for Claude 3 Haiku (cheapest)."""
        provider = AnthropicProvider(
            api_key="sk-ant-test123",
            model="claude-3-haiku-20240307"
        )
        
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost < 0.01

    def test_estimate_cost_zero_tokens(self):
        """Test cost with zero tokens."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        cost = provider.estimate_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0


class TestAnthropicErrorHandling:
    """Tests for error handling."""

    def test_handle_http_error_401_auth(self):
        """Test handling authentication error (401)."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        response = Mock(spec=Response)
        response.status_code = 401
        response.json.return_value = {
            "error": {"message": "Invalid API key"}
        }
        response.headers = {}
        
        request = Mock(spec=Request)
        error = HTTPStatusError(
            message="Unauthorized",
            request=request,
            response=response,
        )
        
        result = provider._handle_http_error(error, attempt=0)
        assert isinstance(result, AuthenticationError)
        assert result.is_retryable is False

    def test_handle_http_error_429_rate_limit(self):
        """Test handling rate limit error (429)."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        response = Mock(spec=Response)
        response.status_code = 429
        response.json.return_value = {
            "error": {"message": "Rate limit exceeded"}
        }
        response.headers = {"retry-after": "60"}
        
        request = Mock(spec=Request)
        error = HTTPStatusError(
            message="Too Many Requests",
            request=request,
            response=response,
        )
        
        result = provider._handle_http_error(error, attempt=0)
        assert isinstance(result, RateLimitError)
        assert result.is_retryable is True
        assert result.retry_after_seconds == 60

    def test_handle_http_error_500_service(self):
        """Test handling service error (500)."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        response = Mock(spec=Response)
        response.status_code = 500
        response.json.return_value = {
            "error": {"message": "Internal server error"}
        }
        response.headers = {}
        
        request = Mock(spec=Request)
        error = HTTPStatusError(
            message="Internal Server Error",
            request=request,
            response=response,
        )
        
        result = provider._handle_http_error(error, attempt=0)
        assert isinstance(result, ProviderUnavailableError)
        assert result.is_retryable is True


@pytest.mark.asyncio
class TestAnthropicExecution:
    """Tests for task execution."""

    async def test_execute_success(self):
        """Test successful execution."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": [{"text": "Test response"}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                }
            }
            mock_response.raise_for_status = Mock()
            
            mock_client.post.return_value = mock_response
            
            response = await provider.execute("Test prompt")
            
            assert response.output == "Test response"
            assert response.tokens_used == 15
            assert response.cost_usd > 0
            assert response.provider_id == "anthropic"

    async def test_execute_with_metadata(self):
        """Test execution with metadata."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        metadata = ExecutionMetadata(
            task_type="summarize",
            complexity="simple",
        )
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": [{"text": "Response"}],
                "usage": {
                    "input_tokens": 5,
                    "output_tokens": 3,
                }
            }
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            
            response = await provider.execute("Test", metadata=metadata)
            assert response.output == "Response"

    async def test_execute_streaming(self):
        """Test streaming response."""
        provider = AnthropicProvider(api_key="sk-ant-test123")
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            stream_lines = [
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" "}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"world"}}',
                'data: {"type":"message_stop"}',
            ]
            
            mock_stream = AsyncMock()
            mock_stream.__aenter__.return_value = mock_stream
            mock_stream.__aexit__.return_value = None
            mock_stream.status_code = 200
            mock_stream.aiter_lines = AsyncMock(return_value=iter(stream_lines))
            
            mock_client.stream.return_value = mock_stream
            
            chunks = []
            async for chunk in provider.execute_streaming("Test prompt"):
                chunks.append(chunk)
            
            assert "".join(chunks) == "Hello world"


class TestAnthropicProviderModels:
    """Tests for different model configurations."""

    def test_all_models_have_config(self):
        """Test that all supported models have configurations."""
        for model in AnthropicProvider.get_available_models(None):
            assert model in AnthropicProvider.MODEL_CONFIGS
            config = AnthropicProvider.MODEL_CONFIGS[model]
            
            assert "max_tokens" in config
            assert "input_price_per_1k" in config
            assert "output_price_per_1k" in config

    def test_model_pricing_consistency(self):
        """Test that cheaper models are actually cheaper."""
        opus_price = AnthropicProvider.MODEL_CONFIGS["claude-3-opus-20240229"]["input_price_per_1k"]
        haiku_price = AnthropicProvider.MODEL_CONFIGS["claude-3-haiku-20240307"]["input_price_per_1k"]
        
        # Haiku should be cheaper than Opus
        assert haiku_price < opus_price

    def test_model_max_tokens_reasonable(self):
        """Test that max tokens values are reasonable."""
        for model, config in AnthropicProvider.MODEL_CONFIGS.items():
            max_tokens = config["max_tokens"]
            # All Claude 3 models support 200k
            assert max_tokens == 200000
