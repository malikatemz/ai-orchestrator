"""Scoring engine for agent selection based on performance history"""

from typing import List, Dict, Optional
from statistics import mean
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timedelta

from ..models import AgentStats
from ..time_utils import utc_now
from .registry import AgentProvider, list_providers_for_task_type


def get_provider_stats(
    db: Session,
    provider_id: str,
    task_type: str,
    lookback_days: int = 7
) -> Dict[str, float]:
    """
    Retrieve provider performance statistics from the last N days.
    
    Returns:
      {
        "success_rate": 0.95,
        "avg_latency_ms": 450,
        "avg_cost_usd": 0.001,
        "total_tasks": 100,
      }
    """
    cutoff_date = utc_now() - timedelta(days=lookback_days)
    
    stats = db.query(AgentStats).filter(
        AgentStats.provider_id == provider_id,
        AgentStats.task_type == task_type,
        AgentStats.recorded_at >= cutoff_date,
    ).all()
    
    if not stats:
        # No history: default to optimistic (1.0 success rate)
        return {
            "success_rate": 1.0,
            "avg_latency_ms": 500,
            "avg_cost_usd": 0.001,
            "total_tasks": 0,
        }
    
    successes = [s for s in stats if s.success]
    success_rate = len(successes) / len(stats) if stats else 1.0
    
    latencies = [s.latency_ms for s in stats if s.latency_ms]
    avg_latency_ms = mean(latencies) if latencies else 500
    
    costs = [s.cost_usd for s in stats if s.cost_usd]
    avg_cost_usd = mean(costs) if costs else 0.001
    
    return {
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency_ms,
        "avg_cost_usd": avg_cost_usd,
        "total_tasks": len(stats),
    }


def normalize_metric(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalize a metric to [0, 1] range"""
    if max_val <= min_val:
        return 1.0
    return (value - min_val) / (max_val - min_val)


def score_provider(
    db: Session,
    provider: AgentProvider,
    task_type: str,
) -> float:
    """
    Score a provider for a given task type using weighted heuristic.
    
    Formula:
      score = (success_rate * 0.5) + (speed_score * 0.3) + (cost_score * 0.2)
    
    Where:
      - success_rate: Historical success rate (0-1)
      - speed_score: Inverse of normalized latency (0-1)
      - cost_score: Inverse of normalized cost (0-1)
    
    Returns score in range [0, 1], where 1.0 is best.
    """
    # Get historical stats
    stats = get_provider_stats(db, provider.id, task_type)
    success_rate = stats["success_rate"]
    
    # Collect all candidates to get normalization bounds
    all_providers = list_providers_for_task_type(task_type)
    all_stats = [get_provider_stats(db, p.id, task_type) for p in all_providers]
    
    latencies = [s["avg_latency_ms"] for s in all_stats]
    costs = [s["avg_cost_usd"] for s in all_stats]
    
    min_latency = min(latencies) if latencies else 300
    max_latency = max(latencies) if latencies else 1000
    min_cost = min(costs) if costs else 0.0001
    max_cost = max(costs) if costs else 0.01
    
    # Normalize latency (lower is better, so invert)
    latency_norm = normalize_metric(stats["avg_latency_ms"], min_latency, max_latency)
    speed_score = 1.0 - latency_norm if latency_norm < 1.0 else 0.0
    
    # Normalize cost (lower is better, so invert)
    cost_norm = normalize_metric(stats["avg_cost_usd"], min_cost, max_cost)
    cost_score = 1.0 - cost_norm if cost_norm < 1.0 else 0.0
    
    # Weighted formula
    final_score = (
        (success_rate * 0.5) +
        (speed_score * 0.3) +
        (cost_score * 0.2)
    )
    
    return min(max(final_score, 0.0), 1.0)  # Clamp to [0, 1]


def rank_providers(
    db: Session,
    task_type: str,
    max_count: Optional[int] = None,
) -> List[tuple[AgentProvider, float]]:
    """
    Rank all providers for a task type by score.
    
    Returns list of (provider, score) tuples in descending score order.
    """
    candidates = list_providers_for_task_type(task_type)
    
    scored = [
        (provider, score_provider(db, provider, task_type))
        for provider in candidates
    ]
    
    # Sort by score descending
    ranked = sorted(scored, key=lambda x: x[1], reverse=True)
    
    if max_count:
        ranked = ranked[:max_count]
    
    return ranked
