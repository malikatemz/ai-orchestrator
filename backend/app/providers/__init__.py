"""Multi-provider LLM and scraper executor.

This package provides:
- Abstract provider interface (base.py)
- Provider registry for managing multiple providers (registry.py)
- Credential loading from environment (credentials.py)
- Task execution engine (executor.py)
- Specific provider implementations (openai_provider.py, anthropic_provider.py, etc.)

Example:
    ```python
    from app.providers import ProviderRegistry, CredentialLoader
    
    # Load credentials from environment
    creds = CredentialLoader.load_all_providers()
    
    # Register providers
    registry = ProviderRegistry.instance()
    registry.register("openai", openai_provider)
    registry.register("anthropic", anthropic_provider)
    
    # Execute task with routing
    from app.providers.executor import execute_task
    result = await execute_task(
        provider_id="openai",
        task_type="summarize",
        input_json={"text": "..."},
    )
    ```
"""

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
from .registry import ProviderRegistry
from .credentials import CredentialLoader
from .executor import execute_task, TaskExecutionError

__all__ = [
    # Base classes and types
    "Provider",
    "ProviderCapabilities",
    "ProviderResponse",
    "ProviderType",
    "ExecutionMetadata",
    "CostModel",
    # Exceptions
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ProviderUnavailableError",
    # Registry and management
    "ProviderRegistry",
    "CredentialLoader",
    # Execution
    "execute_task",
    "TaskExecutionError",
]
