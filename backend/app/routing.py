"""Intelligent routing engine for multi-provider task execution.

This module provides sophisticated task-to-provider routing based on:
- Task complexity and type
- Cost sensitivity vs latency sensitivity
- Provider capabilities (vision, functions, etc.)
- Provider pricing and latency profiles
- Fallback chains for reliability

Routing strategies support cost optimization, latency optimization, accuracy
optimization, or balanced approaches.
"""

import logging
from dataclasses import dataclass
from typing import Any

from .providers.base import ExecutionMetadata, Provider, ProviderType, ProviderCapabilities
from .providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class RoutingStrategy:
    """Configuration for intelligent task routing.
    
    Attributes:
        strategy_type: Routing strategy (cost, latency, accuracy, balanced)
        fallback_chain: List of provider IDs in fallback order
        cost_threshold: Maximum cost threshold in USD
        latency_threshold_ms: Maximum acceptable latency
        prefer_vision: Prefer providers with vision capabilities
        prefer_functions: Prefer providers with function calling
    
    Example:
        ```python
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["openai", "anthropic", "demo"],
            cost_threshold=0.50,
        )
        ```
    """
    strategy_type: str  # cost, latency, accuracy, balanced
    fallback_chain: list[str]  # Provider IDs in priority order
    cost_threshold: float = 0.50  # USD
    latency_threshold_ms: float = 5000.0  # milliseconds
    prefer_vision: bool = False
    prefer_functions: bool = False


@dataclass
class RoutingScore:
    """Score for a provider in routing decision.
    
    Attributes:
        provider_id: Provider ID being scored
        strategy: Routing strategy used
        cost_score: Score for cost optimization (0-1, higher is cheaper)
        latency_score: Score for latency optimization (0-1, higher is faster)
        accuracy_score: Score for accuracy (0-1, higher is more capable)
        capability_score: Score for capability matching (0-1)
        combined_score: Weighted combination of above scores (0-1)
        reason: Human-readable explanation of scoring
    """
    provider_id: str
    strategy: str
    cost_score: float
    latency_score: float
    accuracy_score: float
    capability_score: float
    combined_score: float
    reason: str


