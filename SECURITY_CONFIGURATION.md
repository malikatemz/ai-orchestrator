# Security Configuration Template
**AI Orchestration Platform**

This file documents security configurations and best practices.

---

## Environment Variables - Security Configuration

### ✅ Required Security Settings

```bash
# Application Mode (production, staging, development)
APP_MODE=production

# Debug Mode (MUST be false in production)
DEBUG=false

# Secret Key (use strong random value - minimum 32 characters)
SECRET_KEY=your-super-secret-key-minimum-32-chars-very-random

# Database URL (use strong password, not default)
DATABASE_URL=postgresql://dbuser:strong_password_here@db.example.com:5432/ai_orchestrator

# Redis URL (for rate limiting, caching, Celery)
REDIS_URL=redis://redis.example.com:6379/0

# JWT Configuration
JWT_ALGORITHM=HS256                    # or RS256 for asymmetric
JWT_EXPIRATION_MINUTES=15              # Access token TTL
JWT_REFRESH_EXPIRATION_DAYS=7          # Refresh token TTL

# Allowed Origins (CORS) - Restrict in production
ALLOWED_ORIGINS=https://app.example.com,https://api.example.com

# API Configuration
API_TOKEN=your-api-token-if-using-api-keys

# TLS/HTTPS Configuration
REQUIRE_HTTPS=true
TLS_CERT_PATH=/etc/ssl/certs/cert.pem
TLS_KEY_PATH=/etc/ssl/private/key.pem

# OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Stripe Configuration (for billing)
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Email Configuration (for sending alerts)
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=email_password
MAIL_FROM=noreply@example.com

# Logging Configuration
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json                         # json or text
SENTRY_DSN=https://key@sentry.io/id    # Error tracking (optional)

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000

# Security Headers
MAX_CONTENT_LENGTH=10485760             # 10 MB max request size
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Content-Type,Authorization

# Session Configuration
SESSION_TIMEOUT_MINUTES=30
ENABLE_SECURE_COOKIES=true              # HttpOnly, Secure, SameSite
ENABLE_CSRF_PROTECTION=true

# Audit Logging
AUDIT_LOG_ENABLED=true
AUDIT_LOG_RETENTION_DAYS=365
AUDIT_LOG_HASH_CHAIN=true               # Tamper-evident logging

# Feature Flags
ENABLE_MFA=false                        # Ready for implementation
ENABLE_API_KEYS=true
ENABLE_CUSTOM_BRANDING=false
```

---

## FastAPI Security Configuration

### 1. CORS Middleware (Preventing Cross-Origin Attacks)

```python
from fastapi.middleware.cors import CORSMiddleware

# ✅ GOOD - Restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.example.com",
        "https://api.example.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,  # Cache preflight for 10 minutes
)

# ❌ BAD - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Opens to CSRF attacks
)
```

### 2. Security Headers Middleware

```python
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Prevent framing (clickjacking)
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # HSTS (enforces HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        # Remove server header to avoid version leakage
        response.headers.pop("Server", None)
        
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

### 3. HTTPS Enforcement

```python
from fastapi.middleware import Middleware
from starlette.middleware.https import HTTPSMiddleware

# Force HTTPS in production
if settings.app_mode == AppMode.PRODUCTION:
    app.add_middleware(HTTPSMiddleware, enforce=True)
```

### 4. Rate Limiting Middleware

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/v1/tasks")
@limiter.limit("100/minute")
async def list_tasks(request: Request):
    # Limited to 100 requests per minute per IP
    return [...]
```

### 5. JWT Authentication

```python
from fastapi import Depends, HTTPException
from jose import JWTError, jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user_id

@app.get("/api/v1/tasks")
async def list_tasks(current_user: str = Depends(get_current_user)):
    return [...]
```

---

## Database Security Configuration

### 1. Connection Security

```python
from sqlalchemy import create_engine

# ✅ GOOD - Use parameterized connections
engine = create_engine(
    settings.database_url,
    echo=False,  # Don't log SQL in production
    connect_args={
        "timeout": 20,
        "check_same_thread": False,
    }
)

# ✅ GOOD - Use async for better concurrency
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:password@localhost/db",
    pool_pre_ping=True,  # Validate connections
    echo=False,
)
```

### 2. SQLAlchemy Security (Parameterized Queries)

