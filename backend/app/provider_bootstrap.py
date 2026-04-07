"""Provider registry bootstrap and initialization for Week 2 routing engine.

This module initializes the provider registry with all available providers
on application startup. It's called from main.py to ensure providers are
registered before any task execution requests arrive.

Providers Initialized:
- OpenAI (gpt-4, gpt-4-turbo, gpt-4o, gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet, claude-3-haiku)
- Cohere (command-r, command-r-plus) - future
- Custom providers can be added here

Example:
    >>> from app.provider_bootstrap import bootstrap_providers
    >>> bootstrap_providers()  # Call once on app startup
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def bootstrap_providers() -> None:
    """Initialize the provider registry with all supported providers.
    
    This function is called once during application startup to register
    all available AI providers with the ProviderRegistry singleton.
    
    For each provider, it:
    1. Creates an instance with credentials from environment variables
    2. Registers with the singleton ProviderRegistry
    3. Logs initialization status
    
    Environment Variables (Optional):
        OPENAI_API_KEY: OpenAI API key for GPT models
        ANTHROPIC_API_KEY: Anthropic API key for Claude models
        COHERE_API_KEY: Cohere API key for Command models (future)
    
    Raises:
        Exception: If critical provider registration fails (logs and continues for optional providers)
    
    Side Effects:
        - Modifies ProviderRegistry singleton
        - Logs provider initialization status
        - Sets up provider credentials from environment
    
    Example:
        >>> bootstrap_providers()
        >>> registry = ProviderRegistry.instance()
        >>> providers = registry.list_providers()
        >>> print(f"Registered {len(providers)} providers")
    """
    from .providers.registry import ProviderRegistry
    from .providers.credentials import CredentialLoader
    import os
    
    registry = ProviderRegistry.instance()
    credential_loader = CredentialLoader()
    
    # ===== OpenAI Provider =====
    try:
        from .providers.openai_provider_new import OpenAIProvider
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            # Register all OpenAI models
            openai_models = ["gpt-4", "gpt-4-turbo-preview", "gpt-4o", "gpt-3.5-turbo"]
            
            for model in openai_models:
                try:
                    provider = OpenAIProvider(api_key=openai_api_key, model=model)
                    registry.register(provider)
                    logger.info(f"✓ Registered OpenAI provider: {model}")
                except Exception as e:
                    logger.warning(f"Failed to register OpenAI {model}: {str(e)}")
        else:
            logger.info("⊘ OPENAI_API_KEY not set, skipping OpenAI provider registration")
    except Exception as e:
        logger.error(f"✗ Failed to bootstrap OpenAI provider: {str(e)}")
    
    # ===== Anthropic Provider =====
    try:
        from .providers.anthropic_provider_new import AnthropicProvider
        
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_api_key:
            # Register all Claude 3 models
            anthropic_models = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
            
            for model in anthropic_models:
                try:
                    provider = AnthropicProvider(api_key=anthropic_api_key, model=model)
                    registry.register(provider)
                    logger.info(f"✓ Registered Anthropic provider: {model}")
                except Exception as e:
                    logger.warning(f"Failed to register Anthropic {model}: {str(e)}")
        else:
            logger.info("⊘ ANTHROPIC_API_KEY not set, skipping Anthropic provider registration")
    except Exception as e:
        logger.error(f"✗ Failed to bootstrap Anthropic provider: {str(e)}")
    
    # ===== Cohere Provider (Future) =====
    # try:
    #     from .providers.cohere_provider import CohereProvider
    #     cohere_api_key = os.getenv("COHERE_API_KEY")
    #     if cohere_api_key:
    #         cohere_models = ["command-r", "command-r-plus"]
    #         for model in cohere_models:
    #             provider = CohereProvider(api_key=cohere_api_key, model=model)
    #             registry.register(provider)
    #             logger.info(f"✓ Registered Cohere provider: {model}")
    #     else:
    #         logger.info("⊘ COHERE_API_KEY not set, skipping Cohere provider registration")
    # except Exception as e:
    #     logger.error(f"✗ Failed to bootstrap Cohere provider: {str(e)}")
    
    # ===== Summary =====
    providers = registry.list_providers()
    logger.info(f"Provider registry initialized with {len(providers)} provider instances")
    
    if not providers:
        logger.warning("⚠ No providers registered! Set API key environment variables for at least one provider.")
    else:
        logger.info(f"Active providers: {', '.join([p.provider_id for p in providers])}")


def get_provider_summary() -> dict[str, Any]:
    """Get a summary of registered providers for diagnostics.
    
    Returns:
        Dictionary with provider registration status:
        - total_providers: Number of registered provider instances
        - providers_by_type: Count per provider type (e.g., "openai": 4)
        - models_available: List of all registered model names
        - provider_details: Detailed info per provider (id, model, capabilities)
    
    Example:
        >>> summary = get_provider_summary()
        >>> print(f"Total providers: {summary['total_providers']}")
        >>> print(f"Models: {summary['models_available']}")
    """
    from .providers.registry import ProviderRegistry
    
    registry = ProviderRegistry.instance()
    providers = registry.list_providers()
    
    provider_types = {}
    models = []
    
    for provider in providers:
        # Count by provider ID
        provider_types[provider.provider_id] = provider_types.get(provider.provider_id, 0) + 1
        models.append(provider.model)
    
    return {
        "total_providers": len(providers),
        "providers_by_type": provider_types,
        "models_available": sorted(models),
        "provider_details": [
            {
                "id": p.provider_id,
                "model": p.model,
                "capabilities": {
                    "max_input_tokens": p.capabilities.max_input_tokens,
                    "max_output_tokens": p.capabilities.max_output_tokens,
                    "supports_streaming": p.capabilities.supports_streaming,
                    "supports_vision": p.capabilities.supports_vision,
                }
            }
            for p in providers
        ]
    }
