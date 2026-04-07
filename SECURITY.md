# Security Hardening Guide - AI Orchestrator Phase 5+

## Overview

This guide documents all security improvements implemented in Phase 5 and beyond, including authentication, authorization, data protection, and infrastructure security.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Secrets Management](#secrets-management)
3. [Network Security](#network-security)
4. [Data Protection](#data-protection)
5. [Monitoring & Logging](#monitoring--logging)
6. [Production Deployment](#production-deployment)
7. [Security Checklist](#security-checklist)

---

## Authentication & Authorization

### JWT Token Security

**Implementation:**
- Access tokens: 15-minute expiration (configurable)
- Refresh tokens: 7-day expiration (configurable)
- Token revocation via Redis blacklist
- Minimum 32-character secret key enforcement

**Best Practices:**
```python
# DO: Generate strong secret keys
import secrets
key = secrets.token_urlsafe(32)  # At least 32 characters

# DON'T: Use default or weak keys
"your-super-secret-key-change-in-production"  # INSECURE
```

**Configuration:**
```env
JWT_SECRET_KEY=your-secure-32-char-minimum-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### OAuth2 Integration

**Supported Providers:**
- Google OAuth2
- GitHub OAuth2
- SAML (framework ready)

**Security Features:**
- State parameter validation (CSRF protection)
- Redirect URI validation
- Secure token exchange
- User info verification

**Configuration:**
```env
GOOGLE_CLIENT_ID=your-google-id
GOOGLE_CLIENT_SECRET=your-secret
GITHUB_CLIENT_ID=your-github-id
GITHUB_CLIENT_SECRET=your-secret
```

### Role-Based Access Control (RBAC)

**Roles Hierarchy:**
1. **Owner** - Full system access, can manage all users
2. **Admin** - Full operational access, cannot manage billing
3. **Member** - Read/write data, limited management
4. **Viewer** - Read-only access
5. **BillingAdmin** - Billing management only

**Permission Model:**
- READ_DATA
- WRITE_DATA
- DELETE_DATA
- MANAGE_USERS
- MANAGE_BILLING
- CONFIGURE_INTEGRATIONS
- VIEW_ANALYTICS
- MANAGE_RBAC

---

## Secrets Management

### Environment-Based Secrets

**Development:**
```bash
# Generate development key (not for production)
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

**Production:**
Never hardcode secrets. Use secure secret management:

**Option 1: AWS Secrets Manager**
```python
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='ai-orchestrator-secrets')
```

**Option 2: HashiCorp Vault**
```python
import hvac
client = hvac.Client(url='https://vault.example.com')
secret = client.secrets.kv.read_secret_version(path='ai-orchestrator')
```

**Option 3: Azure Key Vault**
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
client = SecretClient(vault_url='https://vault.azure.com', credential=credential)
secret = client.get_secret('ai-orchestrator-key')
```

### Critical Secrets

| Secret | Usage | Rotation | Minimum Length |
|--------|-------|----------|-----------------|
| JWT_SECRET_KEY | Token signing | Monthly | 32 chars |
| STRIPE_SECRET_KEY | Billing API | N/A (provider) | - |
| OAuth Secrets | Social login | Quarterly | 16 chars |
| API_TOKEN | API authentication | Quarterly | 32 chars |
| Database Password | DB connection | Half-yearly | 32 chars |
| Redis Password | Cache/broker | Half-yearly | 32 chars |

---

## Network Security

### HTTPS Enforcement

**Development:**
```env
PUBLIC_APP_URL=http://localhost:3000
PUBLIC_API_URL=http://localhost:8000
```

**Production:**
```env
PUBLIC_APP_URL=https://app.yourdomain.com
PUBLIC_API_URL=https://api.yourdomain.com
```

⚠️ **CRITICAL:** URLs must use HTTPS in production or app will fail on startup.

### Security Headers

Automatically added by `SecurityHeadersMiddleware`:

| Header | Purpose | Value |
|--------|---------|-------|
| Strict-Transport-Security | Force HTTPS | max-age=31536000 |
| X-Frame-Options | Prevent clickjacking | DENY |
| X-Content-Type-Options | Prevent MIME sniffing | nosniff |
| Content-Security-Policy | XSS & injection protection | See config |
| X-XSS-Protection | Browser XSS filter | 1; mode=block |
| Referrer-Policy | Control referrer info | strict-origin-when-cross-origin |
| Permissions-Policy | Disable features | Disables all by default |

### CORS Configuration

**Development (permissive):**
```env
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
CORS_ALLOW_CREDENTIALS=true
```

**Production (restrictive):**
```env
ALLOWED_ORIGINS=https://app.yourdomain.com,https://api.yourdomain.com
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Content-Type,Authorization
```

⚠️ **BLOCK:** `ALLOWED_ORIGINS=*` is forbidden in production.

---

## Data Protection

### Database Security

**Development:**
```env
DATABASE_URL=sqlite:///./ai_orchestrator.db
```

**Production (PostgreSQL):**
```env
DATABASE_URL=postgresql+asyncpg://user:secure_password@db.example.com:5432/ai_orch
```

**Best Practices:**
1. Use strong passwords (32+ characters)
2. Enable SSL/TLS for DB connections
3. Restrict DB access by IP
4. Use separate credentials for each environment
5. Enable encryption at rest (AWS RDS encryption, etc.)
6. Regular backups with encryption
7. Audit database access

### Password Security (for future user management)

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password during registration
hashed_pwd = pwd_context.hash(password)

# Verify during login
pwd_context.verify(password, hashed_pwd)
```

### API Token Security

```python
import secrets

# Generate random token
token = secrets.token_urlsafe(32)  # URL-safe, 32 bytes

# Storage: Hash before storing
hashed = hashlib.sha256(token.encode()).hexdigest()
```

---

## Monitoring & Logging

### Security Logging

Log all security events:
- Login attempts (success/failure)
- Token creation/revocation
- Permission changes
- Configuration updates
- Failed authentication attempts
- Suspicious activities

### Sentry Integration

```env
SENTRY_DSN=https://your-key@sentry.io/project-id
```

Automatically captures:
- Unhandled exceptions
- Security errors
- Database issues
- Service failures

**Setup:**
1. Create account at https://sentry.io
2. Create project
3. Copy DSN to `SENTRY_DSN`
4. Monitor issues in Sentry dashboard

### Audit Logging

Track user actions:
```python
log_event(actor, event, resource_type, resource_id, details)
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All secrets in secure secret manager (not .env)
- [ ] HTTPS enabled (all URIs use https://)
- [ ] CORS restricted to specific domains
- [ ] Database encrypted and backed up
- [ ] JWT secret key rotated
- [ ] API tokens issued and secured
- [ ] OAuth2 providers configured with production URLs
- [ ] Stripe keys set to live mode (sk_live_*)
- [ ] Monitoring enabled (Sentry, CloudWatch, etc.)
- [ ] Rate limiting configured
- [ ] Logging aggregation setup
- [ ] Database migrations tested
- [ ] Security headers verified
- [ ] TLS/SSL certificates valid
- [ ] WAF (Web Application Firewall) enabled

### Docker Secrets

```dockerfile
# Use Docker secrets instead of env vars for production
docker run --secret jwt_key --secret db_password \
  -e JWT_SECRET_KEY_FILE=/run/secrets/jwt_key \
  myapp
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
stringData:
  jwt-secret-key: your-secret-key
  stripe-secret-key: your-stripe-key
---
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    env:
    - name: JWT_SECRET_KEY
      valueFrom:
        secretKeyRef:
          name: app-secrets
          key: jwt-secret-key
```

---

## Security Checklist

### Authentication
- [ ] OAuth2 providers configured
- [ ] JWT token time-based expiration
- [ ] Token refresh implemented
- [ ] Token revocation available
- [ ] Session timeout configured
- [ ] Multi-factor authentication (roadmap)

### Authorization
- [ ] RBAC implemented with 5 roles
- [ ] Permission checks on all protected endpoints
- [ ] Audit logging for auth changes

### Secrets
- [ ] No hardcoded secrets in code
- [ ] .env file in .gitignore
- [ ] Secrets rotated regularly
- [ ] Minimum length requirements enforced
- [ ] Production secrets in secure vault

### Network
- [ ] HTTPS enforced in production
- [ ] TLS 1.2+ only
- [ ] Security headers enabled
- [ ] CORS properly configured
- [ ] Rate limiting enabled

### Data
- [ ] Database encrypted at rest
- [ ] Database encrypted in transit
- [ ] Regular backups
- [ ] Backup encryption
- [ ] PII handling documented

### Monitoring
- [ ] Error tracking (Sentry)
- [ ] Audit logging
- [ ] Security event alerts
- [ ] Log aggregation
- [ ] Failed auth monitoring

### Deployment
- [ ] Secrets manager used
- [ ] No secrets in git history
- [ ] Environment-specific configs
- [ ] Deployment logs reviewed
- [ ] Staging environment matches prod

---

## Incident Response

### Security Incident Steps

1. **Detect**: Monitor logs and alerts
2. **Contain**: Disable affected accounts/tokens
3. **Eradicate**: Fix vulnerability
4. **Recover**: Restore from backups if needed
5. **Review**: Improve monitoring/security

### Secret Compromise

If a secret is compromised:

1. Immediately revoke the secret
2. Generate new secret
3. Update all environments
4. Check logs for unauthorized use
5. Notify affected users
6. Monitor for suspicious activity

---

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [OAuth2 Security](https://tools.ietf.org/html/rfc6749)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

**Last Updated:** April 6, 2026
**Phase:** 5 - Security Hardening Complete
**Status:** Production Ready
