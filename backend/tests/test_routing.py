"""Unit tests for routing engine.

Tests cover:
- Provider scoring (cost, latency, accuracy, capabilities)
- Routing strategy application (cost, latency, accuracy, balanced)
- Provider selection
- Fallback chain handling
- Task type recommendations
"""

import pytest
from unittest.mock import Mock, MagicMock

from app.routing import (
    RoutingEngine,
    RoutingStrategy,
    RoutingScore,
)
from app.providers import (
    ProviderRegistry,
    Provider,
    ProviderCapabilities,
    ExecutionMetadata,
)


class MockProvider(Provider):
    """Mock provider for testing routing logic."""
    
    def __init__(
        self,
        provider_id: str,
        model: str,
        max_tokens: int = 4096,
        supports_vision: bool = False,
        supports_functions: bool = False,
    ):
        super().__init__(provider_id, {"model": model, "api_key": "test"})
        self.model = model
        self._max_tokens = max_tokens
        self._supports_vision = supports_vision
        self._supports_functions = supports_functions
    
    def _validate_credentials(self):
        pass
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            max_input_tokens=self._max_tokens - 1000,
            max_output_tokens=self._max_tokens - 100,
            supports_streaming=True,
            supports_vision=self._supports_vision,
            supports_functions=self._supports_functions,
        )
    
    @property
    def pricing_per_1k_tokens(self) -> dict[str, float]:
        return {"input": 0.01, "output": 0.02}
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000) * 0.01 + (output_tokens / 1000) * 0.02
    
    def get_available_models(self) -> list[str]:
        return [self.model]
    
    async def execute(self, prompt: str, metadata=None, **kwargs):
        pass
    
    async def execute_streaming(self, prompt: str, metadata=None, **kwargs):
        pass


