# Testing & Quality Assurance Guide

Complete testing strategy for AI Orchestration Platform including unit, integration, E2E, and performance tests.

## Test Structure

```
backend/
  tests/
    conftest.py             # Shared fixtures
    test_agents.py
    test_providers.py
    test_billing.py
    test_auth.py
    test_audit.py
    test_workers.py
    integration/
      test_end_to_end.py
      test_oauth_flows.py
    performance/
      test_load.py
      test_provider_latency.py

frontend/
  __tests__/
    components/
    pages/
    hooks/
```

## Backend Testing

### Setup

Install test dependencies:

```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock faker responses
```

Create `backend/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Organization, User, UserRole

@pytest.fixture
def test_db():
    """In-memory SQLite database for tests"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def test_org(test_db):
    """Test organization"""
    org = Organization(
        id="org-test",
        name="Test Org",
        subscription_status="active"
    )
    test_db.add(org)
    test_db.commit()
    return org

@pytest.fixture
def test_user(test_db, test_org):
    """Test user (Owner role)"""
    user = User(
        id="user-test",
        email="test@example.com",
        org_id=test_org.id,
        role=UserRole.OWNER,
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture
def test_token(test_user):
    """JWT token for test user"""
    from app.auth.tokens import create_access_token
    return create_access_token(test_user.id)

@pytest.fixture
def async_client():
    """FastAPI test client with async support"""
    from httpx import AsyncClient
    from app.main import app
    
    async def _client():
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    return _client
```

### 1. Unit Tests: Agent Routing

Create `backend/tests/test_agents.py`:

```python
import pytest
from app.agents.registry import PROVIDER_REGISTRY, AgentProvider
from app.agents.scorer import score_provider, rank_providers
from app.agents.router import select_agent
from app.models import AgentStats, Task
from datetime import datetime, timedelta

class TestProviderRegistry:
    def test_registry_has_required_providers(self):
        """Verify all required providers are registered"""
        required = {"openai-gpt4o", "anthropic-sonnet", "mistral-small"}
        registered = {p.id for p in PROVIDER_REGISTRY.values()}
        
        assert required.issubset(registered)
    
    def test_provider_metadata(self):
        """Verify provider has all required metadata"""
        for provider in PROVIDER_REGISTRY.values():
            assert provider.id
            assert provider.name
            assert provider.cost_per_1k_tokens > 0
            assert provider.avg_latency_ms > 0
            assert provider.supports_types

class TestProviderScoring:
    def test_score_calculation(self):
        """Test scoring formula: 50% success + 30% speed + 20% cost"""
        stats = {
            "success_rate": 1.0,      # Perfect
            "normalized_speed": 1.0,  # Fastest
            "normalized_cost": 1.0    # Cheapest
        }
        score = score_provider(stats)
        
        # Expected: 1.0 * 0.5 + 1.0 * 0.3 + 1.0 * 0.2 = 1.0
        assert score == 1.0
    
    def test_score_weighted_toward_reliability(self):
        """Verify success rate (50%) is heaviest weight"""
        # High success, low speed/cost
        stats_reliable = {
            "success_rate": 1.0,
            "normalized_speed": 0.1,
            "normalized_cost": 0.1
        }
        # Low success, high speed/cost
        stats_fast = {
            "success_rate": 0.1,
            "normalized_speed": 1.0,
            "normalized_cost": 1.0
        }
        
        score_reliable = score_provider(stats_reliable)
        score_fast = score_provider(stats_fast)
        
        assert score_reliable > score_fast
    
    def test_rank_providers_by_score(self, test_db):
        """Test ranking returns providers in descending score order"""
        providers = [
            AgentProvider(id="p1", name="High", cost=0.001, latency=50, types=["summarize"]),
            AgentProvider(id="p2", name="Low", cost=0.01, latency=500, types=["summarize"]),
            AgentProvider(id="p3", name="Mid", cost=0.005, latency=250, types=["summarize"]),
        ]
        
        # Create stats: p1 best, p3 mid, p2 worst
        for provider in providers:
            test_db.add(AgentStats(
                id=f"stat-{provider.id}",
                provider_id=provider.id,
                success_count=100 if provider.id == "p1" else 50,
                failure_count=0,
                total_latency_ms=provider.latency,
                total_tasks=100
            ))
        test_db.commit()
        
        ranked = rank_providers(test_db, providers, "summarize")
        
        assert ranked[0].id == "p1"
        assert ranked[-1].id == "p2"

class TestAgentSelection:
    def test_select_agent_returns_best_provider(self, test_db, test_org, test_user):
        """Verify selection logic picks highest-scored provider"""
        # Mock provider scores
        selected, alternatives = select_agent(
            test_db,
            org_id=test_org.id,
            task_type="summarize"
        )
        
        assert selected is not None
        assert selected.id in [p.id for p in PROVIDER_REGISTRY.values()]
    
    def test_select_agent_excludes_failed_providers(self, test_db):
        """Ensure failed providers are not selected in fallback chain"""
        failed = ["openai-gpt4o", "anthropic-sonnet"]
        
        selected, alternatives = select_agent(
            test_db,
            task_type="summarize",
            exclude_providers=failed
        )
        
        assert selected.id not in failed
        for alt in alternatives:
            assert alt.id not in failed
    
    def test_fallback_chain_has_alternatives(self, test_db):
        """Verify fallback chain provides alternatives"""
        selected, alternatives = select_agent(test_db, "summarize")
        
        assert len(alternatives) >= 2
        assert selected.id != alternatives[0].id
```

