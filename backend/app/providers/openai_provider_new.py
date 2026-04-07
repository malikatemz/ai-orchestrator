"""OpenAI provider implementation for GPT models.

This module provides a complete OpenAI integration supporting:
- GPT-4, GPT-4 Turbo, GPT-3.5-Turbo models
- Streaming and non-streaming responses
- Accurate token counting via tiktoken
- Cost calculation based on current OpenAI pricing
- Comprehensive error handling and retries
- Rate limit management
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator

import httpx
import tiktoken

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


class OpenAIProvider(Provider):
    """OpenAI API provider for GPT models.
    
    Supports GPT-4, GPT-4 Turbo, and GPT-3.5-Turbo with:
    - Accurate token counting using official tiktoken tokenizer
    - Real-time pricing based on input/output tokens
    - Streaming and non-streaming responses
    - Comprehensive error handling with retries
    - Rate limit awareness
    
    Pricing (as of April 2026):
    - gpt-4: $0.03/1k input, $0.06/1k output
    - gpt-4-turbo-preview: $0.01/1k input, $0.03/1k output
    - gpt-3.5-turbo: $0.0005/1k input, $0.0015/1k output
    
    Example:
        ```python
        provider = OpenAIProvider(
            api_key="sk-...",
            model="gpt-4-turbo-preview"
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

    # OpenAI API configuration
    API_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4-turbo-preview"
    REQUEST_TIMEOUT = 30.0
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds, exponential backoff

    # Model capabilities and pricing
    MODEL_CONFIGS = {
        "gpt-4": {
            "max_tokens": 8192,
            "input_price_per_1k": 0.03,
            "output_price_per_1k": 0.06,
            "supports_vision": False,
            "supports_functions": True,
        },
        "gpt-4-turbo-preview": {
            "max_tokens": 128000,
            "input_price_per_1k": 0.01,
            "output_price_per_1k": 0.03,
            "supports_vision": True,
            "supports_functions": True,
        },
        "gpt-4-turbo": {
            "max_tokens": 128000,
            "input_price_per_1k": 0.01,
            "output_price_per_1k": 0.03,
            "supports_vision": True,
            "supports_functions": True,
        },
        "gpt-4o": {
            "max_tokens": 128000,
            "input_price_per_1k": 0.005,
            "output_price_per_1k": 0.015,
            "supports_vision": True,
            "supports_functions": True,
        },
        "gpt-3.5-turbo": {
            "max_tokens": 16384,
            "input_price_per_1k": 0.0005,
            "output_price_per_1k": 0.0015,
            "supports_vision": False,
            "supports_functions": True,
        },
    }

    def __init__(self, api_key: str, model: str | None = None) -> None:
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (sk-...)
            model: Model ID to use (gpt-4, gpt-4-turbo-preview, gpt-3.5-turbo, etc.)
                   Defaults to gpt-4-turbo-preview
        
        Raises:
            ValueError: If api_key is invalid or model is not supported
        
        Example:
            ```python
            provider = OpenAIProvider(
                api_key="sk-proj-...",
                model="gpt-4-turbo-preview"
            )
            ```
        """
        credentials = {
            "api_key": api_key,
            "model": model or self.DEFAULT_MODEL,
        }
        super().__init__(provider_id="openai", credentials=credentials)
        
        self.api_key = api_key
        self.model = credentials["model"]
        
        # Verify model is supported
        if self.model not in self.MODEL_CONFIGS:
            available = ", ".join(self.MODEL_CONFIGS.keys())
            raise ValueError(
                f"Model '{self.model}' not supported. "
                f"Available: {available}"
            )
        
        # Initialize tokenizer for this model
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback to a similar model's tokenizer
            fallback_model = "gpt-3.5-turbo"
            logger.warning(
                f"Tokenizer for {self.model} not found, using {fallback_model}"
            )
            self.tokenizer = tiktoken.encoding_for_model(fallback_model)
        
        logger.info(
            f"OpenAI provider initialized: model={self.model}, "
            f"max_tokens={self.MODEL_CONFIGS[self.model]['max_tokens']}"
        )

    def _validate_credentials(self) -> None:
        """Validate OpenAI credentials.
        
        Raises:
            ValueError: If api_key is missing or invalid
        """
        if "api_key" not in self.credentials:
            raise ValueError("api_key required for OpenAI provider")
        
        api_key = self.credentials["api_key"]
        if not isinstance(api_key, str) or not api_key.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format (should start with 'sk-')")

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Report OpenAI provider capabilities.
        
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
            max_concurrent_requests=3500,  # OpenAI rate limit for pro accounts
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
            input_cost = (1000 / 1000) * pricing["input"]  # $0.01
            ```
        """
        config = self.MODEL_CONFIGS[self.model]
        return {
            "input": config["input_price_per_1k"],
            "output": config["output_price_per_1k"],
        }

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using official OpenAI tokenizer.
        
        Uses tiktoken with the model-specific encoding to match OpenAI's
        actual token counts.
        
        Args:
            text: Text to count tokens for
        
        Returns:
            Number of tokens (including special tokens)
        
        Example:
            ```python
            tokens = provider.count_tokens("Hello, world!")  # -> 4
            ```
        """
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            # Fallback: rough estimate of 4 chars per token
            return len(text) // 4

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
        """List available OpenAI models.
        
        Returns:
            List of model IDs available through this provider
        
        Example:
            ```python
            models = provider.get_available_models()
            # ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"]
            ```
        """
        return list(self.MODEL_CONFIGS.keys())

    async def execute(
        self,
        prompt: str,
        metadata: ExecutionMetadata | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Execute task with OpenAI API (non-streaming).
        
        Makes a synchronous request to OpenAI and returns the complete response.
        Includes automatic retry logic for rate limits and transient errors.
        
        Args:
            prompt: The prompt to send to the model
            metadata: ExecutionMetadata with task context
            temperature: Sampling temperature (0-2), controls randomness
            max_tokens: Maximum tokens in response (None = model default)
            **kwargs: Additional OpenAI parameters (top_p, frequency_penalty, etc.)
        
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
            print(f"Tokens: {response.tokens_used}")
            ```
        """
        start_time = time.time()
        
        # Count input tokens for cost estimation
        input_token_count = self.count_tokens(prompt)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": max(0.0, min(2.0, temperature)),  # Clamp to valid range
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = min(
                max_tokens,
                self.capabilities.max_output_tokens,
            )
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Execute with retries
        last_error: Exception | None = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                    response = await client.post(
                        f"{self.API_BASE_URL}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                
                # Extract response content and usage
                output = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                # Calculate cost
                cost = self.estimate_cost(
                    input_tokens=usage.get("prompt_tokens", input_token_count),
                    output_tokens=output_tokens,
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                logger.debug(
                    f"OpenAI execution successful: "
                    f"model={self.model}, tokens={total_tokens}, cost=${cost:.6f}"
                )
                
                return ProviderResponse(
                    output=output,
                    tokens_used=total_tokens,
                    tokens_input=usage.get("prompt_tokens", input_token_count),
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
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Execute task with streaming response from OpenAI.
        
        Streams response chunks as they arrive, useful for long outputs.
        Each chunk is yielded as it arrives from the API.
        
        Args:
            prompt: The prompt to send to the model
            metadata: ExecutionMetadata with task context
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional OpenAI parameters
        
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
        # Count input tokens
        input_token_count = self.count_tokens(prompt)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": max(0.0, min(2.0, temperature)),
            "stream": True,  # Enable streaming
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = min(
                max_tokens,
                self.capabilities.max_output_tokens,
            )
        
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Attempt streaming with retries
        last_error: Exception | None = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
                    async with client.stream(
                        "POST",
                        f"{self.API_BASE_URL}/chat/completions",
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
                                
                                if data_str == "[DONE]":
                                    break
                                
                                try:
                                    import json
                                    data = json.loads(data_str)
                                    
                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        yield content
                                except Exception as e:
                                    logger.debug(f"Error parsing stream chunk: {e}")
                
                logger.debug("OpenAI streaming execution successful")
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
        """Handle HTTP errors from OpenAI API.
        
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
                message=f"OpenAI service error ({status_code}): {error_msg}",
            )
        
        else:
            return ProviderError(
                provider_id=self.provider_id,
                message=f"OpenAI API error ({status_code}): {error_msg}",
                is_retryable=False,
            )
