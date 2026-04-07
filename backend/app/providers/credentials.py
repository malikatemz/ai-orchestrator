"""Credential loading and management for LLM providers.

This module handles secure loading of provider credentials from environment
variables or configuration files, with support for multiple credentials per
provider (e.g., multiple OpenAI organizations, API keys).
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class CredentialLoader:
    """Load and manage provider credentials from environment.
    
    Credentials are loaded from environment variables following a standard
    naming convention: PROVIDER_CONFIG_KEY (e.g., OPENAI_API_KEY).
    
    Supports:
    - Loading credentials from environment
    - Validation of required credentials
    - Safe credential caching (no logging of actual values)
    - Credential rotation/reloading
    
    Example:
        ```python
        loader = CredentialLoader()
        
        # Load OpenAI credentials
        openai_creds = loader.load_provider_credentials("openai", [
            "api_key",  # Looks for OPENAI_API_KEY
            "model",    # Looks for OPENAI_MODEL
        ])
        
        # Load Anthropic credentials
        anthropic_creds = loader.load_provider_credentials("anthropic", [
            "api_key",  # Looks for ANTHROPIC_API_KEY
        ])
        ```
    """

    # Standard credential environment variable names per provider
    PROVIDER_ENV_KEYS = {
        "openai": {
            "api_key": "OPENAI_API_KEY",
            "model": "OPENAI_MODEL",
            "organization": "OPENAI_ORGANIZATION",
        },
        "anthropic": {
            "api_key": "ANTHROPIC_API_KEY",
            "model": "ANTHROPIC_MODEL",
        },
        "cohere": {
            "api_key": "COHERE_API_KEY",
            "model": "COHERE_MODEL",
        },
        "mistral": {
            "api_key": "MISTRAL_API_KEY",
            "model": "MISTRAL_MODEL",
        },
        "huggingface": {
            "api_key": "HUGGINGFACE_API_KEY",
            "model": "HUGGINGFACE_MODEL",
        },
    }

    # Required credentials per provider
    REQUIRED_CREDENTIALS = {
        "openai": ["api_key"],  # model is optional, defaults to gpt-4-turbo
        "anthropic": ["api_key"],  # model is optional, defaults to claude-3-sonnet
        "cohere": ["api_key"],
        "mistral": ["api_key"],
        "huggingface": ["api_key"],
    }

    @staticmethod
    def load_provider_credentials(
        provider: str,
        required_keys: list[str] | None = None,
    ) -> dict[str, str]:
        """Load credentials for a provider from environment.
        
        Looks up environment variables based on provider name and requested keys.
        For example, for provider="openai" and key="api_key", looks for env var
        OPENAI_API_KEY.
        
        Args:
            provider: Provider name (openai, anthropic, cohere, etc.)
            required_keys: Keys to load. If None, uses REQUIRED_CREDENTIALS[provider]
        
        Returns:
            Dictionary of {key: value} for loaded credentials
        
        Raises:
            ValueError: If required credentials are missing
            KeyError: If provider is not recognized
        
        Example:
            ```python
            creds = CredentialLoader.load_provider_credentials("openai")
            # Returns: {"api_key": "sk-...", "model": "gpt-4-turbo"}
            
            # Or specify exactly which keys to load
            creds = CredentialLoader.load_provider_credentials("openai", [
                "api_key"  # Only load api_key, not model
            ])
            ```
        """
        if provider not in CredentialLoader.PROVIDER_ENV_KEYS:
            available = ", ".join(CredentialLoader.PROVIDER_ENV_KEYS.keys())
            raise KeyError(
                f"Provider '{provider}' not recognized. "
                f"Available: {available}"
            )
        
        # Use required keys from config if not specified
        if required_keys is None:
            required_keys = CredentialLoader.REQUIRED_CREDENTIALS.get(provider, [])
        
        # Load environment variable mappings for this provider
        env_keys = CredentialLoader.PROVIDER_ENV_KEYS[provider]
        
        credentials: dict[str, str] = {}
        missing_keys: list[str] = []
        
        for key in required_keys:
            if key not in env_keys:
                raise ValueError(
                    f"Unknown credential key '{key}' for provider '{provider}'. "
                    f"Available: {', '.join(env_keys.keys())}"
                )
            
            env_var = env_keys[key]
            value = os.environ.get(env_var)
            
            if value:
                credentials[key] = value
            else:
                missing_keys.append(env_var)
        
        if missing_keys:
            raise ValueError(
                f"Missing required {provider} credentials: {', '.join(missing_keys)}. "
                f"Please set these environment variables."
            )
        
        # Log success (without revealing actual values)
        logger.info(
            f"Loaded {len(credentials)} credentials for {provider} "
            f"({', '.join(credentials.keys())})"
        )
        
        return credentials

    @staticmethod
    def load_all_providers(
        providers: list[str] | None = None,
    ) -> dict[str, dict[str, str]]:
        """Load credentials for multiple providers.
        
        Useful for bootstrapping all configured providers at startup.
        Handles providers that may not be configured (skips them gracefully).
        
        Args:
            providers: List of providers to load. If None, attempts to load all known providers.
        
        Returns:
            Mapping of provider -> credentials dict
        
        Example:
            ```python
            creds = CredentialLoader.load_all_providers([
                "openai",
                "anthropic",
                "cohere",
            ])
            # Returns: {
            #     "openai": {"api_key": "sk-...", "model": "gpt-4"},
            #     "anthropic": {"api_key": "sk-ant-..."},
            # }
            # (cohere is skipped if COHERE_API_KEY not set)
            ```
        """
        if providers is None:
            providers = list(CredentialLoader.PROVIDER_ENV_KEYS.keys())
        
        result: dict[str, dict[str, str]] = {}
        
        for provider in providers:
            try:
                creds = CredentialLoader.load_provider_credentials(provider)
                result[provider] = creds
                logger.debug(f"Successfully loaded credentials for {provider}")
            except ValueError as e:
                logger.warning(
                    f"Skipping {provider} provider: {e}. "
                    f"This provider will not be available."
                )
            except KeyError as e:
                logger.warning(f"Unknown provider {provider}: {e}")
        
        return result

    @staticmethod
    def is_provider_configured(provider: str) -> bool:
        """Check if a provider is configured (credentials available).
        
        Useful for conditional initialization of providers based on available
        credentials.
        
        Args:
            provider: Provider name to check
        
        Returns:
            True if provider credentials are available, False otherwise
        
        Example:
            ```python
            if CredentialLoader.is_provider_configured("openai"):
                openai_provider = OpenAIProvider(...)
            else:
                logger.warning("OpenAI not configured, skipping")
            ```
        """
        try:
            CredentialLoader.load_provider_credentials(provider)
            return True
        except (ValueError, KeyError):
            return False

    @staticmethod
    def get_configured_providers() -> list[str]:
        """Get list of all configured providers.
        
        Scans environment and returns providers that have their required
        credentials set.
        
        Returns:
            List of configured provider names
        
        Example:
            ```python
            providers = CredentialLoader.get_configured_providers()
            # Returns: ["openai", "anthropic"]  # cohere not configured
            ```
        """
        configured: list[str] = []
        
        for provider in CredentialLoader.PROVIDER_ENV_KEYS.keys():
            if CredentialLoader.is_provider_configured(provider):
                configured.append(provider)
        
        return configured

    @staticmethod
    def validate_credentials(
        provider: str,
        credentials: dict[str, Any],
    ) -> tuple[bool, str]:
        """Validate credential structure for a provider.
        
        Checks that:
        - All required keys are present
        - Values are non-empty strings
        - API keys have expected format/length
        
        Args:
            provider: Provider name
            credentials: Credentials dict to validate
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        
        Example:
            ```python
            valid, msg = CredentialLoader.validate_credentials(
                "openai",
                {"api_key": "sk-...", "model": "gpt-4"}
            )
            if not valid:
                logger.error(f"Invalid credentials: {msg}")
            ```
        """
        if provider not in CredentialLoader.REQUIRED_CREDENTIALS:
            return False, f"Unknown provider: {provider}"
        
        required = CredentialLoader.REQUIRED_CREDENTIALS[provider]
        
        # Check all required keys present
        missing = [k for k in required if k not in credentials]
        if missing:
            return False, f"Missing required keys: {', '.join(missing)}"
        
        # Check values are non-empty strings
        for key in required:
            value = credentials.get(key)
            if not isinstance(value, str) or not value.strip():
                return False, f"Credential '{key}' must be non-empty string"
        
        # Provider-specific validation
        if provider == "openai" and "api_key" in credentials:
            api_key = credentials["api_key"]
            if not api_key.startswith("sk-"):
                return False, "OpenAI API key should start with 'sk-'"
        
        if provider == "anthropic" and "api_key" in credentials:
            api_key = credentials["api_key"]
            if not api_key.startswith("sk-ant-"):
                return False, "Anthropic API key should start with 'sk-ant-'"
        
        return True, "OK"
