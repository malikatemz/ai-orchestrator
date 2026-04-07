"""Unit tests for OpenAI provider implementation.

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
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, RequestError, Response, Request

from app.providers.openai_provider_new import OpenAIProvider
from app.providers.base import (
    ExecutionMetadata,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
    ProviderError,
)


class TestOpenAIProviderInitialization:
    """Tests for OpenAI provider initialization."""

    def test_init_with_valid_api_key(self):
        """Test initializing provider with valid API key."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-4-turbo-preview"
        )
        
        assert provider.api_key == "sk-proj-test123"
        assert provider.model == "gpt-4-turbo-preview"
        assert provider.provider_id == "openai"

    def test_init_with_default_model(self):
        """Test that model defaults to gpt-4-turbo-preview."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        assert provider.model == OpenAIProvider.DEFAULT_MODEL

    def test_init_with_invalid_api_key_format(self):
        """Test that invalid API key format raises ValueError."""
        with pytest.raises(ValueError, match="sk-"):
            OpenAIProvider(api_key="invalid-key", model="gpt-4")

    def test_init_with_unsupported_model(self):
        """Test that unsupported model raises ValueError."""
        with pytest.raises(ValueError, match="not supported"):
            OpenAIProvider(
                api_key="sk-proj-test123",
                model="unknown-model"
            )

    def test_init_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError):
            OpenAIProvider(api_key="", model="gpt-4")


class TestOpenAIProviderCapabilities:
    """Tests for provider capabilities and pricing."""

    def test_capabilities_gpt4(self):
        """Test GPT-4 capabilities."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-4"
        )
        
        caps = provider.capabilities
        assert caps.max_input_tokens > 0
        assert caps.max_output_tokens > 0
        assert caps.supports_streaming is True
        assert caps.supports_functions is True
        assert caps.supports_vision is False

    def test_capabilities_gpt4_turbo(self):
        """Test GPT-4 Turbo capabilities."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-4-turbo-preview"
        )
        
        caps = provider.capabilities
        assert caps.supports_vision is True
        assert caps.max_input_tokens >= 100000

    def test_capabilities_gpt35_turbo(self):
        """Test GPT-3.5 Turbo capabilities."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-3.5-turbo"
        )
        
        caps = provider.capabilities
        assert caps.supports_vision is False
        assert caps.max_input_tokens < 20000

    def test_pricing_gpt4(self):
        """Test GPT-4 pricing."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-4"
        )
        
        pricing = provider.pricing_per_1k_tokens
        assert pricing["input"] == 0.03
        assert pricing["output"] == 0.06

    def test_pricing_gpt35_turbo(self):
        """Test GPT-3.5 Turbo pricing (cheapest)."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-3.5-turbo"
        )
        
        pricing = provider.pricing_per_1k_tokens
        assert pricing["input"] < 0.001  # Very cheap
        assert pricing["output"] < 0.002

    def test_get_available_models(self):
        """Test listing available models."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        models = provider.get_available_models()
        assert len(models) >= 4
        assert "gpt-4" in models
        assert "gpt-4-turbo-preview" in models
        assert "gpt-3.5-turbo" in models


class TestOpenAITokenCounting:
    """Tests for token counting accuracy."""

    def test_count_tokens_short_text(self):
        """Test token counting for short text."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        # "Hello, world!" should be ~3-4 tokens
        tokens = provider.count_tokens("Hello, world!")
        assert tokens > 0
        assert tokens <= 5  # Allow small margin

    def test_count_tokens_longer_text(self):
        """Test token counting for longer text."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        # Longer text should have proportionally more tokens
        text = "This is a longer text. " * 10
        tokens = provider.count_tokens(text)
        assert tokens > 50
        assert tokens < 150

    def test_count_tokens_empty_string(self):
        """Test token counting for empty string."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        tokens = provider.count_tokens("")
        assert tokens == 0

    def test_token_counting_consistency(self):
        """Test that token counting is consistent."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        text = "test text"
        count1 = provider.count_tokens(text)
        count2 = provider.count_tokens(text)
        assert count1 == count2


class TestOpenAICostCalculation:
    """Tests for cost estimation accuracy."""

    def test_estimate_cost_gpt4(self):
        """Test cost estimation for GPT-4."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-4"
        )
        
        # 1000 input tokens @ $0.03/1k + 1000 output @ $0.06/1k = $0.09
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost == pytest.approx(0.09, abs=0.001)

    def test_estimate_cost_gpt35_turbo(self):
        """Test cost estimation for GPT-3.5 Turbo (cheapest)."""
        provider = OpenAIProvider(
            api_key="sk-proj-test123",
            model="gpt-3.5-turbo"
        )
        
        # Much cheaper
        cost = provider.estimate_cost(input_tokens=1000, output_tokens=1000)
        assert cost < 0.01

    def test_estimate_cost_zero_tokens(self):
        """Test cost with zero tokens."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        cost = provider.estimate_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_estimate_cost_small_amount(self):
        """Test cost for small token amount."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        # 1 input token + 1 output token
        cost = provider.estimate_cost(input_tokens=1, output_tokens=1)
        assert cost > 0
        assert cost < 0.001  # Very small


