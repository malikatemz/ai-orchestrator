"""Provider registry for managing multiple LLM providers.

The registry is the central hub for:
- Registering new providers
- Loading providers from environment configuration
- Selecting providers by name/type
- Managing provider credentials
- Listing available providers and models

This module uses a singleton pattern to ensure only one registry instance exists
across the application.
"""

import logging
from typing import Any

from .base import Provider, ProviderType


logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Central registry for managing multiple providers.
    
    The registry maintains a collection of provider implementations and provides
    methods to register, retrieve, and list providers. It abstracts away the
    complexity of managing multiple provider types.
    
    Attributes:
        _providers: Mapping of provider_id -> Provider instance
        _provider_types: Mapping of provider_id -> ProviderType
    
    Example:
        ```python
        registry = ProviderRegistry.instance()
        registry.register("openai", OpenAIProvider(...))
        registry.register("anthropic", AnthropicProvider(...))
        
        # Get specific provider
        openai = registry.get_provider("openai")
        
        # List all providers
        all_providers = registry.list_providers()
        ```
    """

    _instance: "ProviderRegistry | None" = None

    def __init__(self) -> None:
        """Initialize empty provider registry."""
        self._providers: dict[str, Provider] = {}
        self._provider_types: dict[str, ProviderType] = {}
        logger.debug("Provider registry initialized")

    @classmethod
    def instance(cls) -> "ProviderRegistry":
        """Get or create the singleton registry instance.
        
        Uses lazy initialization pattern to ensure registry is created only
        when first accessed. Thread-safe for typical usage patterns.
        
        Returns:
            The singleton ProviderRegistry instance
        
        Example:
            ```python
            registry = ProviderRegistry.instance()
            provider = registry.get_provider("openai")
            ```
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing).
        
        Clears the registry and allows creating a new instance. Should only
        be called in tests or during shutdown.
        
        Example:
            ```python
            ProviderRegistry.reset()
            # Next call to instance() creates fresh registry
            ```
        """
        if cls._instance is not None:
            logger.debug("Resetting provider registry")
            cls._instance._providers.clear()
            cls._instance._provider_types.clear()
        cls._instance = None

    def register(
        self,
        provider_id: str,
        provider: Provider,
        provider_type: ProviderType = ProviderType.LLM,
    ) -> None:
        """Register a provider instance.
        
        Registers a provider and makes it available for selection via
        get_provider(). If a provider with the same ID already exists,
        it is replaced (allowing for re-registration during startup).
        
        Args:
            provider_id: Unique identifier for this provider (e.g., "openai", "anthropic")
            provider: Provider instance to register
            provider_type: Type of provider (LLM, SCRAPER, EMBEDDING)
        
        Raises:
            TypeError: If provider does not inherit from Provider ABC
            ValueError: If provider_id is empty
        
        Example:
            ```python
            from providers.openai_provider import OpenAIProvider
            
            openai_provider = OpenAIProvider(
                api_key="sk-...",
                model="gpt-4"
            )
            registry.register("openai", openai_provider, ProviderType.LLM)
            ```
        """
        if not provider_id or not isinstance(provider_id, str):
            raise ValueError("provider_id must be a non-empty string")
        
        if not isinstance(provider, Provider):
            raise TypeError(
                f"provider must inherit from Provider base class, "
                f"got {type(provider).__name__}"
            )
        
        self._providers[provider_id] = provider
        self._provider_types[provider_id] = provider_type
        
        logger.info(
            f"Registered provider: {provider_id} "
            f"(type={provider_type}, model={getattr(provider, 'model', 'N/A')})"
        )

    def get_provider(self, provider_id: str) -> Provider:
        """Retrieve a provider by ID.
        
        Args:
            provider_id: ID of the provider to retrieve
        
        Returns:
            The Provider instance
        
        Raises:
            KeyError: If provider_id is not registered
        
        Example:
            ```python
            openai = registry.get_provider("openai")
            response = await openai.execute(prompt)
            ```
        """
        if provider_id not in self._providers:
            available = ", ".join(self._providers.keys())
            raise KeyError(
                f"Provider '{provider_id}' not registered. "
                f"Available: {available or 'none'}"
            )
        
        return self._providers[provider_id]

    def get_provider_by_type(self, provider_type: ProviderType) -> list[Provider]:
        """Get all providers of a specific type.
        
        Useful for finding all LLM providers or all scrapers, for example.
        
        Args:
            provider_type: Type of provider to search for
        
        Returns:
            List of Provider instances matching the type
        
        Example:
            ```python
            llm_providers = registry.get_provider_by_type(ProviderType.LLM)
            scraper_providers = registry.get_provider_by_type(ProviderType.SCRAPER)
            ```
        """
        return [
            provider
            for pid, provider in self._providers.items()
            if self._provider_types.get(pid) == provider_type
        ]

    def list_providers(self) -> list[str]:
        """List all registered provider IDs.
        
        Returns:
            List of provider IDs in registration order
        
        Example:
            ```python
            providers = registry.list_providers()
            print(f"Available: {providers}")  # ['openai', 'anthropic', ...]
            ```
        """
        return list(self._providers.keys())

    def list_models(self) -> dict[str, list[str]]:
        """List all available models grouped by provider.
        
        Returns:
            Mapping of provider_id -> list of available models
        
        Example:
            ```python
            models = registry.list_models()
            # {
            #     "openai": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            #     "anthropic": ["claude-3-opus", "claude-3-sonnet"],
            # }
            ```
        """
        result: dict[str, list[str]] = {}
        for provider_id, provider in self._providers.items():
            try:
                result[provider_id] = provider.get_available_models()
            except Exception as e:
                logger.warning(
                    f"Failed to get models for {provider_id}: {e}"
                )
                result[provider_id] = []
        
        return result

    def is_registered(self, provider_id: str) -> bool:
        """Check if a provider is registered.
        
        Args:
            provider_id: Provider ID to check
        
        Returns:
            True if provider is registered, False otherwise
        
        Example:
            ```python
            if registry.is_registered("openai"):
                openai = registry.get_provider("openai")
            else:
                logger.warning("OpenAI provider not configured")
            ```
        """
        return provider_id in self._providers

    def unregister(self, provider_id: str) -> None:
        """Unregister a provider (mainly for testing).
        
        Args:
            provider_id: Provider to remove
        
        Raises:
            KeyError: If provider is not registered
        
        Example:
            ```python
            registry.unregister("openai")
            ```
        """
        if provider_id not in self._providers:
            raise KeyError(f"Provider '{provider_id}' not registered")
        
        del self._providers[provider_id]
        del self._provider_types[provider_id]
        logger.debug(f"Unregistered provider: {provider_id}")

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics for monitoring.
        
        Returns:
            Dict with counts and status of registered providers
        
        Example:
            ```python
            stats = registry.get_stats()
            print(f"Registered: {stats['provider_count']} providers")
            ```
        """
        providers_by_type = {}
        for provider_id, provider in self._providers.items():
            ptype = self._provider_types.get(provider_id)
            if ptype not in providers_by_type:
                providers_by_type[ptype] = []
            providers_by_type[ptype].append(provider_id)
        
        return {
            "provider_count": len(self._providers),
            "providers": self.list_providers(),
            "providers_by_type": {k.value: v for k, v in providers_by_type.items()},
            "models_available": sum(
                len(models)
                for models in self.list_models().values()
            ),
        }

    def __repr__(self) -> str:
        """Return string representation of registry."""
        providers = ", ".join(self.list_providers())
        return f"ProviderRegistry(providers=[{providers}])"