### 2. Unit Tests: Providers

Create `backend/tests/test_providers.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.providers.executor import execute_task
from app.providers.openai_provider import OpenAIProvider
from app.providers.scraper_provider import ScraperProvider

class TestOpenAIProvider:
    @pytest.mark.asyncio
    async def test_execute_with_gpt4o(self):
        """Test OpenAI execution with GPT-4o"""
        provider = OpenAIProvider("gpt-4o", api_key="sk-test")
        
        with patch("app.providers.openai_provider.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Summary text"}}],
                "usage": {"completion_tokens": 50, "prompt_tokens": 100}
            }
            mock_client.post.return_value = mock_response
            
            result = await provider.execute(
                task_type="summarize",
                input_data={"text": "Long document..."}
            )
            
            assert "output" in result
            assert result["tokens_used"] == 50
    
    @pytest.mark.asyncio
    async def test_cost_calculation(self):
        """Verify cost is correctly calculated"""
        provider = OpenAIProvider("gpt-4o", api_key="sk-test")
        
        # GPT-4o: $15/1M input, $30/1M output
        # 100 input tokens, 50 output tokens
        cost = provider._calculate_cost(input_tokens=100, output_tokens=50)
        
        expected = (100 * 15 / 1_000_000) + (50 * 30 / 1_000_000)
        assert abs(cost - expected) < 0.00001

class TestScraperProvider:
    @pytest.mark.asyncio
    async def test_scrape_webpage(self):
        """Test web scraping functionality"""
        provider = ScraperProvider()
        
        with patch("app.providers.scraper_provider.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.text = "<html><div class='content'>Test</div></html>"
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            
            result = await provider.execute(
                task_type="web_scrape",
                input_data={"url": "http://example.com", "selector": ".content"}
            )
            
            assert result["output"] == "Test"
            assert result["cost_usd"] == 0  # No API cost

class TestTaskExecutor:
    @pytest.mark.asyncio
    async def test_execute_task_dispatcher(self):
        """Test task execution routing"""
        provider = AgentProvider(
            id="openai-gpt4o",
            name="GPT-4o",
            cost_per_1k_tokens=0.015,
            avg_latency_ms=500,
            supports_types=["summarize"]
        )
        
        with patch("app.providers.openai_provider.OpenAIProvider.execute") as mock:
            mock.return_value = {
                "output": "Summary",
                "tokens_used": 50,
                "cost_usd": 0.001,
                "latency_ms": 523
            }
            
            result = await execute_task(
                provider=provider,
                task_type="summarize",
                input_json={"text": "..."}
            )
            
            assert result["output"] == "Summary"
            assert "tokens_used" in result
```

### 3. Unit Tests: Billing

Create `backend/tests/test_billing.py`:

