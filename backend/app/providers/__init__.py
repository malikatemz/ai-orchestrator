"""Multi-provider LLM and scraper executor"""

from .executor import execute_task, TaskExecutionError

__all__ = ["execute_task", "TaskExecutionError"]
