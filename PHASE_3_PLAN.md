# 🎯 Phase 3: Enterprise Auth & Multi-Tenancy Implementation Plan

**Status**: Ready to Start  
**Target Duration**: 2-3 weeks  
**Todos**: 13 items pending  
**Quality Score Goal**: 9.5/10 (up from 9.2/10)

---

## 📋 Executive Summary

Phase 3 extends the current auth system (OAuth2, JWT, RBAC) into a complete enterprise multi-tenant platform. This includes:

- ✅ User & Workspace models with multi-tenancy
- ✅ Enhanced JWT with workspace context
- ✅ RBAC enforcement on all endpoints
- ✅ Workspace isolation & safety
- ✅ API key management for automation
- ✅ Team invite & management flows
- ✅ Enhanced audit logging
- ✅ SSO scaffolding for Okta/Auth0
- ✅ Billing compliance & usage tracking

---

## 🏗️ Current State Analysis

### ✅ Already Implemented (Foundation in Place)

**Authentication**
- ✅ OAuth2 (Google, GitHub) - `backend/app/auth/oauth.py`
- ✅ JWT token generation - `backend/app/auth/tokens.py`
- ✅ Token refresh logic
- ✅ Token revocation via Redis

**Authorization**
- ✅ RBAC role definitions - `backend/app/auth/rbac.py`
- ✅ 5 roles: Owner, Admin, Member, Viewer, BillingAdmin
- ✅ 14 granular permissions
- ✅ Permission matrix defined

**Models**
- ✅ Organization model - `backend/app/models.py`
- ✅ AuditLog model with details JSON
- ✅ UsageRecord model for billing

**Infrastructure**
- ✅ PostgreSQL with SQLAlchemy 2.0
- ✅ Redis for token revocation & caching
- ✅ Security headers configured
- ✅ CORS properly set up

### ❌ Missing (Phase 3 Tasks)

1. **User & Workspace Models**
   - User table (email, password_hash, workspace_id, role)
   - Workspace table (name, org_id, created_by)
   - User-Workspace relationships
   - User roles per workspace

2. **Multi-Tenant Filtering**
   - Workspace isolation on all queries
   - Cross-tenant safety tests
   - Workspace_id filtering in repositories

3. **RBAC Middleware**
   - Permission checking decorator
   - Endpoint-level enforcement
   - Role validation middleware

4. **API Key Management**
   - API key generation & storage
   - Key rotation logic
   - Usage tracking per key

5. **Team Management**
   - User invite flow
   - Role assignment per workspace
   - User removal & deactivation

6. **Enhanced Audit Logging**
   - User_id & workspace_id context
   - Action descriptions
   - Resource change tracking

7. **SSO Scaffolding**
   - Okta integration hooks
   - Auth0 integration hooks
   - SAML metadata ready

---

## 📊 Implementation Tasks (13 Total)

### 1. User & Workspace Models
**Dependency**: None  
**Effort**: 2 days  
**Tests**: 15+ unit tests

```python
# User Model
class User(Base):
    id: UUID
    email: str (unique, indexed)
    password_hash: str (bcrypt)
    full_name: str
    profile_picture: Optional[str]
    
    # Multi-tenancy
    primary_workspace_id: Optional[UUID] (FK)
    
    # Status
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    workspaces: List[Workspace] (many-to-many via UserWorkspace)
    api_keys: List[APIKey]

# Workspace Model
class Workspace(Base):
    id: UUID
    name: str
    org_id: UUID (FK)
    created_by: UUID (FK to User)
    
    # Settings
    settings_json: str
    features_enabled: str (JSON list)
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    users: List[User] (many-to-many via UserWorkspace)
    tasks: List[Task]
    api_keys: List[APIKey]

# UserWorkspace Join Table
class UserWorkspace(Base):
    user_id: UUID (FK)
    workspace_id: UUID (FK)
    role: UserRole (Owner, Admin, Member, Viewer)
    joined_at: datetime
    invited_by: Optional[UUID]
```

