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
    \"\"\"Logs security events for compliance and monitoring\"\"\"
    
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
        \"\"\"Log login attempt\"\"\"
        try:
            event_type = SecurityEventType.LOGIN_SUCCESS if success else SecurityEventType.LOGIN_FAILURE
            
            details = {
                \"email\": email,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            if not success and reason:
                details[\"failure_reason\"] = reason
            
            self._log_event(
                db,
                actor=email,
                event=event_type.value,
                resource_type=\"user\",
                resource_id=None,
                details=details,
                severity=\"high\" if not success else \"info\",
            )
            
            # Log to application logger
            level = \"warning\" if not success else \"info\"
            getattr(self.logger, level)(
                f\"Login {'success' if success else 'failure'} for {email} from {ip_address}\",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log login attempt: {str(e)}\")
    
    def log_oauth_event(
        self,
        db: Session,
        provider: str,
        success: bool,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        \"\"\"Log OAuth authentication event\"\"\"
        try:
            event_type = SecurityEventType.OAUTH_SUCCESS if success else SecurityEventType.OAUTH_FAILURE
            
            details = {
                \"provider\": provider,
                \"email\": email,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            if not success and reason:
                details[\"failure_reason\"] = reason
            
            self._log_event(
                db,
                actor=email or \"unknown\",
                event=event_type.value,
                resource_type=\"oauth_flow\",
                resource_id=None,
                details=details,
                severity=\"high\" if not success else \"info\",
            )
            
            level = \"warning\" if not success else \"info\"
            getattr(self.logger, level)(
                f\"OAuth {provider} {'success' if success else 'failure'}\" +
                (f\" for {email}\" if email else \"\"),
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log OAuth event: {str(e)}\")
    
    def log_token_operation(
        self,
        db: Session,
        operation: str,  # created, refreshed, revoked
        user_id: str,
        token_type: str = \"access\",
        success: bool = True,
    ) -> None:
        \"\"\"Log token operations (create, refresh, revoke)\"\"\"
        try:
            event_map = {
                \"created\": SecurityEventType.TOKEN_CREATED,
                \"refreshed\": SecurityEventType.TOKEN_REFRESHED,
                \"revoked\": SecurityEventType.TOKEN_REVOKED,
            }
            
            event_type = event_map.get(operation, SecurityEventType.TOKEN_CREATED)
            
            details = {
                \"operation\": operation,
                \"token_type\": token_type,
                \"user_id\": user_id,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            self._log_event(
                db,
                actor=user_id,
                event=event_type.value,
                resource_type=\"token\",
                resource_id=None,
                details=details,
                severity=\"info\",
            )
            
            self.logger.info(
                f\"Token {operation} for user {user_id}\",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log token operation: {str(e)}\")
    
    def log_permission_denied(
        self,
        db: Session,
        user_id: str,
        required_permission: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        \"\"\"Log permission denied events (potential security threat)\"\"\"
        try:
            details = {
                \"user_id\": user_id,
                \"required_permission\": required_permission,
                \"resource_type\": resource_type,
                \"resource_id\": resource_id,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            self._log_event(
                db,
                actor=user_id,
                event=SecurityEventType.PERMISSION_DENIED.value,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                severity=\"high\",  # Security relevant
            )
            
            self.logger.warning(
                f\"Permission denied for user {user_id} - required: {required_permission}\",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log permission denied: {str(e)}\")
    
    def log_suspicious_activity(
        self,
        db: Session,
        user_id: Optional[str],
        activity_type: str,
        details_dict: Dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> None:
        \"\"\"Log suspicious activities\"\"\"
        try:
            details = {
                \"activity_type\": activity_type,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
                **details_dict,
            }
            
            self._log_event(
                db,
                actor=user_id or \"unknown\",
                event=SecurityEventType.SUSPICIOUS_ACTIVITY.value,
                resource_type=\"security\",
                resource_id=None,
                details=details,
                severity=\"critical\",  # Alert administrators immediately
            )
            
            self.logger.critical(
                f\"[SECURITY ALERT] Suspicious activity detected: {activity_type}\" +
                (f\" from {ip_address}\" if ip_address else \"\"),
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log suspicious activity: {str(e)}\")
    
    def log_rate_limit_exceeded(
        self,
        db: Session,
        user_id_or_ip: str,
        endpoint: str,
        ip_address: Optional[str] = None,
    ) -> None:
        \"\"\"Log rate limit violations\"\"\"
        try:
            details = {
                \"target\": user_id_or_ip,
                \"endpoint\": endpoint,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            self._log_event(
                db,
                actor=user_id_or_ip,
                event=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                resource_type=\"security\",
                resource_id=None,
                details=details,
                severity=\"high\",
            )
            
            self.logger.warning(
                f\"Rate limit exceeded for {user_id_or_ip} on {endpoint}\",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log rate limit: {str(e)}\")
    
    def log_invalid_input(
        self,
        db: Session,
        user_id: Optional[str],
        input_type: str,
        reason: str,
        ip_address: Optional[str] = None,
    ) -> None:
        \"\"\"Log invalid input attempts\"\"\"
        try:
            details = {
                \"input_type\": input_type,
                \"reason\": reason,
                \"ip_address\": ip_address,
                \"timestamp\": datetime.utcnow().isoformat(),
            }
            
            self._log_event(
                db,
                actor=user_id or \"unknown\",
                event=SecurityEventType.INVALID_INPUT.value,
                resource_type=\"input\",
                resource_id=None,
                details=details,
                severity=\"medium\",
            )
            
            self.logger.warning(
                f\"Invalid input detected: {reason}\",
                extra=details,
            )
        except Exception as e:
            self.logger.error(f\"Failed to log invalid input: {str(e)}\")
    
    def _log_event(
        self,
        db: Session,
        actor: str,
        event: str,
        resource_type: str,
        resource_id: Optional[int],
        details: Dict[str, Any],
        severity: str = \"info\",
    ) -> None:
        \"\"\"Internal method to log event to database\"\"\"
        try:
            audit_log = AuditLog(
                actor=actor,
                event=event,
                resource_type=resource_type,
                resource_id=resource_id,
                details_json=json.dumps(details),
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            self.logger.error(f\"Failed to write audit log: {str(e)}\")
            # Don't raise - logging shouldn't break the application


def log_security_event(
    db: Session,
    actor: str,
    event: SecurityEventType,
    resource_type: str = \"security\",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    \"\"\"Helper function for logging security events\"\"\"
    logger = SecurityAuditLogger()
    logger._log_event(
        db=db,
        actor=actor,
        event=event.value,
        resource_type=resource_type,
        resource_id=None,
        details=details or {},
        severity=\"high\",
    )


__all__ = [\"SecurityAuditLogger\", \"SecurityEventType\", \"log_security_event\"]
