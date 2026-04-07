"""Abstract provider interface and base classes for multi-provider LLM support.

This module defines the extensible provider abstraction that all provider implementations
must follow. It enables switching between OpenAI, Anthropic, Cohere, and other LLM providers
transparently, with cost tracking, token counting, and fallback chains.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Optional


class ProviderType(str, Enum):
    """Supported provider types."""
    LLM = "llm"
    SCRAPER = "scraper"
    EMBEDDING = "embedding"


class CostModel(str, Enum):
    """Cost calculation models per provider."""
    PER_TOKEN = "per_token"              # OpenAI, Anthropic per-token pricing
    PER_REQUEST = "per_request"          # Cohere, Hugging Face per-request
    FLAT_RATE = "flat_rate"              # Custom flat rate


@dataclass
class ProviderCapabilities:
    """Capabilities and constraints for a provider.
    
    Attributes:
        max_input_tokens: Maximum input tokens per request
        max_output_tokens: Maximum output tokens per response
        supports_streaming: Whether provider supports streaming responses
        supports_functions: Whether provider supports function/tool calling
        supports_vision: Whether provider supports image/vision inputs
        max_concurrent_requests: Rate limit concurrent requests
        cost_model: How cost is calculated (per-token, per-request, flat)
    """
    max_input_tokens: int
    max_output_tokens: int
    supports_streaming: bool = False
    supports_functions: bool = False
    supports_vision: bool = False
    max_concurrent_requests: int = 100
    cost_model: CostModel = CostModel.PER_TOKEN


@dataclass
class ProviderResponse:
    """Standard response format from any provider execution.
    
    Attributes:
        output: Execution result (usually string or JSON object)
        tokens_used: Total tokens consumed (input + output)
        tokens_input: Input tokens consumed
        tokens_output: Output tokens generated
        cost_usd: Cost in USD for this request
        latency_ms: Execution latency in milliseconds
        model_used: Model name that executed the task
        provider_id: Provider identifier (e.g., "openai", "anthropic")
        error: Error message if execution failed (None if successful)
        raw_response: Raw provider response for debugging
    """
    output: Any
    tokens_used: int
    cost_usd: float
    latency_ms: int
    model_used: str
    provider_id: str
    tokens_input: int = 0
    tokens_output: int = 0
    error: Optional[str] = None
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class ExecutionMetadata:
    """Metadata for provider execution decisions.
    
    Attributes:
        task_type: Type of task (summarize, classify, extract, etc.)
        complexity: Estimated complexity (simple, medium, complex)
        required_capabilities: Capabilities required from provider
        cost_sensitive: Whether to prioritize cost over quality
        latency_sensitive: Whether to prioritize latency over accuracy
        preferred_models: Preferred models in order of preference
        timeout_seconds: Maximum execution time
    """
    task_type: str
    complexity: str = "medium"
    required_capabilities: list[str] | None = None
    cost_sensitive: bool = False
    latency_sensitive: bool = False
    preferred_models: list[str] | None = None
    timeout_seconds: float = 30.0


class Provider(ABC):
    """Abstract base class for all provider implementations.
    
    This class defines the contract that all providers (OpenAI, Anthropic, etc.)
    must implement. Providers handle:
    - API client initialization and credential management
    - Request/response formatting
    - Token counting and cost calculation
    - Error handling and retry logic
    - Capability reporting
    
    Example:
        ```python
        provider = OpenAIProvider(
            api_key="sk-...",
            model="gpt-4-turbo-preview"
        )
        response = await provider.execute(
            prompt="Summarize this text: ...",
            metadata=ExecutionMetadata(task_type="summarize")
        )
        print(f"Cost: ${response.cost_usd:.4f}")
        ```
    """

    def __init__(self, provider_id: str, credentials: dict[str, Any]) -> None:
        """Initialize provider with credentials.
        
        Args:
            provider_id: Unique provider identifier (e.g., "openai", "anthropic")
            credentials: Provider-specific credentials dict
                - For OpenAI: {"api_key": "sk-...", "model": "gpt-4"}
                - For Anthropic: {"api_key": "sk-ant-...", "model": "claude-3-opus"}
        
        Raises:
            ValueError: If required credentials are missing
        """
        self.provider_id = provider_id
        self.credentials = credentials
        self._validate_credentials()

    @abstractmethod
    def _validate_credentials(self) -> None:
        """Validate that all required credentials are present.
        
        Should raise ValueError if any required credential is missing.
        
        Raises:
            ValueError: If credentials are invalid or incomplete
        """
        pass

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Report provider capabilities and constraints.
        
        Returns:
            ProviderCapabilities describing this provider's limits
        
        Example:
            ```python
            caps = provider.capabilities
            if caps.supports_vision and caps.supports_functions:
                # Can do complex multi-modal tasks
                pass
            ```
        """
        pass

    @property
    @abstractmethod
    def pricing_per_1k_tokens(self) -> dict[str, float]:
        """Cost per 1,000 tokens for input and output.
        
        Returns:
            {"input": 0.003, "output": 0.006} for cost per 1k tokens
        
        Note:
            Should reflect current provider pricing. Update quarterly.
        """
        pass

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        metadata: ExecutionMetadata | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Execute a task with the provider.
        
        This is the main entrypoint for executing a task. Implementation should:
        1. Format the prompt appropriately
        2. Call the provider API with appropriate parameters
        3. Handle errors and retries (exponential backoff)
        4. Count tokens accurately
        5. Calculate cost based on tokens
        6. Return standardized ProviderResponse
        
        Args:
            prompt: The task prompt/input to send to the provider
            metadata: ExecutionMetadata with task details and preferences
            **kwargs: Provider-specific options (temperature, max_tokens, etc.)
        
        Returns:
            ProviderResponse with output, tokens, cost, and latency
        
        Raises:
            ProviderError: If execution fails after retries
        
        Example:
            ```python
            response = await provider.execute(
                prompt="Classify this text: ...",
                metadata=ExecutionMetadata(task_type="classify"),
                temperature=0.3,
            )
            if not response.error:
                print(f"Result: {response.output}")
            ```
        """
        pass

    @abstractmethod
    async def execute_streaming(
        self,
        prompt: str,
        metadata: ExecutionMetadata | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Execute a task with streaming response chunks.
        
        For long outputs, streaming is more responsive. This method yields
        response chunks as they arrive from the provider.
        
        Args:
            prompt: The task prompt/input to send
            metadata: ExecutionMetadata with task details
            **kwargs: Provider-specific options
        
        Yields:
            Text chunks of the response as they arrive
        
        Raises:
            ProviderError: If streaming fails
        
        Example:
            ```python
            async for chunk in provider.execute_streaming(prompt):
                print(chunk, end="", flush=True)
            ```
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using provider's tokenizer.
        
        Token counting is critical for cost estimation and quota management.
        Should use the same tokenizer as the provider API.
        
        Args:
            text: Text to count tokens for
        
        Returns:
            Number of tokens in the text
        
        Note:
            - Results should match provider's actual token count
            - Some providers include special tokens (GPT uses <|endoftext|>)
            - Use official tokenizer libraries (tiktoken, anthropic.tokenizer)
        
        Example:
            ```python
            tokens = provider.count_tokens("This is a test")  # -> 4
            ```
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost in USD for an execution.
        
        Useful for:
        - Pre-filtering tasks that exceed budget
        - Comparing costs across providers
        - Cost optimization and routing decisions
        
        Args:
            input_tokens: Expected input tokens
            output_tokens: Expected output tokens
        
        Returns:
            Estimated cost in USD
        
        Example:
            ```python
            cost = provider.estimate_cost(
                input_tokens=500,
                output_tokens=200
            )
            if cost > max_budget:
                skip_this_task()
            ```
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """List available models for this provider.
        
        Returns:
            List of model identifiers available through this provider
        
        Example:
            ```python
            models = openai_provider.get_available_models()
            # ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"]
            ```
        """
        pass


class ProviderError(Exception):
    """Base exception for provider-related errors.
    
    Attributes:
        provider_id: Which provider failed
        message: Error description
        is_retryable: Whether error can be retried
        original_error: Original exception if wrapped
    """

    def __init__(
        self,
        provider_id: str,
        message: str,
        is_retryable: bool = False,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize provider error.
        
        Args:
            provider_id: Provider that failed
            message: Error message
            is_retryable: Whether error is transient/retryable
            original_error: Original exception for context
        """
        super().__init__(message)
        self.provider_id = provider_id
        self.is_retryable = is_retryable
        self.original_error = original_error