```python
import pytest
from datetime import datetime, timedelta
from app.billing.models import SubscriptionPlan, PLAN_CONFIGS
from app.billing.service import (
    get_usage_for_period,
    check_subscription_active,
    enforce_rate_limit,
    BillingError
)
from app.models import Organization, UsageRecord

class TestSubscriptionPlans:
    def test_plan_configs_exist(self):
        """Verify all plans are configured"""
        for plan in SubscriptionPlan:
            assert plan.value in PLAN_CONFIGS
            config = PLAN_CONFIGS[plan.value]
            assert config.price_monthly > 0
            assert config.task_limit_monthly > 0
    
    def test_starter_plan_limits(self):
        """Starter plan: $29/month, 1k tasks"""
        config = PLAN_CONFIGS["STARTER"]
        
        assert config.price_monthly == 29
        assert config.task_limit_monthly == 1000

class TestBillingService:
    def test_get_usage_for_period(self, test_db, test_org):
        """Test usage calculation for billing period"""
        # Create usage records
        for i in range(5):
            test_db.add(UsageRecord(
                id=f"usage-{i}",
                org_id=test_org.id,
                task_id=f"task-{i}",
                tokens_used=100,
                cost_usd=0.001
            ))
        test_db.commit()
        
        usage = get_usage_for_period(test_db, test_org.id)
        
        assert usage == 5  # 5 tasks
    
    def test_check_subscription_status(self, test_db):
        """Verify subscription status check"""
        org = Organization(
            id="org-active",
            subscription_status="active"
        )
        test_db.add(org)
        test_db.commit()
        
        is_active = check_subscription_active(test_db, org.id)
        
        assert is_active is True
    
    def test_enforce_rate_limit_raises_on_exceeded(self, test_db, test_org):
        """Rate limit enforcement should raise when quota exceeded"""
        # Simulate 1500 tasks (over 1000 limit for Starter)
        for i in range(1500):
            test_db.add(UsageRecord(
                id=f"usage-{i}",
                org_id=test_org.id,
                task_id=f"task-{i}",
                tokens_used=1,
                cost_usd=0.0001
            ))
        test_db.commit()
        
        test_org.subscription_plan = "STARTER"
        test_db.commit()
        
        with pytest.raises(BillingError):
            enforce_rate_limit(test_db, test_org.id)
```

### 4. Integration Tests: OAuth

Create `backend/tests/integration/test_oauth_flows.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
from app.auth.oauth import google_callback, github_callback
from app.models import User, Organization

@pytest.mark.asyncio
class TestGoogleOAuth:
    async def test_google_callback_creates_user(self, test_db):
        """Google OAuth callback should create new user and org"""
        with patch("app.auth.oauth.GoogleOAuth.exchange_code") as mock_exchange:
            mock_exchange.return_value = {
                "id": "google-123",
                "email": "user@gmail.com",
                "name": "Test User"
            }
            
            user, is_new = await google_callback(
                test_db,
                code="auth-code-123"
            )
            
            assert user.email == "user@gmail.com"
            assert is_new is True
            
            # Verify org created
            org = test_db.query(Organization).filter_by(
                id=user.org_id
            ).first()
            assert org is not None
            assert org.subscription_status == "trialing"
    
    async def test_google_callback_logs_in_existing_user(self, test_db, test_user):
        """OAuth callback logs in existing user without creating new org"""
        with patch("app.auth.oauth.GoogleOAuth.exchange_code") as mock_exchange:
            mock_exchange.return_value = {
                "id": "google-456",
                "email": test_user.email,
                "name": test_user.email
            }
            
            user, is_new = await google_callback(test_db, code="new-code")
            
            assert user.email == test_user.email
            assert is_new is False

@pytest.mark.asyncio
class TestGithubOAuth:
    async def test_github_callback_creates_user(self, test_db):
        """GitHub OAuth callback should create new user"""
        with patch("app.auth.oauth.GitHubOAuth.exchange_code") as mock_exchange:
            mock_exchange.return_value = {
                "id": "github-789",
                "login": "testuser",
                "email": "test@github.com"
            }
            
            user, is_new = await github_callback(test_db, code="gh-code")
            
            assert user.email == "test@github.com"
            assert is_new is True
```

