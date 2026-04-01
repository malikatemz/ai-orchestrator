"""Agent provider registry with metadata and cost information"""

from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class ProviderType(str, Enum):
    """Provider technology type"""
    LLM = "llm"
    WEB_SCRAPER = "web_scraper"


@dataclass
class AgentProvider:
    """Registered agent provider with capabilities and cost metrics"""
    
    id: str
    name: str
    provider_type: ProviderType
    model_id: str
    
    # Cost & Performance
    cost_per_1k_tokens: float  # Cost in USD per 1000 tokens
    avg_latency_ms: int  # Average response time
    
    # Capabilities
    supports_types: List[str] = field(default_factory=list)  # Task types: summarize, classify, extract, etc.
    max_tokens: int = 4096
    
    # Configuration
    base_url: str = ""  # For self-hosted / custom endpoints
    requires_api_key: bool = True
    api_key_env_var: str = ""


# ============ Provider Registry ============

PROVIDER_REGISTRY: Dict[str, AgentProvider] = {
    # OpenAI Models
    "openai-gpt4o": AgentProvider(
        id="openai-gpt4o",
        name="OpenAI GPT-4o",
        provider_type=ProviderType.LLM,
        model_id="gpt-4o",
        cost_per_1k_tokens=0.005,
        avg_latency_ms=800,
        supports_types=["summarize", "classify", "extract", "analyze"],
        max_tokens=4096,
        api_key_env_var="OPENAI_API_KEY",
    ),
    
    "openai-gpt4o-mini": AgentProvider(
        id="openai-gpt4o-mini",
        name="OpenAI GPT-4o Mini",
        provider_type=ProviderType.LLM,
        model_id="gpt-4o-mini",
        cost_per_1k_tokens=0.0002,
        avg_latency_ms=400,
        supports_types=["summarize", "classify", "extract"],
        max_tokens=4096,
        api_key_env_var="OPENAI_API_KEY",
    ),
    
    # Anthropic Models
    "anthropic-sonnet": AgentProvider(
        id="anthropic-sonnet",
        name="Anthropic Claude 3.5 Sonnet",
        provider_type=ProviderType.LLM,
        model_id="claude-3-5-sonnet-20241022",
        cost_per_1k_tokens=0.003,
        avg_latency_ms=700,
        supports_types=["summarize", "analyze", "extract", "classify"],
        max_tokens=4096,
        api_key_env_var="ANTHROPIC_API_KEY",
    ),
    
    # Mistral Models
    "mistral-small": AgentProvider(
        id="mistral-small",
        name="Mistral Small (Latest)",
        provider_type=ProviderType.LLM,
        model_id="mistral-small-latest",
        cost_per_1k_tokens=0.0001,
        avg_latency_ms=300,
        supports_types=["summarize", "classify", "extract"],
        max_tokens=4096,
        api_key_env_var="MISTRAL_API_KEY",
    ),
    
    # Web Scraper
    "scraper": AgentProvider(
        id="scraper",
        name="HTTP + BeautifulSoup Scraper",
        provider_type=ProviderType.WEB_SCRAPER,
        model_id="scraper-v1",
        cost_per_1k_tokens=0.0,
        avg_latency_ms=500,
        supports_types=["scrape"],
        max_tokens=999999,  # No token limit
        requires_api_key=False,
    ),
}


def get_provider(provider_id: str) -> AgentProvider:
    """Retrieve provider by ID"""
    if provider_id not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_id}")
    return PROVIDER_REGISTRY[provider_id]


def list_providers_for_task_type(task_type: str) -> List[AgentProvider]:
    """Get all providers that support a specific task type"""
    return [
        provider
        for provider in PROVIDER_REGISTRY.values()
        if task_type in provider.supports_types
    ]