**Success Criteria**:
- [ ] User model with bcrypt password hashing
- [ ] Workspace model with multi-workspace support
- [ ] UserWorkspace join table with role assignment
- [ ] All relationships properly configured
- [ ] Cascade delete tested
- [ ] Indexes on critical fields

---

### 2. RBAC Models & Middleware
**Dependency**: Task 1  
**Effort**: 2 days  
**Tests**: 20+ permission tests

**Create RBAC enforcement**:
- Permission checking decorator
- Endpoint-level role validation
- Resource ownership checks
- Workspace isolation enforcement

```python
# Permission decorator
@require_permission("read:tasks")
@require_workspace(path="workspace_id")
async def list_tasks(workspace_id: UUID, db: Session) -> List[Task]:
    # Automatically filters by workspace_id
    pass

# Usage:
# - Protects endpoint
# - Validates user has permission
# - Filters results by workspace
# - Returns 403 if unauthorized
```

**Success Criteria**:
- [ ] @require_permission decorator implemented
- [ ] @require_workspace decorator implemented
- [ ] Workspace isolation enforced
- [ ] All endpoints protected
- [ ] 403/401 responses tested
- [ ] Cross-workspace access blocked

---

### 3. JWT Authentication Enhancement
**Dependency**: Task 1  
**Effort**: 1 day  
**Tests**: 10+ token tests

**Enhance JWT to include workspace context**:

```python
# Updated JWT Payload
{
    "sub": "user_id",
    "email": "user@example.com",
    "primary_workspace_id": "workspace_id",
    "workspaces": [
        {"id": "workspace_id", "role": "Owner"},
        {"id": "workspace_id_2", "role": "Member"}
    ],
    "iat": timestamp,
    "exp": timestamp,
    "type": "access"
}
```

**Success Criteria**:
- [ ] JWT includes workspace list
- [ ] Token validation checks workspace access
- [ ] Token refresh preserves workspace context
- [ ] Backward compatibility maintained
- [ ] Payload size reasonable

---

### 4. Workspace Isolation Filtering
**Dependency**: Tasks 1, 2  
**Effort**: 3 days  
**Tests**: 25+ integration tests

**Implement automatic workspace filtering**:
- All queries filtered by workspace_id
- Database-level isolation
- Cross-tenant safety tests
- Audit trail of access

```python
# Repository pattern with workspace filtering
class TaskRepository:
    def get_tasks(self, workspace_id: UUID, db: Session) -> List[Task]:
        # Automatically adds WHERE workspace_id = ?
        return db.query(Task).filter(Task.workspace_id == workspace_id).all()
    
    def get_task(self, workspace_id: UUID, task_id: int, db: Session) -> Optional[Task]:
        # Returns task ONLY if it belongs to workspace
        return db.query(Task).filter(
            Task.workspace_id == workspace_id,
            Task.id == task_id
        ).first()
```

**Success Criteria**:
- [ ] All queries include workspace filter
- [ ] Repository methods workspace-aware
- [ ] Service layer enforces isolation
- [ ] Cross-tenant tests verify safety
- [ ] No data leaks between workspaces

---

### 5. API Key Management
**Dependency**: Task 1  
**Effort**: 2 days  
**Tests**: 15+ tests

**User-level API key generation**:

```python
class APIKey(Base):
    id: UUID
    user_id: UUID (FK)
    workspace_id: UUID (FK)
    name: str
    key_hash: str (bcrypt)  # Never store plaintext
    key_prefix: str         # For display: sk_live_abc...
    
    # Permissions
    permissions: List[str]  # Subset of user's permissions
    
    # Rate limiting
    rate_limit_requests: int
    rate_limit_period: int  # seconds
    
    # Usage
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
```

**Endpoints**:
- `POST /api-keys` - Generate new key
- `GET /api-keys` - List keys
- `DELETE /api-keys/{key_id}` - Revoke key
- `POST /api-keys/{key_id}/rotate` - Rotate key