class TestOpenAIErrorHandling:
    """Tests for error handling."""

    def test_handle_http_error_401_auth(self):
        """Test handling authentication error (401)."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
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
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
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
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
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

    def test_handle_http_error_generic(self):
        """Test handling generic HTTP error."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        response = Mock(spec=Response)
        response.status_code = 400
        response.json.return_value = {
            "error": {"message": "Bad request"}
        }
        response.headers = {}
        
        request = Mock(spec=Request)
        error = HTTPStatusError(
            message="Bad Request",
            request=request,
            response=response,
        )
        
        result = provider._handle_http_error(error, attempt=0)
        assert isinstance(result, ProviderError)
        assert result.is_retryable is False


@pytest.mark.asyncio
class TestOpenAIExecution:
    """Tests for task execution."""

    async def test_execute_success(self):
        """Test successful execution."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        # Mock the httpx client
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                }
            }
            mock_response.raise_for_status = Mock()
            
            mock_client.post.return_value = mock_response
            
            response = await provider.execute("Test prompt")
            
            assert response.output == "Test response"
            assert response.tokens_used == 15
            assert response.cost_usd > 0
            assert response.provider_id == "openai"
            assert response.model_used == provider.model

    async def test_execute_with_metadata(self):
        """Test execution with metadata."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        metadata = ExecutionMetadata(
            task_type="summarize",
            complexity="simple",
        )
        
        # Just verify it accepts metadata without error
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                }
            }
            mock_response.raise_for_status = Mock()
            mock_client.post.return_value = mock_response
            
            response = await provider.execute("Test", metadata=metadata)
            assert response.output == "Response"

    async def test_execute_auth_error_not_retried(self):
        """Test that authentication errors are not retried."""
        provider = OpenAIProvider(api_key="sk-invalid")
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            response = Mock(spec=Response)
            response.status_code = 401
            response.json.return_value = {
                "error": {"message": "Invalid API key"}
            }
            response.headers = {}
            request = Mock(spec=Request)
            
            mock_client.post.side_effect = HTTPStatusError(
                message="Unauthorized",
                request=request,
                response=response,
            )
            
            with pytest.raises(AuthenticationError):
                await provider.execute("Test prompt")

    async def test_execute_rate_limit_retried(self):
        """Test that rate limit errors are retried."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        provider.INITIAL_RETRY_DELAY = 0.01  # Fast retry for testing
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # First call: rate limit error
            rate_limit_response = Mock(spec=Response)
            rate_limit_response.status_code = 429
            rate_limit_response.json.return_value = {
                "error": {"message": "Rate limit exceeded"}
            }
            rate_limit_response.headers = {"retry-after": "1"}
            request = Mock(spec=Request)
            
            # Second call: success
            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                }
            }
            success_response.raise_for_status = Mock()
            
            mock_client.post.side_effect = [
                HTTPStatusError(
                    message="Too Many Requests",
                    request=request,
                    response=rate_limit_response,
                ),
                success_response,
            ]
            
            response = await provider.execute("Test prompt")
            assert response.output == "Response"
            assert mock_client.post.call_count == 2  # Called twice

    async def test_execute_streaming(self):
        """Test streaming response."""
        provider = OpenAIProvider(api_key="sk-proj-test123")
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock streaming response
            stream_lines = [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" "}}]}',
                'data: {"choices":[{"delta":{"content":"world"}}]}',
                'data: [DONE]',
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


class TestOpenAIProviderModels:
    """Tests for different model configurations."""

    def test_all_models_have_config(self):
        """Test that all supported models have configurations."""
        for model in OpenAIProvider.get_available_models(None):
            assert model in OpenAIProvider.MODEL_CONFIGS
            config = OpenAIProvider.MODEL_CONFIGS[model]
            
            assert "max_tokens" in config
            assert "input_price_per_1k" in config
            assert "output_price_per_1k" in config

    def test_model_pricing_consistency(self):
        """Test that newer models are generally cheaper."""
        gpt4_price = OpenAIProvider.MODEL_CONFIGS["gpt-4"]["input_price_per_1k"]
        gpt35_price = OpenAIProvider.MODEL_CONFIGS["gpt-3.5-turbo"]["input_price_per_1k"]
        
        # GPT-3.5 should be cheaper than GPT-4
        assert gpt35_price < gpt4_price

    def test_model_max_tokens_reasonable(self):
        """Test that max tokens values are reasonable."""
        for model, config in OpenAIProvider.MODEL_CONFIGS.items():
            max_tokens = config["max_tokens"]
            # All models should support at least 1K tokens
            assert max_tokens >= 1024
            # No model should claim unreasonable tokens
            assert max_tokens <= 200000