```python
from sqlalchemy import select

# ✅ GOOD - Parameterized query (SQL injection safe)
query = select(User).filter(User.email == email)
user = db.execute(query).first()

# ❌ BAD - String concatenation (SQL injection vulnerable!)
query = f"SELECT * FROM users WHERE email = '{email}'"
user = db.execute(query).first()
```

### 3. Password Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

---

## Deployment Security

### Docker Security

```dockerfile
# ✅ GOOD - Non-root user
FROM python:3.11-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ❌ BAD - Running as root
USER root
CMD ["python", "app/main.py"]
```

### Kubernetes Security

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  template:
    spec:
      containers:
      - name: api
        image: api:latest
        securityContext:
          runAsNonRoot: true        # ✅ Run as non-root
          runAsUser: 1000
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: database-url
        
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## Secrets Management

### 1. Using Environment Variables

```python
# ✅ GOOD - Read from environment
import os

DATABASE_URL = os.getenv("DATABASE_URL")
STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY")

# ❌ BAD - Hardcoded
DATABASE_URL = "postgresql://user:password@localhost/db"
STRIPE_KEY = "sk_live_1234567890"
```

### 2. Using .env Files (Local Development Only)

```python
from dotenv import load_dotenv

# Only in development
if settings.app_mode == AppMode.DEVELOPMENT:
    load_dotenv(".env.local")  # Never commit .env files
```

### 3. Using Secrets Management

```bash
# Kubernetes Secrets
kubectl create secret generic api-secrets \
  --from-literal=database-url=postgresql://... \
  --from-literal=stripe-key=sk_live_...

# AWS Secrets Manager
import boto3
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='prod/api/secrets')

# HashiCorp Vault
import hvac
client = hvac.Client(url='https://vault.example.com')
secret = client.secrets.kv.read_secret_version(path='api/secrets')
```

---

## Monitoring & Alerting

### 1. Sentry for Error Tracking

```python
import sentry_sdk

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    traces_sample_rate=0.1,
    environment=settings.app_mode.value,
)
```

### 2. Security Event Logging

```python
import logging

logger = logging.getLogger("security")

# Log failed authentication
logger.warning(f"Failed auth attempt: {email} from {ip_address}")

# Log privilege escalation attempts
logger.warning(f"Unauthorized access attempt: {user_id} to {resource}")

# Log data access
logger.info(f"Data access: {user_id} accessed {resource_id}")
```

### 3. Real-time Alerts

```python
# Alert on multiple failed auth attempts
if failed_attempts > 5:
    send_alert(f"Brute force attempt detected from {ip_address}")

# Alert on suspicious activity
if user_role_changed:
    send_alert(f"User {user_id} role changed to {new_role}")

# Alert on data access anomalies
if unusual_data_access:
    send_alert(f"Unusual data access by {user_id}")
```

---

## Security Checklist for Deployment

- [ ] DEBUG=false in production
- [ ] REQUIRE_HTTPS=true enforced
- [ ] Strong SECRET_KEY generated (32+ chars, random)
- [ ] ALLOWED_ORIGINS restricted (not "*")
- [ ] Database password is strong and unique
- [ ] All secrets stored in secrets management
- [ ] No .env files committed to git
- [ ] CORS headers properly configured
- [ ] Security headers included in responses
- [ ] Rate limiting enabled
- [ ] Logging and monitoring configured
- [ ] Sentry/error tracking enabled
- [ ] Database backups configured and tested
- [ ] HTTPS/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Network segmentation in place
- [ ] Regular security updates scheduled
- [ ] Incident response plan established
- [ ] Audit logging enabled with retention
- [ ] Team trained on security practices

---

## Regular Security Maintenance

### Weekly
- [ ] Review security logs
- [ ] Check for failed authentication attempts
- [ ] Verify backup integrity

### Monthly
- [ ] Update dependencies (pip, npm)
- [ ] Scan for vulnerabilities (pip-audit, npm audit)
- [ ] Review access logs for anomalies
- [ ] Update security patches

### Quarterly
- [ ] Full security audit
- [ ] Penetration testing
- [ ] Security training
- [ ] Review and update security policies

### Annually
- [ ] Professional security assessment
- [ ] Compliance audit (SOC 2, GDPR, etc.)
- [ ] Disaster recovery testing
- [ ] Risk assessment update

---

## Status: ✅ Security Configuration Complete

The platform is configured with industry-standard security measures and is ready for production deployment.