**Success Criteria**:
- [ ] API key generation working
- [ ] Key hashing with bcrypt
- [ ] Key rotation logic
- [ ] Revocation tracking
- [ ] Rate limiting per key
- [ ] Usage logging

---

### 6. RBAC Middleware & Enforcement
**Dependency**: Tasks 1, 2, 3  
**Effort**: 2 days  
**Tests**: 20+ endpoint tests

**Enforce RBAC on all API endpoints**:

```python
# Decorator usage
@router.get("/tasks")
@require_permission("read:tasks")
@require_workspace("workspace_id")
async def list_tasks(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[TaskResponse]:
    # User must have "read:tasks" permission in workspace
    pass
```

**Coverage**:
- [ ] Auth endpoints protected
- [ ] Task endpoints protected
- [ ] User endpoints protected
- [ ] Billing endpoints protected
- [ ] Admin endpoints protected
- [ ] Workspace endpoints protected

**Success Criteria**:
- [ ] All endpoints have permission checks
- [ ] 403 returned when unauthorized
- [ ] Permissions validated per workspace
- [ ] Hierarchical permissions work (Owner > Admin > Member > Viewer)
- [ ] Special roles handled (BillingAdmin)

---

### 7. Team Invite & Management
**Dependency**: Tasks 1, 2, 6  
**Effort**: 3 days  
**Tests**: 20+ tests

**Implement team management flows**:

```python
class Invitation(Base):
    id: UUID
    workspace_id: UUID (FK)
    email: str
    role: UserRole
    invited_by: UUID (FK to User)
    
    # Status
    status: str  # "pending", "accepted", "expired"
    expires_at: datetime
    accepted_at: Optional[datetime]
    accepted_by: Optional[UUID] (FK to User)

# Endpoints
POST /workspaces/{id}/invitations      # Send invite
GET  /workspaces/{id}/invitations      # List pending
POST /invitations/{id}/accept          # Accept invite
DELETE /workspaces/{id}/users/{user_id}  # Remove user
PUT /workspaces/{id}/users/{user_id}/role  # Change role
```

**Flows**:
1. Owner/Admin invites user via email
2. Email sent with invite link
3. User clicks link, logs in
4. User added to workspace with role
5. Audit log created

**Success Criteria**:
- [ ] Invitation creation & email
- [ ] Invitation acceptance flow
- [ ] Role assignment on acceptance
- [ ] User removal from workspace
- [ ] Role change functionality
- [ ] Invitation expiration (7 days)

---

### 8. Multi-Tenant Filtering in Repositories
**Dependency**: Tasks 1, 4  
**Effort**: 2 days  
**Tests**: 25+ tests

**Update all repository queries**:

```python
# repositories.py - all methods workspace-aware

class TaskRepository:
    @staticmethod
    def get_all(workspace_id: UUID, db: Session) -> List[Task]:
        return db.query(Task).filter_by(workspace_id=workspace_id).all()

class UserRepository:
    @staticmethod
    def get_workspace_users(workspace_id: UUID, db: Session) -> List[User]:
        return db.query(User).join(UserWorkspace).filter(
            UserWorkspace.workspace_id == workspace_id
        ).all()

class AuditLogRepository:
    @staticmethod
    def get_workspace_logs(workspace_id: UUID, db: Session) -> List[AuditLog]:
        return db.query(AuditLog).filter(
            AuditLog.workspace_id == workspace_id
        ).all()
```

**Success Criteria**:
- [ ] All queries filtered by workspace
- [ ] No cross-tenant data exposure
- [ ] Query tests verify isolation
- [ ] Performance acceptable with filtering
- [ ] Indexes optimized

---

### 9. Enhanced Audit Logging
**Dependency**: Tasks 1, 2  
**Effort**: 1.5 days  
**Tests**: 15+ tests

