"""Tamper-evident audit logging with hash chain verification"""

import hashlib
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models import AuditLog
from ..time_utils import utc_now

logger = logging.getLogger(__name__)


class AuditIntegrityError(Exception):
    """Audit log integrity violation detected"""
    pass


def compute_row_hash(
    row_id: int,
    user_id: str,
    action: str,
    details_json: Dict[str, Any],
    timestamp: datetime,
    previous_hash: Optional[str] = None,
) -> str:
    """
    Compute SHA256 hash of an audit log row.
    
    Hash includes:
      id + user_id + action + timestamp + details_json + previous_hash
    
    This creates a tamper-evident chain.
    """
    # Serialize data consistently
    data_str = (
        f"{row_id}|"
        f"{user_id}|"
        f"{action}|"
        f"{int(timestamp.timestamp())}|"
        f"{str(details_json)}|"
        f"{previous_hash or ''}"
    )
    
    return hashlib.sha256(data_str.encode()).hexdigest()


def log_event(
    db: Session,
    user_id: str,
    org_id: str,
    action: str,
    resource_type: str,
    resource_id: int,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Log an audit event with chain verification.
    
    Returns the created AuditLog row.
    """
    details = details or {}
    
    # Get previous row (most recent)
    previous = db.query(AuditLog).filter(
        AuditLog.org_id == org_id
    ).order_by(desc(AuditLog.created_at)).first()
    
    previous_hash = previous.row_hash if previous else None
    
    # Create new log entry
    log = AuditLog(
        org_id=org_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=details,
        previous_hash=previous_hash,
    )
    
    # Compute this row's hash
    log.row_hash = compute_row_hash(
        row_id=0,  # Will be assigned by DB
        user_id=str(user_id),
        action=action,
        details_json=details,
        timestamp=utc_now(),
        previous_hash=previous_hash,
    )
    
    db.add(log)
    db.flush()
    
    # Update hash with actual ID
    log.row_hash = compute_row_hash(
        row_id=log.id,
        user_id=str(user_id),
        action=action,
        details_json=details,
        timestamp=log.created_at,
        previous_hash=previous_hash,
    )
    
    db.commit()
    logger.info(f"Audit event logged: {action} on {resource_type}:{resource_id}")
    
    return log


def verify_audit_chain(
    db: Session,
    org_id: str,
    raise_on_break: bool = False,
) -> Dict[str, Any]:
    """
    Verify the integrity of the entire audit log chain for an org.
    
    Returns:
      {
        "valid": bool,
        "broken_at": int | null,  # ID of broken row, if any
        "total_checked": int,
      }
    
    Raises AuditIntegrityError if raise_on_break=True and chain is broken.
    """
    logs = db.query(AuditLog).filter(
        AuditLog.org_id == org_id
    ).order_by(AuditLog.created_at).all()
    
    if not logs:
        return {"valid": True, "broken_at": None, "total_checked": 0}
    
    previous_hash = None
    
    for log in logs:
        # Recompute hash for this row
        expected_hash = compute_row_hash(
            row_id=log.id,
            user_id=str(log.user_id),
            action=log.action,
            details_json=log.details_json,
            timestamp=log.created_at,
            previous_hash=previous_hash,
        )
        
        # Check row hash
        if log.row_hash != expected_hash:
            result = {
                "valid": False,
                "broken_at": log.id,
                "total_checked": len(logs),
            }
            
            if raise_on_break:
                raise AuditIntegrityError(
                    f"Audit chain broken at row {log.id}: "
                    f"expected hash {expected_hash}, got {log.row_hash}"
                )
            
            logger.error(f"Audit integrity violation at row {log.id}")
            return result
        
        # Check previous_hash link
        if log.previous_hash != previous_hash:
            result = {
                "valid": False,
                "broken_at": log.id,
                "total_checked": len(logs),
            }
            
            if raise_on_break:
                raise AuditIntegrityError(
                    f"Audit chain broken at row {log.id}: "
                    f"previous_hash mismatch"
                )
            
            logger.error(f"Audit chain broken at row {log.id}: previous_hash mismatch")
            return result
        
        previous_hash = log.row_hash
    
    return {"valid": True, "broken_at": None, "total_checked": len(logs)}


def get_audit_logs(
    db: Session,
    org_id: str,
    action_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """
    Get audit logs for an organization.
    
    Returns (logs, total_count)
    """
    query = db.query(AuditLog).filter(AuditLog.org_id == org_id)
    
    if action_filter:
        query = query.filter(AuditLog.action.like(f"%{action_filter}%"))
    
    total = query.count()
    logs = query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()
    
    return logs, total