### 5. Integration Tests: End-to-End Task Execution

Create `backend/tests/integration/test_end_to_end.py`:

```python
import pytest
from unittest.mock import patch
from app.agents.router import select_agent, record_provider_usage
from app.models import Task, AgentStats
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

@pytest.mark.asyncio
class TestTaskExecution:
    async def test_full_task_lifecycle(self, test_db, test_org, test_user):
        """Test complete task from creation through completion"""
        # 1. Create task
        task = Task(
            id="task-e2e-1",
            org_id=test_org.id,
            task_type="summarize",
            input_data={"text": "Long document..."},
            status=TaskStatus.PENDING
        )
        test_db.add(task)
        test_db.commit()
        
        assert task.status == TaskStatus.PENDING
        
        # 2. Select provider
        provider, alternatives = select_agent(test_db, test_org.id, "summarize")
        assert provider is not None
        
        # 3. Mock execution
        with patch("app.providers.executor.execute_task") as mock_exec:
            mock_exec.return_value = {
                "output": "Summary of document",
                "tokens_used": 150,
                "cost_usd": 0.005,
                "latency_ms": 1200
            }
            
            result = await mock_exec(provider, "summarize", task.input_data)
            
            # 4. Record usage
            record_provider_usage(
                test_db,
                provider_id=provider.id,
                success=True,
                latency_ms=result["latency_ms"]
            )
            
            # 5. Mark complete
            task.status = TaskStatus.COMPLETED
            task.output_data = result["output"]
            test_db.commit()
        
        # Verify final state
        final_task = test_db.query(Task).filter_by(id=task.id).first()
        assert final_task.status == TaskStatus.COMPLETED
        assert final_task.output_data is not None
```

### 6. Run Tests

```bash
cd backend

# All tests
pytest

# With coverage
pytest --cov=app

# Specific file
pytest tests/test_agents.py -v

# Specific test
pytest tests/test_agents.py::TestProviderScoring::test_score_calculation -v

# Failed tests only
pytest --lf

# Parallel execution (faster)
pip install pytest-xdist
pytest -n auto
```

---

## Frontend Testing

### Setup

```bash
cd frontend

npm install --save-dev \
  @testing-library/react \
  @testing-library/jest-dom \
  jest \
  @types/jest \
  jest-environment-jsdom
```

Create `frontend/jest.config.js`:

```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testPathIgnorePatterns: ['<rootDir>/.next/'],
};
```

### Component Tests

Create `frontend/__tests__/components/LoginButton.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import LoginButton from '@/components/LoginButton';

describe('LoginButton', () => {
  it('renders login button', () => {
    render(<LoginButton />);
    const button = screen.getByRole('button', { name: /login/i });
    expect(button).toBeInTheDocument();
  });

  it('redirects to Google OAuth on click', () => {
    const mockRedirect = jest.fn();
    window.location.href = mockRedirect;
    
    render(<LoginButton />);
    const button = screen.getByRole('button', { name: /google/i });
    fireEvent.click(button);
    
    expect(mockRedirect).toHaveBeenCalledWith(
      expect.stringContaining('/auth/google')
    );
  });
});
```

### Hook Tests

Create `frontend/__tests__/hooks/useAuth.test.ts`:

```typescript
import { renderHook, act } from '@testing-library/react';
import useAuth from '@/hooks/useAuth';

describe('useAuth', () => {
  it('returns null when no token in storage', () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.user).toBeNull();
  });

  it('parses JWT and returns user', () => {
    const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJyb2xlIjoiT3duZXIifQ.sig';
    
    localStorage.setItem('access_token', token);
    
    const { result } = renderHook(() => useAuth());
    
    expect(result.current.user).toEqual({
      id: 'user-1',
      email: 'test@example.com',
      role: 'Owner'
    });
  });

  it('logout clears token', () => {
    const { result } = renderHook(() => useAuth());
    
    act(() => {
      result.current.logout();
    });
    
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(result.current.user).toBeNull();
  });
});
```

### Page Tests

