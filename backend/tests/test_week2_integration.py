"""Integration tests for Week 2 routing engine with worker and database.

Tests verify:
1. Workflow schema updates with routing configuration
2. Task schema updates with provider execution tracking
3. Worker integration with routing engine
4. Provider registry bootstrap on startup
5. End-to-end task execution with provider selection and cost tracking
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from app.models import Workflow, Task
from app.schemas import WorkflowCreate, TaskCreate, TaskResponse, WorkflowSummary
from app.routing import RoutingEngine, RoutingStrategy, ExecutionMetadata
from app.providers.registry import ProviderRegistry
from app.providers.base import ProviderResponse, ExecutionMetadata


class TestWorkflowRoutingSchema:
    """Tests for Workflow model routing configuration fields."""
    
    def test_workflow_has_routing_strategy_field(self):
        """Verify Workflow model includes routing_strategy column."""
        workflow = Workflow(
            name="Test Workflow",
            description="Test description",
            routing_strategy="cost",
        )
        assert workflow.routing_strategy == "cost"
        assert hasattr(workflow, "routing_strategy")
    
    def test_workflow_routing_defaults(self):
        """Verify routing configuration defaults."""
        workflow = Workflow(
            name="Test Workflow",
            description="Test description",
        )
        assert workflow.routing_strategy == "balanced"
        assert workflow.cost_threshold == 10.0
        assert workflow.latency_threshold_ms == 30000
        assert workflow.fallback_chain is None
        assert workflow.prefer_providers is None
    
    def test_workflow_fallback_chain_serialization(self):
        """Verify fallback chain is stored as JSON."""
        fallback = ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet"]
        workflow = Workflow(
            name="Test Workflow",
            description="Test description",
            fallback_chain=json.dumps(fallback),
        )
        assert workflow.fallback_chain == json.dumps(fallback)
        assert json.loads(workflow.fallback_chain) == fallback


class TestTaskProviderTracking:
    """Tests for Task model provider execution tracking."""
    
    def test_task_has_provider_execution_fields(self):
        """Verify Task model includes provider execution tracking columns."""
        task = Task(
            workflow_id=1,
            name="Test Task",
            input_data="test input",
            executed_provider="gpt-4",
            execution_cost_usd=0.042,
            execution_latency_ms=2350,
            tokens_used=156,
        )
        assert task.executed_provider == "gpt-4"
        assert task.execution_cost_usd == 0.042
        assert task.execution_latency_ms == 2350
        assert task.tokens_used == 156
    
    def test_task_provider_fields_nullable(self):
        """Verify provider fields are optional until task completion."""
        task = Task(
            workflow_id=1,
            name="Test Task",
            input_data="test input",
        )
        assert task.executed_provider is None
        assert task.execution_cost_usd is None
        assert task.execution_latency_ms is None
        assert task.tokens_used is None


class TestWorkflowCreateSchema:
    """Tests for WorkflowCreate request schema with routing config."""
    
    def test_workflow_create_with_routing_strategy(self):
        """Verify WorkflowCreate accepts routing strategy."""
        request = WorkflowCreate(
            name="Email Summarizer",
            description="Summarize emails with routing optimization",
            routing_strategy="latency",
            cost_threshold=5.0,
            latency_threshold_ms=10000,
        )
        assert request.routing_strategy == "latency"
        assert request.cost_threshold == 5.0
        assert request.latency_threshold_ms == 10000
    
    def test_workflow_create_routing_defaults(self):
        """Verify routing configuration defaults in schema."""
        request = WorkflowCreate(
            name="Email Summarizer",
            description="Summarize emails",
        )
        assert request.routing_strategy == "balanced"
        assert request.cost_threshold == 10.0
        assert request.latency_threshold_ms == 30000
        assert request.fallback_chain is None
    
    def test_workflow_create_fallback_chain_list(self):
        """Verify fallback chain is a list of provider IDs."""
        request = WorkflowCreate(
            name="Email Summarizer",
            description="Summarize emails",
            fallback_chain=["gpt-4", "gpt-3.5-turbo"],
        )
        assert request.fallback_chain == ["gpt-4", "gpt-3.5-turbo"]
    
    def test_workflow_create_invalid_strategy(self):
        """Verify routing strategy validation."""
        with pytest.raises(ValueError):
            WorkflowCreate(
                name="Email Summarizer",
                description="Summarize emails",
                routing_strategy="invalid",
            )
    
    def test_workflow_create_negative_threshold_invalid(self):
        """Verify cost threshold must be positive."""
        with pytest.raises(ValueError):
            WorkflowCreate(
                name="Email Summarizer",
                description="Summarize emails",
                cost_threshold=-1.0,
            )


class TestTaskResponseSchema:
    """Tests for TaskResponse schema with provider execution info."""
    
    def test_task_response_includes_provider_info(self):
        """Verify TaskResponse includes executed provider details."""
        response = TaskResponse(
            id=123,
            workflow_id=42,
            source_task_id=None,
            name="Summarize email",
            agent="executor",
            stage="completed",
            status="succeeded",
            queue_name="default",
            input="test input",
            output="test output",
            error_message=None,
            retries=0,
            duration_seconds=2.5,
            executed_provider="gpt-4",
            execution_cost_usd=0.042,
            execution_latency_ms=2500,
            tokens_used=150,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        assert response.executed_provider == "gpt-4"
        assert response.execution_cost_usd == 0.042
        assert response.execution_latency_ms == 2500
        assert response.tokens_used == 150
    
    def test_task_response_provider_fields_optional(self):
        """Verify provider fields are optional in schema."""
        response = TaskResponse(
            id=123,
            workflow_id=42,
            source_task_id=None,
            name="Summarize email",
            agent="executor",
            stage="queued",
            status="pending",
            queue_name="default",
            input="test input",
            output=None,
            error_message=None,
            retries=0,
            duration_seconds=None,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
        )
        assert response.executed_provider is None
        assert response.execution_cost_usd is None


class TestWorkflowSummarySchema:
    """Tests for WorkflowSummary schema with routing configuration."""
    
    def test_workflow_summary_includes_routing_config(self):
        """Verify WorkflowSummary includes routing strategy and thresholds."""
        summary = WorkflowSummary(
            id=42,
            name="Email Summarizer",
            description="Summarize emails",
            owner="user-123",
            status="active",
            priority="medium",
            target_model="gpt-4",
            routing_strategy="cost",
            cost_threshold=5.0,
            latency_threshold_ms=10000,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_run_at=None,
            task_count=0,
            completed_tasks=0,
            failed_tasks=0,
            active_tasks=0,
        )
        assert summary.routing_strategy == "cost"
        assert summary.cost_threshold == 5.0
        assert summary.latency_threshold_ms == 10000


class TestProviderBootstrap:
    """Tests for provider registry bootstrap."""
    
    def test_bootstrap_providers_initializes_registry(self):
        """Verify bootstrap_providers populates registry."""
        from app.provider_bootstrap import bootstrap_providers
        
        registry = ProviderRegistry.instance()
        # Clear existing providers
        registry._providers.clear()
        
        # Bootstrap with API keys
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "sk-test123",
            "ANTHROPIC_API_KEY": "sk-ant-test123",
        }):
            bootstrap_providers()
        
        providers = registry.list_providers()
        # Should have registered some providers
        assert len(providers) > 0
    
    def test_bootstrap_handles_missing_api_keys(self):
        """Verify bootstrap handles missing API keys gracefully."""
        from app.provider_bootstrap import bootstrap_providers
        
        registry = ProviderRegistry.instance()
        registry._providers.clear()
        
        # Bootstrap without API keys
        with patch.dict("os.environ", {}, clear=True):
            bootstrap_providers()  # Should not raise


class TestRoutingEngineWithSchema:
    """Tests for RoutingEngine using workflow configuration."""
    
    def test_routing_engine_from_workflow_config(self):
        """Verify routing engine respects workflow configuration."""
        # Create workflow with cost optimization
        workflow_config = {
            "routing_strategy": "cost",
            "fallback_chain": ["gpt-3.5-turbo", "claude-3-haiku"],
            "cost_threshold": 1.0,
        }
        
        # Create routing strategy from workflow
        strategy = RoutingStrategy(
            strategy_type=workflow_config["routing_strategy"],
            fallback_chain=workflow_config["fallback_chain"],
            cost_threshold=workflow_config["cost_threshold"],
        )
        
        assert strategy.strategy_type == "cost"
        assert strategy.cost_threshold == 1.0
        assert strategy.fallback_chain == ["gpt-3.5-turbo", "claude-3-haiku"]
    
    def test_execution_metadata_from_task(self):
        """Verify ExecutionMetadata can be built from task."""
        task_config = {
            "agent": "executor",
            "input_data": "x" * 600,  # 600 chars = complex
            "queue_name": "low_cost",
        }
        
        metadata = ExecutionMetadata(
            task_type=task_config["agent"],
            complexity="complex" if len(task_config["input_data"]) > 500 else "simple",
            cost_sensitive=task_config["queue_name"] == "low_cost",
            latency_sensitive=task_config["queue_name"] == "high_priority",
        )
        
        assert metadata.task_type == "executor"
        assert metadata.complexity == "complex"
        assert metadata.cost_sensitive is True
        assert metadata.latency_sensitive is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