class RateLimitError(ProviderError):
    """Provider rate limit exceeded."""

    def __init__(
        self,
        provider_id: str,
        retry_after_seconds: int | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize rate limit error.
        
        Args:
            provider_id: Provider that rate limited us
            retry_after_seconds: Seconds to wait before retry
            message: Error message
        """
        msg = message or f"{provider_id} rate limit exceeded"
        super().__init__(
            provider_id=provider_id,
            message=msg,
            is_retryable=True,
        )
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(ProviderError):
    """Provider authentication failed (invalid credentials)."""

    def __init__(
        self,
        provider_id: str,
        message: str | None = None,
    ) -> None:
        """Initialize authentication error.
        
        Args:
            provider_id: Provider authentication failed
            message: Error message
        """
        msg = message or f"{provider_id} authentication failed"
        super().__init__(
            provider_id=provider_id,
            message=msg,
            is_retryable=False,  # Auth errors are not retryable
        )


class ProviderUnavailableError(ProviderError):
    """Provider service temporarily unavailable."""

    def __init__(
        self,
        provider_id: str,
        message: str | None = None,
    ) -> None:
        """Initialize unavailability error.
        
        Args:
            provider_id: Provider that's unavailable
            message: Error message
        """
        msg = message or f"{provider_id} service unavailable"
        super().__init__(
            provider_id=provider_id,
            message=msg,
            is_retryable=True,  # Service errors can be retried
        )