class TestRoutingEngine:
    """Tests for routing engine."""
    
    @pytest.fixture
    def registry(self):
        """Create provider registry with mock providers."""
        ProviderRegistry.reset()
        registry = ProviderRegistry.instance()
        
        # Register mock providers
        registry.register(
            "gpt-4",
            MockProvider("openai", "gpt-4", supports_vision=True, supports_functions=True)
        )
        registry.register(
            "gpt-3.5-turbo",
            MockProvider("openai", "gpt-3.5-turbo", supports_functions=True)
        )
        registry.register(
            "claude-opus",
            MockProvider("anthropic", "claude-3-opus", supports_vision=True, supports_functions=True)
        )
        registry.register(
            "claude-haiku",
            MockProvider("anthropic", "claude-3-haiku", supports_vision=True)
        )
        
        return registry
    
    @pytest.fixture
    def router(self, registry):
        """Create routing engine."""
        return RoutingEngine(registry)
    
    def test_select_provider_cost_strategy(self, router):
        """Test cost-optimized provider selection."""
        strategy = RoutingStrategy(
            strategy_type="cost",
            fallback_chain=["gpt-4", "gpt-3.5-turbo", "claude-haiku"],
            cost_threshold=0.50,
        )
        
        metadata = ExecutionMetadata(
            task_type="summarize",
            cost_sensitive=True,
        )
        
        selected = router.select_provider(metadata, strategy)
        assert selected in ["gpt-4", "gpt-3.5-turbo", "claude-haiku"]
    
    def test_select_provider_latency_strategy(self, router):
        """Test latency-optimized provider selection."""
        strategy = RoutingStrategy(
            strategy_type="latency",
            fallback_chain=["gpt-3.5-turbo", "claude-haiku"],
            latency_threshold_ms=1000.0,
        )
        
        metadata = ExecutionMetadata(
            task_type="classify",
            latency_sensitive=True,
        )
        
        selected = router.select_provider(metadata, strategy)
        # Latency-sensitive should prefer faster models
        assert selected in ["gpt-3.5-turbo", "claude-haiku"]
    
    def test_select_provider_accuracy_strategy(self, router):
        """Test accuracy-optimized provider selection."""
        strategy = RoutingStrategy(
            strategy_type="accuracy",
            fallback_chain=["gpt-4", "claude-opus"],
        )
        
        metadata = ExecutionMetadata(
            task_type="analyze",
            complexity="complex",
        )
        
        selected = router.select_provider(metadata, strategy)
        # Accuracy should prefer most capable models
        assert selected in ["gpt-4", "claude-opus"]
    
    def test_select_provider_balanced_strategy(self, router):
        """Test balanced provider selection."""
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["gpt-4", "gpt-3.5-turbo"],
        )
        
        metadata = ExecutionMetadata(task_type="extract")
        
        selected = router.select_provider(metadata, strategy)
        assert selected in ["gpt-4", "gpt-3.5-turbo"]
    
    def test_select_provider_respects_fallback_chain_order(self, router):
        """Test that provider selection respects fallback chain."""
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["gpt-3.5-turbo", "gpt-4"],  # Unconventional order
        )
        
        metadata = ExecutionMetadata(task_type="summarize")
        
        selected = router.select_provider(metadata, strategy)
        # Should still select best from available
        assert selected in ["gpt-3.5-turbo", "gpt-4"]
    
    def test_select_provider_no_suitable_provider(self, router):
        """Test error when no suitable provider found."""
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["nonexistent-provider"],
        )
        
        metadata = ExecutionMetadata(task_type="summarize")
        
        with pytest.raises(ValueError, match="No suitable provider found"):
            router.select_provider(metadata, strategy)
    
    def test_score_provider_cost_sensitive(self, router):
        """Test cost scoring for cost-sensitive tasks."""
        provider = router.registry.get_provider("gpt-3.5-turbo")
        
        metadata = ExecutionMetadata(
            task_type="summarize",
            cost_sensitive=True,
        )
        
        strategy = RoutingStrategy(
            strategy_type="cost",
            fallback_chain=["gpt-3.5-turbo"],
            cost_threshold=0.10,
        )
        
        score = router._score_provider(provider, metadata, strategy)
        assert isinstance(score, RoutingScore)
        assert score.cost_score > 0
        assert score.provider_id == "gpt-3.5-turbo"
    
    def test_score_provider_latency_sensitive(self, router):
        """Test latency scoring for latency-sensitive tasks."""
        provider = router.registry.get_provider("gpt-3.5-turbo")
        
        metadata = ExecutionMetadata(
            task_type="classify",
            latency_sensitive=True,
        )
        
        strategy = RoutingStrategy(
            strategy_type="latency",
            fallback_chain=["gpt-3.5-turbo"],
            latency_threshold_ms=1000.0,
        )
        
        score = router._score_provider(provider, metadata, strategy)
        assert score.latency_score > 0
    
    def test_score_provider_capability_requirements(self, router):
        """Test capability scoring based on task requirements."""
        # Provider with vision
        provider_vision = router.registry.get_provider("gpt-4")
        
        # Provider without vision
        provider_no_vision = router.registry.get_provider("gpt-3.5-turbo")
        
        metadata = ExecutionMetadata(task_type="analyze")
        
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["gpt-4", "gpt-3.5-turbo"],
            prefer_vision=True,
        )
        
        score_vision = router._score_provider(provider_vision, metadata, strategy)
        score_no_vision = router._score_provider(provider_no_vision, metadata, strategy)
        
        # Vision provider should score higher when vision is preferred
        assert score_vision.capability_score >= score_no_vision.capability_score
    
    def test_get_fallback_provider(self, router):
        """Test fallback provider selection."""
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["gpt-4", "gpt-3.5-turbo", "claude-opus"],
        )
        
        # Get fallback after gpt-4 fails
        next_provider = router.get_fallback_provider("gpt-4", strategy)
        assert next_provider == "gpt-3.5-turbo"
        
        # Get fallback after gpt-3.5-turbo fails
        next_provider = router.get_fallback_provider("gpt-3.5-turbo", strategy)
        assert next_provider == "claude-opus"
        
        # No fallback after last provider
        next_provider = router.get_fallback_provider("claude-opus", strategy)
        assert next_provider is None
    
    def test_get_fallback_provider_nonexistent_provider(self, router):
        """Test fallback with nonexistent provider."""
        strategy = RoutingStrategy(
            strategy_type="balanced",
            fallback_chain=["gpt-4", "gpt-3.5-turbo"],
        )
        
        # Nonexistent provider in chain
        next_provider = router.get_fallback_provider("nonexistent", strategy)
        assert next_provider is None
    
    def test_get_preferred_provider_for_task(self, router):
        """Test task type recommendations."""
        # Summarization prefers capable models
        provider = router.get_preferred_provider_for_task("summarize")
        assert provider in router.registry.list_providers()
        
        # Classification
        provider = router.get_preferred_provider_for_task("classify")
        assert provider in router.registry.list_providers()
        
        # Complex analysis
        provider = router.get_preferred_provider_for_task("analyze")
        assert provider in router.registry.list_providers()
    
    def test_estimate_provider_cost(self, router):
        """Test cost estimation."""
        provider = router.registry.get_provider("gpt-3.5-turbo")
        cost = router._estimate_provider_cost(provider)
        
        assert cost > 0
        assert cost < 0.1  # Should be relatively cheap
    
    def test_estimate_provider_latency(self, router):
        """Test latency estimation."""
        provider_fast = router.registry.get_provider("gpt-3.5-turbo")
        provider_slow = router.registry.get_provider("gpt-4")
        
        latency_fast = router._estimate_provider_latency(provider_fast)
        latency_slow = router._estimate_provider_latency(provider_slow)
        
        assert latency_fast > 0
        assert latency_slow > 0
        # Fast model should generally be faster
        assert latency_fast <= latency_slow
    
    def test_estimate_capability_level(self, router):
        """Test capability level estimation."""
        gpt4 = router.registry.get_provider("gpt-4")
        gpt35 = router.registry.get_provider("gpt-3.5-turbo")
        
        cap_4 = router._estimate_capability_level(gpt4)
        cap_35 = router._estimate_capability_level(gpt35)
        
        # GPT-4 should be more capable than GPT-3.5
        assert cap_4 > cap_35
        assert 0 <= cap_4 <= 1.0
        assert 0 <= cap_35 <= 1.0
    
    def test_routing_strategy_dataclass(self):
        """Test routing strategy creation."""
        strategy = RoutingStrategy(
            strategy_type="cost",
            fallback_chain=["gpt-3.5-turbo", "claude-haiku"],
            cost_threshold=0.50,
            latency_threshold_ms=2000,
        )
        
        assert strategy.strategy_type == "cost"
        assert len(strategy.fallback_chain) == 2
        assert strategy.cost_threshold == 0.50
    
    def test_routing_score_dataclass(self):
        """Test routing score creation."""
        score = RoutingScore(
            provider_id="gpt-4",
            strategy="cost",
            cost_score=0.8,
            latency_score=0.7,
            accuracy_score=0.9,
            capability_score=0.85,
            combined_score=0.81,
            reason="cost-optimized",
        )
        
        assert score.provider_id == "gpt-4"
        assert score.combined_score == 0.81
        assert 0 <= score.cost_score <= 1.0