class RoutingEngine:
    """Intelligent task-to-provider router.
    
    Routes tasks to optimal providers based on:
    1. Task requirements (complexity, type, capabilities needed)
    2. Routing strategy (cost vs latency vs accuracy)
    3. Provider capabilities and pricing
    4. Historical performance (latency, reliability)
    
    Example:
        ```python
        router = RoutingEngine(registry)
        
        # Route a simple summarization task
        provider_id = router.select_provider(
            task=task,
            metadata=ExecutionMetadata(task_type="summarize", cost_sensitive=True),
            strategy=RoutingStrategy(
                strategy_type="cost",
                fallback_chain=["gpt-3.5-turbo", "claude-haiku", "demo"],
            )
        )
        
        provider = registry.get_provider(provider_id)
        response = await provider.execute(prompt, metadata)
        ```
    """

    # Default latency and cost profiles (estimates in milliseconds and USD)
    PROVIDER_PROFILES = {
        "openai": {
            "gpt-4": {"avg_latency_ms": 2000, "avg_cost": 0.05},
            "gpt-4-turbo-preview": {"avg_latency_ms": 2500, "avg_cost": 0.015},
            "gpt-4o": {"avg_latency_ms": 1500, "avg_cost": 0.01},
            "gpt-3.5-turbo": {"avg_latency_ms": 800, "avg_cost": 0.002},
        },
        "anthropic": {
            "claude-3-opus": {"avg_latency_ms": 2500, "avg_cost": 0.05},
            "claude-3-sonnet": {"avg_latency_ms": 2000, "avg_cost": 0.01},
            "claude-3-haiku": {"avg_latency_ms": 1000, "avg_cost": 0.002},
        },
        "cohere": {
            "command": {"avg_latency_ms": 500, "avg_cost": 0.002},
        },
    }

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize routing engine.
        
        Args:
            registry: ProviderRegistry instance with registered providers
        
        Example:
            ```python
            registry = ProviderRegistry.instance()
            router = RoutingEngine(registry)
            ```
        """
        self.registry = registry
        logger.info("Routing engine initialized")

    def select_provider(
        self,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> str:
        """Select best provider for task.
        
        Evaluates all available providers against the routing strategy and
        task metadata, returning the ID of the best provider.
        
        Args:
            metadata: Task execution metadata (complexity, requirements, etc.)
            strategy: Routing strategy (cost, latency, accuracy, balanced)
        
        Returns:
            Provider ID to use for this task
        
        Raises:
            ValueError: If no suitable provider found
        
        Example:
            ```python
            provider_id = router.select_provider(
                metadata=ExecutionMetadata(
                    task_type="summarize",
                    complexity="simple",
                    cost_sensitive=True,
                ),
                strategy=RoutingStrategy(
                    strategy_type="cost",
                    fallback_chain=["gpt-3.5-turbo", "claude-haiku"],
                )
            )
            ```
        """
        # Score all providers in fallback chain
        scores: dict[str, RoutingScore] = {}
        
        for provider_id in strategy.fallback_chain:
            if not self.registry.is_registered(provider_id):
                logger.warning(f"Provider {provider_id} not registered, skipping")
                continue
            
            try:
                provider = self.registry.get_provider(provider_id)
                score = self._score_provider(
                    provider=provider,
                    metadata=metadata,
                    strategy=strategy,
                )
                scores[provider_id] = score
                
                logger.debug(
                    f"Scored {provider_id}: {score.combined_score:.3f} "
                    f"({score.reason})"
                )
            
            except Exception as e:
                logger.warning(f"Failed to score {provider_id}: {e}")
        
        if not scores:
            raise ValueError(
                f"No suitable provider found. "
                f"Attempted: {strategy.fallback_chain}"
            )
        
        # Select provider with highest combined score
        best_provider_id = max(scores, key=lambda pid: scores[pid].combined_score)
        best_score = scores[best_provider_id]
        
        logger.info(
            f"Selected provider: {best_provider_id} "
            f"(score={best_score.combined_score:.3f}, strategy={strategy.strategy_type})"
        )
        
        return best_provider_id

    def _score_provider(
        self,
        provider: Provider,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> RoutingScore:
        """Score a provider for the given task.
        
        Calculates four component scores:
        1. Cost score: Lower cost = higher score
        2. Latency score: Lower latency = higher score
        3. Accuracy score: More capable = higher score
        4. Capability score: Matches task requirements = higher score
        
        Then combines them based on strategy type.
        
        Args:
            provider: Provider to score
            metadata: Task metadata
            strategy: Routing strategy
        
        Returns:
            RoutingScore with component and combined scores
        """
        # Calculate component scores
        cost_score = self._score_cost(provider, metadata, strategy)
        latency_score = self._score_latency(provider, metadata, strategy)
        accuracy_score = self._score_accuracy(provider, metadata, strategy)
        capability_score = self._score_capabilities(provider, metadata, strategy)
        
        # Combine based on strategy
        if strategy.strategy_type == "cost":
            # Heavily weight cost, secondary on capability
            combined = (cost_score * 0.7 + capability_score * 0.3)
            reason = f"cost-optimized: ${self._estimate_provider_cost(provider):.4f}"
        
        elif strategy.strategy_type == "latency":
            # Heavily weight latency, secondary on capability
            combined = (latency_score * 0.7 + capability_score * 0.3)
            reason = f"latency-optimized: {self._estimate_provider_latency(provider)}ms"
        
        elif strategy.strategy_type == "accuracy":
            # Heavily weight accuracy/capability
            combined = (accuracy_score * 0.7 + capability_score * 0.3)
            reason = f"accuracy-optimized: capability={capability_score:.2f}"
        
        else:  # balanced (default)
            # Equal weight to cost, latency, accuracy
            combined = (
                cost_score * 0.3 +
                latency_score * 0.3 +
                accuracy_score * 0.2 +
                capability_score * 0.2
            )
            reason = "balanced: cost/latency/accuracy tradeoff"
        
        return RoutingScore(
            provider_id=provider.provider_id,
            strategy=strategy.strategy_type,
            cost_score=cost_score,
            latency_score=latency_score,
            accuracy_score=accuracy_score,
            capability_score=capability_score,
            combined_score=combined,
            reason=reason,
        )

    def _score_cost(
        self,
        provider: Provider,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> float:
        """Score provider for cost.
        
        Cheaper providers score higher. Providers exceeding cost threshold
        are penalized.
        
        Returns:
            Cost score 0-1 (1.0 = excellent, 0.0 = unacceptable)
        """
        if not metadata.cost_sensitive:
            # If task isn't cost-sensitive, all providers equally good
            return 0.5
        
        avg_cost = self._estimate_provider_cost(provider)
        
        # Penalize if exceeds threshold
        if avg_cost > strategy.cost_threshold:
            penalty = (avg_cost - strategy.cost_threshold) / strategy.cost_threshold
            return max(0.0, 0.5 - penalty)
        
        # Normalize: cheaper providers get higher scores
        # Assume max cost around $0.50 for scoring purposes
        max_cost = strategy.cost_threshold * 2
        score = 1.0 - (avg_cost / max_cost)
        
        return max(0.0, min(1.0, score))

    def _score_latency(
        self,
        provider: Provider,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> float:
        """Score provider for latency.
        
        Faster providers score higher. Providers exceeding latency threshold
        are penalized.
        
        Returns:
            Latency score 0-1 (1.0 = excellent, 0.0 = unacceptable)
        """
        if not metadata.latency_sensitive:
            # If task isn't latency-sensitive, all providers equally good
            return 0.5
        
        avg_latency = self._estimate_provider_latency(provider)
        
        # Penalize if exceeds threshold
        if avg_latency > strategy.latency_threshold_ms:
            penalty = (avg_latency - strategy.latency_threshold_ms) / strategy.latency_threshold_ms
            return max(0.0, 0.5 - penalty)
        
        # Normalize: faster providers get higher scores
        # Assume max latency around 5s for scoring purposes
        max_latency = strategy.latency_threshold_ms * 2
        score = 1.0 - (avg_latency / max_latency)
        
        return max(0.0, min(1.0, score))

    def _score_accuracy(
        self,
        provider: Provider,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> float:
        """Score provider for accuracy/capability.
        
        More capable models score higher based on complexity level.
        
        Returns:
            Accuracy score 0-1 (1.0 = excellent, 0.0 = unacceptable)
        """
        complexity = metadata.complexity or "medium"
        
        # Estimate model capability level
        capability_level = self._estimate_capability_level(provider)
        
        # Match complexity to capability
        if complexity == "simple":
            # Simple tasks work well with any provider
            return min(1.0, capability_level * 0.8 + 0.3)
        
        elif complexity == "medium":
            # Medium tasks need decent providers
            return min(1.0, capability_level * 0.7 + 0.4)
        
        elif complexity == "complex":
            # Complex tasks need high-capability providers
            return min(1.0, capability_level * 0.9 + 0.1)
        
        else:
            return capability_level

    def _score_capabilities(
        self,
        provider: Provider,
        metadata: ExecutionMetadata,
        strategy: RoutingStrategy,
    ) -> float:
        """Score provider based on capability requirements.
        
        Providers with required capabilities (vision, functions) score higher
        if those capabilities are needed.
        
        Returns:
            Capability match score 0-1 (1.0 = perfect match, 0.0 = missing)
        """
        caps = provider.capabilities
        score = 1.0
        
        # Check for required capabilities
        if strategy.prefer_vision and not caps.supports_vision:
            score -= 0.2
        
        if strategy.prefer_functions and not caps.supports_functions:
            score -= 0.2
        
        # Bonus for having more capabilities
        capability_count = sum([
            caps.supports_streaming,
            caps.supports_vision,
            caps.supports_functions,
        ])
        score += capability_count * 0.1
        
        return max(0.0, min(1.0, score))

    def _estimate_provider_cost(self, provider: Provider) -> float:
        """Estimate average cost for a typical execution.
        
        Uses historical profiles or estimates based on model name.
        Typical task: 500 input tokens, 200 output tokens.
        
        Returns:
            Estimated cost in USD
        """
        try:
            # Look up in profiles
            profiles = self.PROVIDER_PROFILES.get(provider.provider_id, {})
            
            # Try to find matching model
            for model_pattern, profile in profiles.items():
                if model_pattern in provider.model:
                    return profile.get("avg_cost", 0.01)
            
            # Fallback: use pricing info
            pricing = provider.pricing_per_1k_tokens
            input_tokens = 500
            output_tokens = 200
            return provider.estimate_cost(input_tokens, output_tokens)
        
        except Exception as e:
            logger.warning(f"Failed to estimate cost for {provider.provider_id}: {e}")
            return 0.01

    def _estimate_provider_latency(self, provider: Provider) -> float:
        """Estimate typical latency for a provider.
        
        Uses historical profiles or conservative estimates.
        
        Returns:
            Estimated latency in milliseconds
        """
        try:
            profiles = self.PROVIDER_PROFILES.get(provider.provider_id, {})
            
            # Try to find matching model
            for model_pattern, profile in profiles.items():
                if model_pattern in provider.model:
                    return profile.get("avg_latency_ms", 2000)
            
            # Fallback: reasonable estimate based on provider type
            if "gpt-3.5" in provider.model:
                return 800
            elif "gpt-4" in provider.model:
                return 2000
            elif "claude" in provider.model:
                if "haiku" in provider.model:
                    return 1000
                elif "opus" in provider.model:
                    return 2500
                else:
                    return 2000
            else:
                return 1500
        
        except Exception as e:
            logger.warning(f"Failed to estimate latency for {provider.provider_id}: {e}")
            return 2000

    def _estimate_capability_level(self, provider: Provider) -> float:
        """Estimate capability level of a provider.
        
        Based on model name and reported capabilities.
        
        Returns:
            Capability score 0-1 (1.0 = most capable)
        """
        provider_id = provider.provider_id
        model = provider.model.lower()
        
        # OpenAI capability hierarchy
        if provider_id == "openai":
            if "gpt-4o" in model:
                return 1.0
            elif "gpt-4" in model:
                if "turbo" in model:
                    return 0.95
                return 0.85
            elif "gpt-3.5" in model:
                return 0.6
        
        # Anthropic capability hierarchy
        elif provider_id == "anthropic":
            if "opus" in model:
                return 0.95
            elif "sonnet" in model:
                return 0.75
            elif "haiku" in model:
                return 0.5
        
        # Default: medium capability
        return 0.7

    def get_fallback_provider(
        self,
        failed_provider: str,
        strategy: RoutingStrategy,
    ) -> str | None:
        """Get next fallback provider after failure.
        
        Args:
            failed_provider: Provider ID that failed
            strategy: Routing strategy with fallback chain
        
        Returns:
            Next provider ID in fallback chain, or None if exhausted
        
        Example:
            ```python
            try:
                response = await provider.execute(prompt)
            except ProviderError as e:
                if e.is_retryable:
                    next_provider_id = router.get_fallback_provider(
                        provider.provider_id,
                        strategy,
                    )
                    if next_provider_id:
                        provider = registry.get_provider(next_provider_id)
                        response = await provider.execute(prompt)
            ```
        """
        try:
            idx = strategy.fallback_chain.index(failed_provider)
            
            # Get next provider in chain
            if idx + 1 < len(strategy.fallback_chain):
                next_id = strategy.fallback_chain[idx + 1]
                
                if self.registry.is_registered(next_id):
                    logger.info(
                        f"Falling back from {failed_provider} to {next_id}"
                    )
                    return next_id
        
        except (ValueError, IndexError):
            pass
        
        logger.warning(
            f"No fallback provider available after {failed_provider}"
        )
        return None

    def get_preferred_provider_for_task(
        self,
        task_type: str,
    ) -> str | None:
        """Get recommended provider for specific task type.
        
        Returns preferred provider based on task type and available providers.
        
        Args:
            task_type: Type of task (summarize, classify, extract, etc.)
        
        Returns:
            Recommended provider ID, or None if no suitable provider
        
        Example:
            ```python
            provider_id = router.get_preferred_provider_for_task("summarize")
            if provider_id:
                provider = registry.get_provider(provider_id)
            ```
        """
        # Task type recommendations
        recommendations = {
            "summarize": {
                "preferred": ["gpt-4o", "claude-3-sonnet"],
                "cost_effective": ["gpt-3.5-turbo", "claude-3-haiku"],
            },
            "classify": {
                "preferred": ["gpt-4", "claude-3-sonnet"],
                "cost_effective": ["gpt-3.5-turbo", "claude-3-haiku"],
            },
            "extract": {
                "preferred": ["gpt-4", "claude-3-sonnet"],
                "cost_effective": ["gpt-3.5-turbo", "claude-3-haiku"],
            },
            "analyze": {
                "preferred": ["gpt-4", "claude-3-opus"],
                "cost_effective": ["gpt-4-turbo", "claude-3-sonnet"],
            },
            "write": {
                "preferred": ["gpt-4", "claude-3-opus"],
                "cost_effective": ["gpt-4-turbo", "claude-3-sonnet"],
            },
        }
        
        # Get recommendations for this task type
        task_recs = recommendations.get(task_type, {})
        preferred_models = task_recs.get("preferred", [])
        
        # Find first available preferred model
        for model_id in preferred_models:
            if self.registry.is_registered(model_id):
                logger.debug(f"Recommending {model_id} for {task_type}")
                return model_id
        
        # Fallback to any registered provider
        providers = self.registry.list_providers()
        if providers:
            logger.debug(
                f"No preferred provider for {task_type}, using {providers[0]}"
            )
            return providers[0]
        
        return None
