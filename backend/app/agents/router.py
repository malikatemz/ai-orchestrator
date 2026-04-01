"""Agent selection router - picks best provider for task"""

from typing import Optional, List
from sqlalchemy.orm import Session

from ..models import AgentStats, Task
from .registry import AgentProvider, list_providers_for_task_type
from .scorer import rank_providers


class ProviderSelectionError(Exception):
    """No suitable provider found for task"""
    pass


def select_agent(
    db: Session,
    task_type: str,
    exclude_providers: Optional[List[str]] = None,
) -> tuple[AgentProvider, List[AgentProvider]]:
    """
    Select best provider for a task type.
    
    Returns:
      (selected_provider, ranked_alternatives)
    
    Raises:
      ProviderSelectionError if no suitable providers available
    """
    exclude_providers = exclude_providers or []
    
    # Get ranked candidates
    ranked = rank_providers(db, task_type)
    
    if not ranked:
        raise ProviderSelectionError(f"No providers support task type: {task_type}")
    
    # Filter out excluded providers
    available = [
        (provider, score)
        for provider, score in ranked
        if provider.id not in exclude_providers
    ]
    
    if not available:
        raise ProviderSelectionError(
            f"All providers for {task_type} have been excluded or failed. "
            f"Exclude list: {exclude_providers}"
        )
    
    # Select best available provider
    selected_provider, _ = available[0]
    
    # Return selected + alternatives (excluding selected)
    alternatives = [p for p, _ in available[1:]]
    
    return selected_provider, alternatives


def record_provider_usage(
    db: Session,
    org_id,
    provider_id: str,
    task_type: str,
    success: bool,
    latency_ms: int,
    cost_usd: float = 0.0,
    token_count: Optional[int] = None,
) -> None:
    """
    Record provider usage statistics for future scoring.
    
    This should be called after each task execution to build the
    performance history used by the scoring engine.
    """
    stat = AgentStats(
        org_id=org_id,
        provider_id=provider_id,
        task_type=task_type,
        success=success,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        token_count=token_count,
    )
    db.add(stat)
    db.commit()


def get_fallback_chain(
    db: Session,
    task_type: str,
    failed_providers: Optional[List[str]] = None,
    max_fallbacks: int = 3,
) -> List[AgentProvider]:
    """
    Get ordered fallback providers if primary selection fails.
    
    Excludes any providers that have already failed.
    Returns up to max_fallbacks providers.
    """
    failed_providers = failed_providers or []
    
    try:
        selected, alternatives = select_agent(db, task_type, exclude_providers=failed_providers)
        # Return selected + next alternatives up to max
        return [selected] + alternatives[:max_fallbacks-1]
    except ProviderSelectionError:
        return []