**Expand audit logs with context**:

```python
class AuditLog(Base):
    # Updated fields
    user_id: UUID (FK)           # Who performed action
    workspace_id: UUID (FK)      # Which workspace
    action: str                  # "create_task", "invite_user", etc
    resource_type: str           # "task", "user", "workspace"
    resource_id: UUID            # ID of resource
    
    # Changes
    changes_before: str (JSON)   # Old values
    changes_after: str (JSON)    # New values
    
    # Meta
    ip_address: str
    user_agent: str
    created_at: datetime
```

**Audit all operations**:
- User creation, invitation, role changes
- Task creation, updates, execution
- Workspace creation, settings changes
- API key creation, rotation
- Billing changes, subscription updates

**Success Criteria**:
- [ ] All user actions logged
- [ ] Before/after values captured
- [ ] Workspace context included
- [ ] IP & user agent logged
- [ ] Immutable audit trail
- [ ] Query performance acceptable

---

### 10. Provider UI Enhancement
**Dependency**: Task 1  
**Effort**: 1 day  
**Tests**: 10+ component tests

**Display agent execution info in dashboard**:

```typescript
// Provider execution details
- Agent name (OpenAI, Anthropic, etc)
- Cost per task execution
- Latency (execution time)
- Success rate
- Provider health status

// Dashboard widget
<ProviderMetrics taskId={taskId} />

// Task history with provider info
<TaskHistory 
  agent={task.agent}
  cost={task.cost}
  latency={task.latency_ms}
/>
```

**Success Criteria**:
- [ ] Agent info displayed
- [ ] Cost tracking visible
- [ ] Latency metrics shown
- [ ] Provider health status
- [ ] Historical trends visible
- [ ] Real-time updates

---

### 11. SSO Scaffolding
**Dependency**: Task 3  
**Effort**: 1 day  
**Tests**: 5+ integration hook tests

**Create SSO integration hooks** (no implementation, ready for future):

```python
# backend/app/auth/sso.py

class OktaSSO:
    """Okta SAML/OIDC integration hooks"""
    def get_authorization_url(self) -> str:
        # Hook for Okta auth
        pass
    
    async def exchange_code(self, code: str) -> Dict:
        # Hook for token exchange
        pass

class Auth0SSO:
    """Auth0 OIDC integration hooks"""
    def get_authorization_url(self) -> str:
        # Hook for Auth0 auth
        pass
    
    async def exchange_code(self, code: str) -> Dict:
        # Hook for token exchange
        pass

# Configuration via environment
OKTA_DOMAIN=None      # Disabled until configured
AUTH0_DOMAIN=None     # Disabled until configured
```

**Success Criteria**:
- [ ] SSO provider classes created
- [ ] Configuration hooks in place
- [ ] Environment-based toggles
- [ ] Ready for future implementation

---

### 12. Billing Compliance & Usage Tracking
**Dependency**: Tasks 1, 2, 9  
**Effort**: 1.5 days  
**Tests**: 10+ tests

**Track usage per workspace & user**:

```python
class UsageRecord(Base):
    # Enhanced tracking
    workspace_id: UUID (FK)
    user_id: UUID (FK)
    task_id: UUID (FK)
    
    # Usage details
    usage_type: str  # "task_execution", "api_call", "storage"
    quantity: int    # Number of tokens, requests, etc
    cost: Decimal    # In USD
    
    # Compliance
    provider_used: str
    model_used: str
    created_at: datetime
```

**Endpoints**:
- `GET /billing/usage` - Monthly usage
- `GET /billing/usage/workspace/{id}` - Per-workspace
- `GET /billing/invoices` - Generated invoices

**Success Criteria**:
- [ ] Usage tracked per workspace
- [ ] Cost calculation accurate
- [ ] Usage limits enforced
- [ ] Billing compliance ready
- [ ] Reports available

---

