"""
Security Audit Logging - Compliance & Monitoring
Logs all security-relevant events for compliance, monitoring, and incident investigation
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog


class SecurityEventType(str, Enum):
    """Security-relevant event types"""
    # Authentication events
    LOGIN_SUCCESS = "auth:login_success"
    LOGIN_FAILURE = "auth:login_failure"
    LOGOUT = "auth:logout"
    TOKEN_CREATED = "auth:token_created"
    TOKEN_REFRESHED = "auth:token_refreshed"
    TOKEN_REVOKED = "auth:token_revoked"
    OAUTH_INITIATED = "auth:oauth_initiated"
    OAUTH_SUCCESS = "auth:oauth_success"
    OAUTH_FAILURE = "auth:oauth_failure"
    
    # Authorization events
    PERMISSION_CHECK = "authz:permission_check"
    PERMISSION_DENIED = "authz:permission_denied"
    ROLE_CHANGED = "authz:role_changed"
    
    # Security events
    SUSPICIOUS_ACTIVITY = "security:suspicious_activity"
    RATE_LIMIT_EXCEEDED = "security:rate_limit_exceeded"
    INVALID_INPUT = "security:invalid_input"
    SQL_INJECTION_ATTEMPT = "security:sql_injection_attempt"
    XSS_ATTEMPT = "security:xss_attempt"
    CSRF_TOKEN_INVALID = "security:csrf_token_invalid"
    
    # System events
    CONFIG_CHANGED = "system:config_changed"
    SECRET_ACCESSED = "system:secret_accessed"
    ERROR_OCCURRED = "system:error_occurred"


class SecurityAuditLogger:
    """Logs security events for compliance and monitoring"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def log_login_attempt(
        self,
        db: Session,
        email: str,
        success: bool,
        ip_address: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log login attempt"""
        try:
            event_type = (
                SecurityEventType.LOGIN_SUCCESS
                if success
                else SecurityEventType.LOGIN_FAILURE
            )
            
            details = {
                "email": email,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if not success and reason:
                details["failure_reason"] = reason
            
            self._log_event(
                db,
                actor=email,
                event=event_type.value,
                resource_type="user",
                resource_id=None,
                details=details,
                severity="high" if not success else "info",
            )
            
            # Log to application logger
            level = "warning" if not success else "info"
            getattr(self.logger, level)(
                f"Login {'success' if success else 'failure'} for {email} from {ip_address}",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f"Failed to log login attempt: {str(e)}")
    
    def _log_event(
        self,
        db: Session,
        actor: str,
        event: str,
        resource_type: str,
        resource_id: Optional[str],
        details: Dict[str, Any],
        severity: str = "info",
    ) -> None:
        """Log a security event to the database"""
        try:
            log_entry = AuditLog(
                actor=actor,
                event=event,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details),
                severity=severity,
                timestamp=datetime.utcnow(),
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            self.logger.error(f"Failed to log event to database: {str(e)}")


__all__ = ["SecurityAuditLogger", "SecurityEventType"]
