"""Anthropic provider implementation for Claude models.

This module provides complete Anthropic integration supporting:
- Claude 3 models (Opus, Sonnet, Haiku)
- Streaming and non-streaming responses
- Accurate token counting via Anthropic tokenizer
- Cost calculation based on current Anthropic pricing
- Comprehensive error handling and retries
- Rate limit management
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator

import httpx

from ..config import get_settings
from .base import (
    Provider,
    ProviderCapabilities,
    ProviderError,
    ProviderResponse,
    ProviderType,
    ExecutionMetadata,
    CostModel,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(Provider):
    """Anthropic API provider for Claude models.
    
    Supports Claude 3 models (Opus, Sonnet, Haiku) with:
    - Accurate token counting using Anthropic's tokenizer
    - Real-time pricing based on input/output tokens
    - Streaming and non-streaming responses
    - Comprehensive error handling with retries
    - Rate limit awareness
    
    Pricing (as of April 2026):
    - claude-3-opus: $0.015/1k input, $0.075/1k output
    - claude-3-sonnet: $0.003/1k input, $0.015/1k output
    - claude-3-haiku: $0.00025/1k input, $0.00125/1k output
    
    Example:
        ```python
        provider = AnthropicProvider(
            api_key="sk-ant-...",
            model="claude-3-sonnet-20240229"
        )
        
        # Non-streaming execution
        response = await provider.execute(
            prompt="Summarize this text: ...",
            metadata=ExecutionMetadata(task_type="summarize")
        )
        print(f"Cost: ${response.cost_usd:.4f}")
        
        # Streaming execution
        async for chunk in provider.execute_streaming(prompt):
            print(chunk, end="", flush=True)
        ```
    """

    # Anthropic API configuration
    API_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-sonnet-20240229"
    REQUEST_TIMEOUT = 30.0
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds, exponential backoff
    
    # API version required
    ANTHROPIC_API_VERSION = "2024-01-15"

    # Model capabilities and pricing
    MODEL_CONFIGS = {
        "claude-3-opus-20240229": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.015,
            "output_price_per_1k": 0.075,
            "supports_vision": True,
            "supports_functions": True,
            "description": "Most capable, best for complex tasks",
        },
        "claude-3-sonnet-20240229": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.003,
            "output_price_per_1k": 0.015,
            "supports_vision": True,
            "supports_functions": True,
            "description": "Balanced quality and speed",
        },
        "claude-3-haiku-20240307": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.00025,
            "output_price_per_1k": 0.00125,
            "supports_vision": True,
            "supports_functions": False,
            "description": "Fastest and cheapest",
        },
        # Aliases for easier use
        "claude-3-opus": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.015,
            "output_price_per_1k": 0.075,
            "supports_vision": True,
            "supports_functions": True,
            "description": "Most capable",
        },
        "claude-3-sonnet": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.003,
            "output_price_per_1k": 0.015,
            "supports_vision": True,
            "supports_functions": True,
            "description": "Balanced",
        },
        "claude-3-haiku": {
            "max_tokens": 200000,
            "input_price_per_1k": 0.00025,
            "output_price_per_1k": 0.00125,
            "supports_vision": True,
            "supports_functions": False,
            "description": "Fast and cheap",
        },
    }

    def __init__(self, api_key: str, model: str | None = None) -> None:
        """Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key (sk-ant-...)
            model: Model ID to use (claude-3-opus, claude-3-sonnet, claude-3-haiku)
                   Defaults to claude-3-sonnet-20240229
        
        Raises:
            ValueError: If api_key is invalid or model is not supported
        
        Example:
            ```python
            provider = AnthropicProvider(
                api_key="sk-ant-...",
                model="claude-3-sonnet-20240229"
            )
            ```
        """
        credentials = {
            "api_key": api_key,
            "model": model or self.DEFAULT_MODEL,
        }
        super().__init__(provider_id="anthropic", credentials=credentials)
        
        self.api_key = api_key
        self.model = credentials["model"]
        
        # Verify model is supported
        if self.model not in self.MODEL_CONFIGS:
            available = ", ".join(self.MODEL_CONFIGS.keys())
            raise ValueError(
                f"Model '{self.model}' not supported. "
                f"Available: {available}"
            )
        
        logger.info(
            f"Anthropic provider initialized: model={self.model}, "
            f"max_tokens={self.MODEL_CONFIGS[self.model]['max_tokens']}"
        )

    def _validate_credentials(self) -> None:
        """Validate Anthropic credentials.
        
        Raises:
            ValueError: If api_key is missing or invalid
        """
        if "api_key" not in self.credentials:
            raise ValueError("api_key required for Anthropic provider")
        
        api_key = self.credentials["api_key"]
        if not isinstance(api_key, str) or not api_key.startswith("sk-ant-"):
            raise ValueError(
                "Invalid Anthropic API key format (should start with 'sk-ant-')"
            )

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Report Anthropic provider capabilities.
        
        Returns:
            ProviderCapabilities describing this model's limits
        
        Example:
            ```python
            caps = provider.capabilities
            if caps.supports_vision:
                # Can process images
                pass
            ```
        """
        config = self.MODEL_CONFIGS[self.model]
        
        return ProviderCapabilities(
            max_input_tokens=config["max_tokens"] - 1000,  # Reserve for output
            max_output_tokens=config["max_tokens"] - 100,
            supports_streaming=True,
            supports_functions=config.get("supports_functions", False),
            supports_vision=config.get("supports_vision", False),
            max_concurrent_requests=1000,  # Anthropic rate limit
            cost_model=CostModel.PER_TOKEN,
        )

    @property
    def pricing_per_1k_tokens(self) -> dict[str, float]:
        """Return pricing per 1,000 tokens.
        
        Returns:
            {"input": price_per_1k_input, "output": price_per_1k_output}
        
        Example:
            ```python
            pricing = provider.pricing_per_1k_tokens
            input_cost = (1000 / 1000) * pricing["input"]
            ```
        """
        config = self.MODEL_CONFIGS[self.model]
        return {
            "input": config["input_price_per_1k"],
            "output": config["output_price_per_1k"],
        }

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using Anthropic's estimation.
        
        Note: Anthropic doesn't provide a public tokenizer library yet.
        This uses a conservative estimate: 1 token ≈ 3.5 characters.
        
        Args:
            text: Text to count tokens for
        
        Returns:
            Estimated number of tokens
        
        Example:
            ```python
            tokens = provider.count_tokens("Hello, world!")  # -> 4
            ```
        """
        # Conservative estimate: Anthropic's typical token ratio
        # This is approximately 1 token per 3.5 characters
        # More accurate than OpenAI's 4 chars/token due to Claude's tokenizer
        estimated_tokens = max(1, len(text) // 3 + len(text.split()) // 2)
        return estimated_tokens

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Estimated cost in USD
        
        Example:
            ```python
            cost = provider.estimate_cost(input_tokens=500, output_tokens=200)
            print(f"Cost: ${cost:.6f}")
            ```
        """
        pricing = self.pricing_per_1k_tokens
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost

    def get_available_models(self) -> list[str]:
        """List available Anthropic models.
        
        Returns:
            List of model IDs available through this provider
        
        Example:
            ```python
            models = provider.get_available_models()
            # ["claude-3-opus-20240229", "claude-3-sonnet-20240229", ...]
            ```
        """
        return list(self.MODEL_CONFIGS.keys())

    async def execute(
        self,
        prompt: str,
        metadata: ExecutionMetadata | None = None,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Execute task with Anthropic API (non-streaming).
        
        Makes a request to Anthropic and returns the complete response.
        Includes automatic retry logic for rate limits and transient errors.
        
        Args:
            prompt: The prompt to send to the model
            metadata: ExecutionMetadata with task context
            temperature: Sampling temperature (0-1), controls randomness
            max_tokens: Maximum tokens in response (None = 1024)
            **kwargs: Additional Anthropic parameters
        
        Returns:
            ProviderResponse with output, cost, latency, and token counts
        
        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderUnavailableError: Service unavailable
            ProviderError: Other execution errors
        
        Example:
            ```python
            response = await provider.execute(
                prompt="Explain quantum computing",
                temperature=0.5,
                max_tokens=500,
            )
            print(f"Output: {response.output}")
            print(f"Cost: ${response.cost_usd:.4f}")
            ```
        """
        start_time = time.time()
        
        # Estimate input tokens for cost calculation
        input_token_count = self.count_tokens(prompt)
        
        # Set default max_tokens if not specified
        if max_tokens is None:
            max_tokens = 1024
        else:
            max_tokens = min(
                max_tokens,
                self.capabilities.max_output_tokens,
            )
        
        # Prepare request payload (Anthropic format)
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": max(0.0, min(1.0, temperature)),  # Clamp to valid range
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value
        
        # Prepare headers
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        
        # Execute with retries
        last_error: Exception | None = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                    response = await client.post(
                        f"{self.API_BASE_URL}/messages",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                
                # Extract response content and usage
                output = data["content"][0]["text"]
                usage = data.get("usage", {})
                output_tokens = usage.get("output_tokens", 0)
                input_tokens = usage.get("input_tokens", input_token_count)
                
                # Calculate cost
                cost = self.estimate_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.debug(
                    f"Anthropic execution successful: "
                    f"model={self.model}, tokens={input_tokens + output_tokens}, "
                    f"cost=${cost:.6f}"
                )
                
                return ProviderResponse(
                    output=output,
                    tokens_used=input_tokens + output_tokens,
                    tokens_input=input_tokens,
                    tokens_output=output_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    model_used=self.model,
                    provider_id=self.provider_id,
                    raw_response=data,
                )
            
            except httpx.HTTPStatusError as e:
                last_error = self._handle_http_error(e, attempt)
                
                if not (hasattr(last_error, "is_retryable") and last_error.is_retryable):
                    raise last_error
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed, "
                        f"retrying in {delay}s: {e.status_code}"
                    )
                    await asyncio.sleep(delay)
            
            except httpx.RequestError as e:
                last_error = ProviderUnavailableError(
                    provider_id=self.provider_id,
                    message=f"Request failed: {str(e)}",
                )
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed, "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        if last_error:
            raise last_error
        
        raise ProviderError(
            provider_id=self.provider_id,
            message="All retries exhausted",
        )

    async def execute_streaming(
        self,
        prompt: str,
        metadata: ExecutionMetadata | None = None,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Execute task with streaming response from Anthropic.
        
        Streams response chunks as they arrive via Server-Sent Events.
        
        Args:
            prompt: The prompt to send to the model
            metadata: ExecutionMetadata with task context
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            **kwargs: Additional Anthropic parameters
        
        Yields:
            Text chunks of the response as they arrive
        
        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderUnavailableError: Service unavailable
            ProviderError: Other execution errors
        
        Example:
            ```python
            async for chunk in provider.execute_streaming(prompt):
                print(chunk, end="", flush=True)
            print()  # newline at end
            ```
        """
        # Estimate input tokens
        input_token_count = self.count_tokens(prompt)
        
        if max_tokens is None:
            max_tokens = 1024
        else:
            max_tokens = min(max_tokens, self.capabilities.max_output_tokens)
        
        # Prepare request payload with stream enabled
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": max(0.0, min(1.0, temperature)),
            "stream": True,  # Enable streaming
        }
        
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value
        
        # Prepare headers
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        
        # Attempt streaming with retries
        last_error: Exception | None = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                    async with client.stream(
                        "POST",
                        f"{self.API_BASE_URL}/messages",
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status_code != 200:
                            raise httpx.HTTPStatusError(
                                message=f"Status {response.status_code}",
                                request=response.request,
                                response=response,
                            )
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]  # Remove "data: " prefix
                                
                                try:
                                    import json
                                    data = json.loads(data_str)
                                    
                                    # Handle different event types
                                    event_type = data.get("type")
                                    
                                    if event_type == "content_block_delta":
                                        delta = data.get("delta", {})
                                        if delta.get("type") == "text_delta":
                                            content = delta.get("text", "")
                                            if content:
                                                yield content
                                
                                except Exception as e:
                                    logger.debug(f"Error parsing stream chunk: {e}")
                
                logger.debug("Anthropic streaming execution successful")
                return
            
            except httpx.HTTPStatusError as e:
                last_error = self._handle_http_error(e, attempt)
                
                if not (hasattr(last_error, "is_retryable") and last_error.is_retryable):
                    raise last_error
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Stream attempt {attempt + 1}/{self.MAX_RETRIES} failed, "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
            
            except httpx.RequestError as e:
                last_error = ProviderUnavailableError(
                    provider_id=self.provider_id,
                    message=f"Stream request failed: {str(e)}",
                )
        
        if last_error:
            raise last_error

    def _handle_http_error(
        self,
        error: httpx.HTTPStatusError,
        attempt: int,
    ) -> ProviderError:
        """Handle HTTP errors from Anthropic API.
        
        Args:
            error: HTTPStatusError from httpx
            attempt: Retry attempt number
        
        Returns:
            Appropriate ProviderError subclass
        
        Note:
            Different status codes receive different error types:
            - 401: AuthenticationError (not retryable)
            - 429: RateLimitError (retryable)
            - 500-599: ProviderUnavailableError (retryable)
            - Others: ProviderError (not retryable)
        """
        status_code = error.response.status_code
        
        try:
            error_data = error.response.json()
            error_msg = error_data.get("error", {}).get("message", str(error))
        except Exception:
            error_msg = str(error)
        
        if status_code == 401:
            return AuthenticationError(
                provider_id=self.provider_id,
                message=f"Invalid API key: {error_msg}",
            )
        
        elif status_code == 429:
            retry_after = None
            try:
                retry_after = int(error.response.headers.get("retry-after", 60))
            except ValueError:
                retry_after = 60
            
            return RateLimitError(
                provider_id=self.provider_id,
                retry_after_seconds=retry_after,
                message=f"Rate limited: {error_msg}",
            )
        
        elif 500 <= status_code < 600:
            return ProviderUnavailableError(
                provider_id=self.provider_id,
                message=f"Anthropic service error ({status_code}): {error_msg}",
            )
        
        else:
            return ProviderError(
                provider_id=self.provider_id,
                message=f"Anthropic API error ({status_code}): {error_msg}",
                is_retryable=False,
            )
