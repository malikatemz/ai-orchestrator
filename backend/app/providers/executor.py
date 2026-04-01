"""Provider implementation execution logic"""

import asyncio
import time
from typing import Dict, Any, Optional
import logging

from ..agents.registry import AgentProvider, ProviderType
from ..config import get_settings
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .mistral_provider import MistralProvider
from .scraper_provider import ScraperProvider

logger = logging.getLogger(__name__)


class TaskExecutionError(Exception):
    """Provider execution failed"""
    pass


async def execute_task(
    provider: AgentProvider,
    task_type: str,
    input_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute task using specified provider.
    
    Returns:
      {
        "output": result_data,
        "tokens_used": int,
        "latency_ms": int,
        "cost_usd": float,
      }
    
    Raises:
      TaskExecutionError on failure
    """
    settings = get_settings()
    start_time = time.time()
    
    try:
        if provider.provider_type == ProviderType.LLM:
            result = await _execute_llm(provider, task_type, input_json)
        elif provider.provider_type == ProviderType.WEB_SCRAPER:
            result = await _execute_scraper(task_type, input_json)
        else:
            raise TaskExecutionError(f"Unknown provider type: {provider.provider_type}")
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "output": result.get("output"),
            "tokens_used": result.get("tokens_used", 0),
            "latency_ms": latency_ms,
            "cost_usd": result.get("cost_usd", 0.0),
        }
    
    except Exception as e:
        logger.error(f"Provider {provider.id} failed: {str(e)}")
        raise TaskExecutionError(f"Execution failed: {str(e)}") from e


async def _execute_llm(
    provider: AgentProvider,
    task_type: str,
    input_json: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute task via LLM provider"""
    settings = get_settings()
    
    if provider.id.startswith("openai"):
        api_key = settings.openai_api_key
        if not api_key:
            raise TaskExecutionError("OPENAI_API_KEY not configured")
        llm = OpenAIProvider(api_key=api_key, model=provider.model_id)
        return await llm.execute(task_type, input_json)
    
    elif provider.id.startswith("anthropic"):
        api_key = settings.anthropic_api_key
        if not api_key:
            raise TaskExecutionError("ANTHROPIC_API_KEY not configured")
        llm = AnthropicProvider(api_key=api_key, model=provider.model_id)
        return await llm.execute(task_type, input_json)
    
    elif provider.id.startswith("mistral"):
        api_key = settings.mistral_api_key
        if not api_key:
            raise TaskExecutionError("MISTRAL_API_KEY not configured")
        llm = MistralProvider(api_key=api_key, model=provider.model_id)
        return await llm.execute(task_type, input_json)
    
    else:
        raise TaskExecutionError(f"Unknown LLM provider: {provider.id}")


async def _execute_scraper(
    task_type: str,
    input_json: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute scraping task"""
    scraper = ScraperProvider()
    return await scraper.execute(task_type, input_json)
