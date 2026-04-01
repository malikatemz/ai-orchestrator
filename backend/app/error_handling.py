from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCode:
    WORKFLOW_NOT_FOUND = "AIORCH-NOTFOUND-001"
    TASK_NOT_FOUND = "AIORCH-NOTFOUND-002"
    DATABASE_UNAVAILABLE = "AIORCH-DEP-001"
    QUEUE_DEGRADED = "AIORCH-DEP-002"
    TASK_RETRY_EXHAUSTED = "AIORCH-TASK-003"
    INVALID_REQUEST = "AIORCH-VAL-001"
    INTERNAL_ERROR = "AIORCH-SYS-001"


@dataclass
class ApiError(Exception):
    code: str
    message: str
    status_code: int
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    retryable: bool = False
    details: dict[str, Any] | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "severity": self.severity.value,
                "retryable": self.retryable,
                "details": self.details or {},
            }
        }