Create `frontend/__tests__/pages/tasks.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import TasksPage from '@/pages/tasks';

describe('Tasks Page', () => {
  it('fetches and displays tasks', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve({
        tasks: [
          { id: '1', title: 'Task 1', status: 'completed' }
        ]
      })
    });
    global.fetch = mockFetch;

    render(<TasksPage />);

    await waitFor(() => {
      expect(screen.getByText('Task 1')).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/tasks'),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': expect.stringContaining('Bearer')
        })
      })
    );
  });
});
```

### Run Tests

```bash
cd frontend

# Run all tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm test -- --coverage

# Specific test file
npm test -- components/LoginButton
```

---

## Performance Testing

### Load Testing with Locust

Create `backend/tests/performance/locustfile.py`:

```python
from locust import HttpUser, task, between
import random

class ApiUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        # Login
        self.token = "test-jwt-token"
    
    @task(3)
    def create_task(self):
        self.client.post(
            "/api/tasks",
            json={
                "task_type": "summarize",
                "input": "Test input text"
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(1)
    def get_tasks(self):
        self.client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

Run:

```bash
pip install locust

locust -f tests/performance/locustfile.py -H http://localhost:8000 --users 50 --spawn-rate 5 --run-time 10m
```

Access UI at http://localhost:8089

### Provider Latency Benchmarking

Create `backend/tests/performance/test_provider_latency.py`:

```python
import pytest
import time
from unittest.mock import patch

class TestProviderLatency:
    @pytest.mark.asyncio
    async def test_openai_p95_latency(self):
        """OpenAI should complete 95% of requests in < 2 seconds"""
        latencies = []
        
        for _ in range(100):
            start = time.time()
            
            with patch("app.providers.openai_provider.httpx.AsyncClient.post"):
                # Simulated API call
                await openai_provider.execute(...)
            
            latencies.append((time.time() - start) * 1000)
        
        latencies.sort()
        p95 = latencies[int(0.95 * len(latencies))]
        
        assert p95 < 2000  # 2 seconds
```

Run:

```bash
pytest tests/performance/test_provider_latency.py -v --benchmark
```

---

## Continuous Integration (GitHub Actions)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379
        run: |
          cd backend
          pytest --cov=app

  frontend:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Run tests
        run: |
          cd frontend
          npm test -- --coverage
      
      - name: Type check
        run: |
          cd frontend
          npm run type-check
      
      - name: Lint
        run: |
          cd frontend
          npm run lint
```

---

## Test Metrics & Goals

### Target Coverage

| Component | Target |
|-----------|--------|
| Agents (routing, scoring) | 90%+ |
| Providers (executors) | 85%+ |
| Billing (service logic) | 90%+ |
| Auth (OAuth, RBAC, tokens) | 90%+ |
| Audit (logging, verification) | 95%+ |
| Frontend Components | 80%+ |
| Overall Backend | 85%+ |

### Report Coverage

```bash
cd backend

# Generate HTML report
pytest --cov=app --cov-report=html

# Open in browser
open htmlcov/index.html
```

### Test Execution Time Goals

| Category | Target |
|----------|--------|
| Unit tests | < 5 seconds |
| Integration tests | < 30 seconds |
| Full suite | < 2 minutes |

---

## Troubleshooting Tests

### Test Database Isolation

Each test should use `test_db` fixture to get clean database:

```python
def test_something(test_db):
    # test_db is in-memory SQLite
    # No pollution between tests
```

### Async Test Execution

Always use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_func()
    assert result is not None
```

### Mocking External APIs

Always mock external calls (OpenAI, Stripe, OAuth):

```python
with patch("app.providers.openai_provider.httpx.AsyncClient.post") as mock:
    mock.return_value = AsyncMock(json=lambda: {...})
    # Test logic
```

Never make real API calls in tests.

### Import Errors in Tests

Ensure PYTHONPATH includes backend:

```bash
cd backend
PYTHONPATH=. pytest
```

## Next Steps

- [ ] Achieve 85%+ overall coverage
- [ ] Add load testing targets to CI/CD
- [ ] Set up coverage badges in README
- [ ] Create test data fixtures for common scenarios
- [ ] Add visual regression testing for frontend