### 13. Enterprise Auth Documentation
**Dependency**: All tasks  
**Effort**: 1 day  
**Tests**: Documentation review

**Create comprehensive documentation**:

- `ENTERPRISE_AUTH_GUIDE.md` - Setup & configuration
- `MULTI_TENANCY_GUIDE.md` - Implementation details
- `API_KEYS_GUIDE.md` - API key management
- `TEAM_MANAGEMENT_GUIDE.md` - User management
- `SSO_INTEGRATION_GUIDE.md` - SSO setup (future)
- `AUDIT_LOGGING_GUIDE.md` - Audit trail querying

**Success Criteria**:
- [ ] All features documented
- [ ] Setup instructions clear
- [ ] Code examples provided
- [ ] Troubleshooting guide
- [ ] Best practices documented

---

## 🔄 Dependency Chain

```
┌─ Task 1: User & Workspace Models
│  ├─ Task 2: RBAC Models
│  │  ├─ Task 6: RBAC Middleware
│  │  │  └─ Task 7: Team Invite
│  │  └─ Task 9: Enhanced Audit
│  │
│  ├─ Task 3: JWT Enhancement
│  │  ├─ Task 5: API Keys
│  │  └─ Task 11: SSO Scaffold
│  │
│  ├─ Task 4: Workspace Filtering
│  │  └─ Task 8: Repository Filtering
│  │
│  ├─ Task 10: Provider UI
│  └─ Task 12: Billing Compliance

└─ Task 13: Documentation (last)
```

---

## 📅 Implementation Timeline

### Week 1
- **Days 1-2**: Task 1 (User & Workspace Models)
- **Days 3-4**: Task 2 (RBAC Models) + Task 3 (JWT)
- **Day 5**: Task 4 (Workspace Filtering)

### Week 2
- **Days 1-2**: Task 8 (Repository Filtering)
- **Days 3-4**: Task 6 (RBAC Middleware)
- **Day 5**: Task 5 (API Keys)

### Week 3
- **Days 1-2**: Task 7 (Team Invite)
- **Days 3-4**: Task 9 (Audit) + Task 10 (Provider UI)
- **Day 5**: Task 11 (SSO) + Task 12 (Billing) + Task 13 (Docs)

---

## 🎯 Success Criteria

### Functional Requirements
- ✅ Multi-workspace support
- ✅ Per-workspace user management
- ✅ Role-based access control
- ✅ API key management
- ✅ Team invitations
- ✅ Enhanced audit logging
- ✅ Workspace isolation verified

### Quality Requirements
- ✅ 90%+ test coverage (up from 80%)
- ✅ 95%+ type hints
- ✅ 95%+ docstrings
- ✅ Security verified
- ✅ Performance acceptable
- ✅ Documentation complete

### Testing Requirements
- ✅ Unit tests (100+ new tests)
- ✅ Integration tests (30+ new tests)
- ✅ Cross-tenant safety tests
- ✅ Permission enforcement tests
- ✅ End-to-end user flow tests

---

## 🚀 Next Steps

1. **Review this plan** - Confirm approach and timeline
2. **Start Task 1** - User & Workspace Models (Day 1)
3. **Parallel work** - Frontend components while backend models being built
4. **Weekly reviews** - Check progress and adjust as needed
5. **Testing coverage** - Maintain 90%+ coverage throughout

---

## 📊 Expected Outcomes

After Phase 3 completion:

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Code Coverage | 80% | 90% | 📈 |
| Type Hints | 95% | 95% | ✅ |
| Docstrings | 90% | 95% | 📈 |
| Security Score | 98/100 | 98/100 | ✅ |
| Enterprise Features | 30% | 100% | 📈 |
| Overall Quality | 9.2/10 | 9.5/10 | 📈 |

---

**Status**: Ready to implement  
**Estimated Duration**: 2-3 weeks  
**Team Size**: 1-2 developers  
**Complexity**: Medium-High

Let's build enterprise-grade multi-tenancy! 🚀
